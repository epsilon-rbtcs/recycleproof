import os, re, uuid
from pathlib import Path
from fastapi import HTTPException
from .config import settings

ALLOWED = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png"}

def save_file(data: bytes, content_type: str, original_name: str, owner_id: int):
    if content_type not in ALLOWED:
        raise HTTPException(415, "Only PDF, JPEG, and PNG evidence is accepted.")
    if not data or len(data) > settings.max_upload_bytes:
        raise HTTPException(413, f"File must be non-empty and at most {settings.max_upload_bytes // (1024*1024)} MB.")
    try:
        if content_type == "application/pdf":
            if data[:5] != b"%PDF-": raise ValueError("PDF signature missing")
            from pypdf import PdfReader
            import io
            if not PdfReader(io.BytesIO(data), strict=False).pages: raise ValueError("PDF has no pages")
        else:
            from PIL import Image
            import io
            expected = "JPEG" if content_type == "image/jpeg" else "PNG"
            with Image.open(io.BytesIO(data)) as image:
                if image.format != expected or image.width < 1 or image.height < 1: raise ValueError("Image format mismatch")
                image.verify()
    except Exception as exc:
        raise HTTPException(415, "Evidence content is not a valid readable PDF, JPEG, or PNG.") from exc
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", Path(original_name).name)[:160] or "evidence"
    key = f"users/{owner_id}/{uuid.uuid4().hex}-{safe}"
    if settings.storage_provider == "s3":
        if not settings.s3_ready:
            raise HTTPException(503, "S3 is selected but AWS_REGION or S3_BUCKET is missing.")
        try:
            import boto3
            client = boto3.client("s3", region_name=settings.aws_region)
            client.put_object(Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type, ServerSideEncryption="AES256")
            return "s3", key
        except Exception as exc:
            raise HTTPException(502, f"S3 upload failed; no local fallback was used ({type(exc).__name__}).") from exc
    if settings.storage_provider != "local":
        raise HTTPException(503, "STORAGE_PROVIDER must be local or s3.")
    dest = Path(settings.upload_dir) / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return "local", key

def read_file(provider: str, key: str) -> bytes:
    if provider == "s3":
        import boto3
        return boto3.client("s3", region_name=settings.aws_region).get_object(Bucket=settings.s3_bucket, Key=key)["Body"].read()
    path = Path(settings.upload_dir) / key
    if not path.resolve().is_relative_to(Path(settings.upload_dir).resolve()):
        raise HTTPException(400, "Invalid file reference.")
    if not path.exists(): raise HTTPException(404, "Stored evidence file not found.")
    return path.read_bytes()

def extract_pdf(data: bytes):
    try:
        from pypdf import PdfReader
        import io
        text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
        return text[:50000], "EXTRACTED" if text.strip() else "NO_TEXT", None
    except Exception:
        return "", "FAILED", None
