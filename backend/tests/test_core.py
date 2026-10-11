import os
os.environ.setdefault("JWT_SECRET","test-secret-long-enough-for-jwt")
os.environ.setdefault("DEV_OTP_ENABLED","true")
os.environ.setdefault("APP_ENV","development")
from datetime import date
from types import SimpleNamespace
from fastapi.testclient import TestClient
from app.main import app
from app.security import hash_password,verify_password
from app.verifier import normalize_kg,verify_claim

client=TestClient(app)

def claim(**kwargs):
    base=dict(material_category="circuit boards",claimed_quantity=1000,units="kg",shipment_quantity=1000,shipment_ids=["S-1"],invoice_ids=["I-1"],certificate_ids=["C-1"],permit_expiry=date(2027,1,1),processing_date=date(2026,1,1),permit_categories=["circuit boards"],evidence_expected=[],details={})
    base.update(kwargs)
    return SimpleNamespace(**base)

def test_password_is_salted_and_verifies():
    a=hash_password("CorrectHorseBattery1!");b=hash_password("CorrectHorseBattery1!")
    assert a!=b and verify_password("CorrectHorseBattery1!",a) and not verify_password("bad",a)

def test_units_convert_and_unknown_is_not_guessed():
    assert normalize_kg(1,"tonne")==1000
    assert normalize_kg(1,"mystery") is None

def test_consistent_claim_and_quantity_discrepancy():
    result=verify_claim(claim(),[])
    assert result["status"]=="NO_MAJOR_INCONSISTENCY_DETECTED"
    bad=verify_claim(claim(shipment_quantity=800),[])
    assert any(f["code"]=="QUANTITY_DISCREPANCY" for f in bad["findings"])

def test_duplicate_and_expired_permit_and_missing_evidence():
    result=verify_claim(claim(shipment_ids=["S-1","S-1"],permit_expiry=date(2025,1,1),evidence_expected=["invoice"]),[])
    codes={f["code"] for f in result["findings"]}
    assert {"DUPLICATE_IDENTIFIER","EXPIRED_PERMIT","MISSING_EVIDENCE"}<=codes

def test_health_and_private_routes():
    assert client.get("/api/health").status_code==200
    assert client.get("/api/claims").status_code==401

def test_full_auth_and_claim_flow():
    suffix=os.urandom(4).hex()
    r=client.post("/api/auth/register",json={"name":"Test Auditor","user_id":"test_"+suffix,"email":"test+"+suffix+"@example.com","password":"StrongTestPass2026!"})
    assert r.status_code==201,r.text
    login=client.post("/api/auth/login",json={"user_id":"test_"+suffix,"password":"StrongTestPass2026!"})
    assert login.status_code==200,login.text
    code=login.json().get("dev_otp")
    assert code and len(code)==6
    token=client.post("/api/auth/verify-otp",json={"challenge_id":login.json()["challenge_id"],"code":code}).json()["access_token"]
    headers={"Authorization":"Bearer "+token}
    created=client.post("/api/claims",headers=headers,json={"recycler":"Fictional Demo","facility":"Plant A","material_category":"circuit boards","claimed_quantity":10,"units":"kg","shipment_quantity":10,"shipment_ids":["S-10"],"permit_expiry":"2027-01-01","processing_date":"2026-01-01","permit_categories":["circuit boards"],"evidence_expected":[]})
    assert created.status_code==201,created.text
    result=client.post(f"/api/claims/{created.json()['id']}/verify",headers=headers)
    assert result.status_code==200 and result.json()["status"]=="NO_MAJOR_INCONSISTENCY_DETECTED"

def test_invalid_upload_rejected():
    suffix=os.urandom(4).hex(); client.post("/api/auth/register",json={"name":"Upload User","user_id":"upload_"+suffix,"email":"upload+"+suffix+"@example.com","password":"StrongUploadPass2026!"})
    login_response=client.post("/api/auth/login",json={"user_id":"upload_"+suffix,"password":"StrongUploadPass2026!"})
    assert login_response.status_code==200,login_response.text
    login=login_response.json()
    token=client.post("/api/auth/verify-otp",json={"challenge_id":login["challenge_id"],"code":login["dev_otp"]}).json()["access_token"]
    h={"Authorization":"Bearer "+token}
    c=client.post("/api/claims",headers=h,json={"recycler":"Fictional Demo","facility":"Plant A","material_category":"devices","claimed_quantity":5,"evidence_expected":[]}).json()
    r=client.post(f"/api/claims/{c['id']}/documents",headers=h,data={"document_type":"invoice"},files={"file":("fake.pdf",b"not a pdf","application/pdf")})
    assert r.status_code==415


def test_cross_claim_duplicate_identifier():
    current=claim(id=10,shipment_ids=["SHIP-REUSED"])
    sibling=claim(id=11,shipment_ids=["ship-reused"])
    result=verify_claim(current,[],[current,sibling])
    duplicate=next(f for f in result["findings"] if f["code"]=="DUPLICATE_IDENTIFIER")
    assert "ship-reused" in duplicate["values_compared"]["identifiers"]
    assert duplicate["values_compared"]["other_claim_ids"]["ship-reused"]==[11]

def test_incorrect_and_expired_otp():
    from datetime import datetime,timedelta,timezone
    from app.db import SessionLocal
    from app.models import OtpChallenge
    suffix=os.urandom(4).hex()
    client.post("/api/auth/register",json={"name":"OTP User","user_id":"otp_"+suffix,"email":"otp+"+suffix+"@example.com","password":"StrongOtpPass2026!"})
    login=client.post("/api/auth/login",json={"user_id":"otp_"+suffix,"password":"StrongOtpPass2026!"}).json()
    bad=client.post("/api/auth/verify-otp",json={"challenge_id":login["challenge_id"],"code":"000000" if login["dev_otp"]!="000000" else "000001"})
    assert bad.status_code==400
    db=SessionLocal()
    try:
        ch=db.get(OtpChallenge,login["challenge_id"])
        ch.expires_at=datetime.now(timezone.utc)-timedelta(minutes=1);db.commit()
    finally:db.close()
    expired=client.post("/api/auth/verify-otp",json={"challenge_id":login["challenge_id"],"code":login["dev_otp"]})
    assert expired.status_code==400 and "expired" in expired.json()["detail"].lower()

def test_s3_write_failure_does_not_fallback(monkeypatch,tmp_path):
    import boto3
    import io
    from types import SimpleNamespace
    from fastapi import HTTPException
    from app.config import settings
    from app.storage import save_file
    from pypdf import PdfWriter
    pdf=io.BytesIO();writer=PdfWriter();writer.add_blank_page(width=72,height=72);writer.write(pdf)
    monkeypatch.setattr(settings,"storage_provider","s3")
    monkeypatch.setattr(settings,"aws_region","us-east-1")
    monkeypatch.setattr(settings,"s3_bucket","private-test-bucket")
    monkeypatch.setattr(settings,"upload_dir",str(tmp_path))
    def failed_client(*args,**kwargs):
        def fail(**kwargs): raise RuntimeError("simulated S3 failure")
        return SimpleNamespace(put_object=fail)
    monkeypatch.setattr(boto3,"client",failed_client)
    try:
        save_file(pdf.getvalue(), "application/pdf", "test.pdf", 7)
        assert False,"Expected S3 failure"
    except HTTPException as exc:
        assert exc.status_code==502 and "no local fallback" in exc.detail
    assert not list(tmp_path.rglob("*"))

def test_malformed_document_content_is_rejected(monkeypatch,tmp_path):
    from fastapi import HTTPException
    from app.config import settings
    from app.storage import save_file
    monkeypatch.setattr(settings,"storage_provider","local")
    monkeypatch.setattr(settings,"upload_dir",str(tmp_path))
    for data,kind,name in [(b"%PDF-1.4 but not a document","application/pdf","bad.pdf"),(b"\x89PNG\r\n\x1a\nnot-an-image","image/png","bad.png")]:
        try:
            save_file(data,kind,name,9)
            assert False,"Expected invalid file rejection"
        except HTTPException as exc:
            assert exc.status_code==415
    assert not list(tmp_path.rglob("*"))


def _new_demo():
    from app.main import RATE
    # Keep independent tests from consuming each other's per-IP session quota.
    RATE.pop("demo-session:testclient", None)
    response = client.post("/api/demo/session")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["mode"] == "demo" and body["scope"] == ["demo"]
    return {"Authorization": "Bearer " + body["access_token"]}, body


def test_demo_session_is_public_synthetic_and_documents_are_session_authorized(tmp_path, monkeypatch):
    import io
    from pypdf import PdfReader
    from app.config import settings
    monkeypatch.setattr(settings, "storage_provider", "local")
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    headers, body = _new_demo()
    assert body["expires_in"] == settings.demo_session_ttl_minutes * 60
    claims = client.get("/api/demo/claims", headers=headers)
    assert claims.status_code == 200 and len(claims.json()) == 5
    assert all("fictional" in c["scenario_description"].lower() or "fictional" in c["recycler"].lower() for c in claims.json())
    quantity = next(c for c in claims.json() if c["scenario_key"] == "quantity_discrepancy")
    detail = client.get(f"/api/demo/claims/{quantity['id']}", headers=headers)
    assert detail.status_code == 200 and len(detail.json()["documents"]) == 5
    assert {d["document_type"] for d in detail.json()["documents"]} >= {"invoice", "shipment_manifest"}
    document = next(d for d in detail.json()["documents"] if d["document_type"] == "invoice")
    downloaded = client.get(f"/api/demo/claims/{quantity['id']}/documents/{document['id']}/download", headers=headers)
    assert downloaded.status_code == 200 and downloaded.content.startswith(b"%PDF-")
    assert "FICTIONAL SAMPLE" in PdfReader(io.BytesIO(downloaded.content)).pages[0].extract_text()
    status = client.get("/api/demo/status", headers=headers).json()
    assert status["label"] == "DEMO MODE — SYNTHETIC DATA"
    assert status["storage"]["provider"] == "local" and status["storage"]["aws_connected"] is False
    assert "not connected" in status["storage"]["message"].lower()


def test_demo_verification_runs_real_engine_for_all_five_scenarios():
    headers, _ = _new_demo()
    claims = client.get("/api/demo/claims", headers=headers).json()
    results = {}
    for claim_row in claims:
        response = client.post(f"/api/demo/claims/{claim_row['id']}/analyze", headers=headers)
        assert response.status_code == 200, response.text
        results[claim_row["scenario_key"]] = response.json()
    assert results["consistent"]["status"] == "NO_MAJOR_INCONSISTENCY_DETECTED"
    quantity = results["quantity_discrepancy"]
    finding = next(f for f in quantity["findings"] if f["code"] == "QUANTITY_DISCREPANCY")
    assert finding["values_compared"]["claimed_quantity"] == 500
    assert finding["values_compared"]["shipment_quantity"] == 320
    assert finding["values_compared"]["difference"] == 180
    assert finding["values_compared"]["units"] == "tonnes"
    assert "180 tonnes" in finding["description"]
    assert len(finding["document_refs"]) >= 2
    duplicate = next(f for f in results["duplicate_shipment"]["findings"] if f["code"] == "DUPLICATE_IDENTIFIER")
    assert len(duplicate["document_refs"]) == 2
    expired = next(f for f in results["expired_permit"]["findings"] if f["code"] == "EXPIRED_PERMIT")
    assert expired["document_refs"]
    identity = results["identity_chronology"]["findings"]
    assert {f["code"] for f in identity} >= {"FACILITY_IDENTITY_MISMATCH", "CHRONOLOGY_CONFLICT"}


def test_demo_and_real_tokens_and_other_sessions_are_strictly_separate():
    demo_a, _ = _new_demo()
    demo_b, _ = _new_demo()
    claim_a = client.get("/api/demo/claims", headers=demo_a).json()[0]
    claim_b = client.get("/api/demo/claims", headers=demo_b).json()[0]
    assert client.get(f"/api/demo/claims/{claim_a['id']}", headers=demo_b).status_code == 404
    assert client.get(f"/api/demo/claims/{claim_b['id']}", headers=demo_a).status_code == 404
    assert client.get("/api/claims", headers=demo_a).status_code == 401
    assert client.get("/api/auth/me", headers=demo_a).status_code == 401
    assert client.get("/api/demo/claims", headers={"Authorization": "Bearer not-a-demo-token"}).status_code == 401

    suffix = os.urandom(4).hex()
    registered = client.post("/api/auth/register", json={"name": "Isolation Tester", "user_id": "iso_"+suffix,
                                 "email": "iso+"+suffix+"@example.com", "password": "StrongIsolationPass2026!"})
    assert registered.status_code == 201
    login = client.post("/api/auth/login", json={"user_id": "iso_"+suffix, "password": "StrongIsolationPass2026!"}).json()
    real_token = client.post("/api/auth/verify-otp", json={"challenge_id": login["challenge_id"], "code": login["dev_otp"]}).json()["access_token"]
    real_headers = {"Authorization": "Bearer " + real_token}
    real_claim = client.post("/api/claims", headers=real_headers, json={"recycler": "Private fictional organization", "facility": "Private plant",
                         "material_category": "paper", "claimed_quantity": 10, "shipment_quantity": 10, "shipment_ids": ["PRIVATE-"+suffix],
                         "permit_expiry": "2027-01-01", "processing_date": "2026-01-01", "permit_categories": ["paper"], "evidence_expected": []})
    assert real_claim.status_code == 201
    assert client.get(f"/api/claims/{real_claim.json()['id']}", headers=demo_a).status_code == 401
    assert client.get("/api/demo/claims", headers=real_headers).status_code == 401


def test_demo_review_is_session_scoped_and_reset_restores_seed_data():
    headers, _ = _new_demo()
    other_headers, _ = _new_demo()
    claim = next(c for c in client.get("/api/demo/claims", headers=headers).json() if c["scenario_key"] == "quantity_discrepancy")
    review = client.post(f"/api/demo/claims/{claim['id']}/review", headers=headers,
                         json={"decision": "mark_for_further_review", "comments": "Compare the invoice with both shipment records."})
    assert review.status_code == 201
    assert client.get(f"/api/demo/claims/{claim['id']}", headers=other_headers).status_code == 404
    assert client.post("/api/demo/reset", headers=headers).status_code == 200
    restored = client.get(f"/api/demo/claims/{claim['id']}", headers=headers)
    # Reset replaces the session's claim rows; obtain the restored record by its stable scenario key.
    rows = client.get("/api/demo/claims", headers=headers).json()
    restored_row = next(c for c in rows if c["scenario_key"] == "quantity_discrepancy")
    restored = client.get(f"/api/demo/claims/{restored_row['id']}", headers=headers).json()
    assert restored["status"] == "NOT_VERIFIED"
    assert restored["verification_runs"] == [] and restored["reviews"] == []
    assert restored["claimed_quantity"] == 500 and restored["shipment_quantity"] == 320


def test_expired_demo_token_is_rejected_and_revoked():
    from datetime import datetime, timedelta, timezone
    from app.db import SessionLocal
    from app.models import DemoSession
    from app.security import _demo_signing_key
    import jwt
    headers, body = _new_demo()
    token = body["access_token"]
    sid = jwt.decode(token, _demo_signing_key(), algorithms=["HS256"], audience="recycleproof-demo", issuer="recycleproof", options={"verify_exp": False})["sid"]
    db = SessionLocal()
    try:
        session = db.get(DemoSession, sid)
        session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()
    response = client.get("/api/demo/claims", headers=headers)
    assert response.status_code == 401 and "expired" in response.json()["detail"].lower()
    db = SessionLocal()
    try:
        assert db.get(DemoSession, sid).revoked_at is not None
    finally:
        db.close()


def test_demo_session_creation_rate_limit(monkeypatch, tmp_path):
    from app.config import settings
    from app.main import RATE
    monkeypatch.setattr(settings, "storage_provider", "local")
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    RATE.clear()
    for _ in range(8):
        response = client.post("/api/demo/session")
        assert response.status_code == 201, response.text
    limited = client.post("/api/demo/session")
    assert limited.status_code == 429
    RATE.clear()


def test_s3_demo_seed_is_idempotent_private_and_reports_only_verified_connectivity(monkeypatch):
    import boto3
    from botocore.exceptions import ClientError
    from app.config import settings
    from app import demo_storage
    from app.demo_data import all_seed_assets
    monkeypatch.setattr(settings, "storage_provider", "s3")
    monkeypatch.setattr(settings, "aws_region", "us-east-1")
    monkeypatch.setattr(settings, "s3_bucket", "private-demo-test-bucket")
    demo_storage._S3_READY_FOR.clear()
    uploads = []
    class FakeS3:
        def head_bucket(self, **kwargs): return {}
        def head_object(self, **kwargs): raise ClientError({"Error": {"Code": "404", "Message": "missing"}}, "HeadObject")
        def put_object(self, **kwargs): uploads.append(kwargs); return {}
    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: FakeS3())
    assert demo_storage.ensure_demo_seed_assets() == "s3"
    assert len(uploads) == len(all_seed_assets())
    assert all(item["Key"].startswith("demo-assets/seed/") and "ACL" not in item for item in uploads)
    assert all(item["ServerSideEncryption"] == "AES256" for item in uploads)
    assert demo_storage.ensure_demo_seed_assets() == "s3" and len(uploads) == len(all_seed_assets())
    status = demo_storage.demo_storage_status()
    assert status["aws_connected"] is True and status["provider"] == "s3"


def test_s3_seed_failure_never_falls_back_or_returns_success(monkeypatch, tmp_path):
    import boto3
    from app.config import settings
    from app.main import RATE
    monkeypatch.setattr(settings, "storage_provider", "s3")
    monkeypatch.setattr(settings, "aws_region", "us-east-1")
    monkeypatch.setattr(settings, "s3_bucket", "unreachable-demo-test-bucket")
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    from app import demo_storage
    demo_storage._S3_READY_FOR.clear()
    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("no credentials")))
    RATE.pop("demo-session:testclient", None)
    response = client.post("/api/demo/session")
    assert response.status_code == 502
    assert "no local fallback" in response.json()["detail"].lower()
    assert not (tmp_path / "demo-assets").exists()
