"""Private storage helpers for immutable, fictional demo seed documents."""
from __future__ import annotations
import hashlib
from pathlib import Path
from threading import Lock
from fastapi import HTTPException
from .config import settings
from .demo_data import all_seed_assets

_SETUP_LOCK = Lock()
_S3_READY_FOR: set[tuple[str, str]] = set()


def _safe_local_path(object_key: str) -> Path:
    if not object_key.startswith("demo-assets/seed/") or ".." in Path(object_key).parts:
        raise HTTPException(400, "Invalid demo evidence reference.")
    root = Path(settings.upload_dir).resolve()
    path = (root / object_key).resolve()
    if not path.is_relative_to(root):
        raise HTTPException(400, "Invalid demo evidence reference.")
    return path


def ensure_demo_seed_assets() -> str:
    """Ensure deterministic sample PDFs exist once; S3 objects remain private."""
    if settings.storage_provider == "local":
        for key, data in all_seed_assets():
            path = _safe_local_path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256(data).hexdigest()
            if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                temp = path.with_suffix(path.suffix + ".tmp")
                temp.write_bytes(data)
                temp.replace(path)
        return "local"
    if settings.storage_provider != "s3":
        raise HTTPException(503, "STORAGE_PROVIDER must be local or s3.")
    if not settings.s3_ready:
        raise HTTPException(503, "S3 is selected, but AWS_REGION or S3_BUCKET is missing. Configure the existing private bucket before starting a demo.")

    cache_key = (settings.aws_region, settings.s3_bucket)
    with _SETUP_LOCK:
        if cache_key in _S3_READY_FOR:
            return "s3"
        try:
            import boto3
            from botocore.exceptions import ClientError
            client = boto3.client("s3", region_name=settings.aws_region)
            client.head_bucket(Bucket=settings.s3_bucket)
            for key, data in all_seed_assets():
                digest = hashlib.sha256(data).hexdigest()
                found = False
                try:
                    meta = client.head_object(Bucket=settings.s3_bucket, Key=key)
                    found = meta.get("Metadata", {}).get("recycleproof-sha256") == digest
                except ClientError as exc:
                    code = str(exc.response.get("Error", {}).get("Code", ""))
                    if code not in {"404", "NoSuchKey", "NotFound"}:
                        raise
                if not found:
                    client.put_object(Bucket=settings.s3_bucket, Key=key, Body=data,
                                      ContentType="application/pdf", ServerSideEncryption="AES256",
                                      Metadata={"recycleproof-sha256": digest, "data-classification": "synthetic-demo"})
        except Exception as exc:
            raise HTTPException(502, f"Private S3 seed setup failed; no local fallback was used ({type(exc).__name__}).") from exc
        _S3_READY_FOR.add(cache_key)
    return "s3"


def demo_storage_status() -> dict:
    if settings.storage_provider == "local":
        return {"provider": "local", "aws_connected": False,
                "label": "Local development storage", "message": "Synthetic evidence is stored locally; AWS S3 is not connected."}
    if settings.storage_provider != "s3":
        return {"provider": settings.storage_provider, "aws_connected": False,
                "label": "Storage unavailable", "message": "STORAGE_PROVIDER is not configured as local or s3."}
    if not settings.s3_ready:
        return {"provider": "s3", "aws_connected": False,
                "label": "S3 not configured", "message": "AWS_REGION and S3_BUCKET are required; evidence is not reported as stored in AWS."}
    try:
        import boto3
        boto3.client("s3", region_name=settings.aws_region).head_bucket(Bucket=settings.s3_bucket)
        return {"provider": "s3", "aws_connected": True,
                "label": "Private AWS S3 verified", "message": "The configured private bucket passed a live connectivity check. Evidence downloads remain authorized by the demo session."}
    except Exception as exc:
        return {"provider": "s3", "aws_connected": False,
                "label": "S3 connection not verified", "message": f"The configured S3 bucket could not be verified ({type(exc).__name__}); no AWS connection is claimed."}


def read_demo_asset(provider: str, object_key: str) -> bytes:
    if not object_key.startswith("demo-assets/seed/") or ".." in Path(object_key).parts:
        raise HTTPException(400, "Invalid demo evidence reference.")
    if provider == "local":
        path = _safe_local_path(object_key)
        if not path.is_file():
            raise HTTPException(404, "Synthetic demo evidence file is missing.")
        return path.read_bytes()
    if provider != "s3" or not settings.s3_ready:
        raise HTTPException(503, "Demo evidence storage is not available.")
    try:
        import boto3
        from botocore.exceptions import ClientError
        return boto3.client("s3", region_name=settings.aws_region).get_object(
            Bucket=settings.s3_bucket, Key=object_key)["Body"].read()
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in {"404", "NoSuchKey", "NotFound"}:
            raise HTTPException(404, "Synthetic demo evidence file is missing.") from exc
        raise HTTPException(502, f"Private S3 evidence retrieval failed ({type(exc).__name__}).") from exc
    except Exception as exc:
        raise HTTPException(502, f"Private S3 evidence retrieval failed ({type(exc).__name__}).") from exc
