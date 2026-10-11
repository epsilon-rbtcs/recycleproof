import hmac, secrets, smtplib, time
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from .config import settings
from .db import Base, engine, get_db
from .models import Claim, DemoClaim, DemoDocument, DemoFinding, DemoReview, DemoSession, DemoVerificationRun, Document, Finding, OtpChallenge, Review, User, VerificationRun
from .security import current_demo_session, current_user, hash_password, verify_password, otp_hash, issue_demo_token, issue_token
from .storage import ALLOWED, extract_pdf, read_file, save_file
from .verifier import verify_claim
from .gemini_extractor import apply_extracted_fields, extract_document_fields
from .demo_data import SCENARIOS
from .demo_service import demo_claim_out, demo_detail_out, demo_run_out, seed_demo_claims, reset_demo_claims
from .demo_storage import demo_storage_status, ensure_demo_seed_assets, read_demo_asset

Base.metadata.create_all(bind=engine)
app = FastAPI(title="RecycleProof API", version="1.0.0", description="Explainable environmental recycling-claim review MVP. Automated flags support human review; they do not establish fraud.")
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

RATE: dict[str,list[float]] = {}
def throttle(key: str, max_calls: int, window: int):
    now = time.time(); hits = [t for t in RATE.get(key,[]) if now-t < window]
    if len(hits) >= max_calls: raise HTTPException(429, "Too many attempts. Please wait before trying again.")
    hits.append(now); RATE[key] = hits
    if len(RATE) > 10000:
        for old_key, old_hits in list(RATE.items()):
            fresh = [t for t in old_hits if now-t < 3600]
            if fresh: RATE[old_key] = fresh
            else: RATE.pop(old_key, None)

class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    user_id: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
class LoginIn(BaseModel):
    user_id: str
    password: str
class OtpIn(BaseModel):
    challenge_id: int
    code: str = Field(pattern=r"^\d{6}$")
class ResendIn(BaseModel):
    challenge_id: int
class ClaimIn(BaseModel):
    recycler: str = Field(min_length=1, max_length=200)
    facility: str = Field(min_length=1, max_length=200)
    material_category: str = Field(min_length=1, max_length=100)
    claimed_quantity: float = Field(gt=0)
    units: str = "kg"
    processing_date: date | None = None
    shipment_ids: list[str] = []
    shipment_quantity: float | None = Field(default=None, ge=0)
    invoice_ids: list[str] = []
    certificate_ids: list[str] = []
    permit_expiry: date | None = None
    permit_categories: list[str] = []
    evidence_expected: list[str] = ["invoice","shipment_manifest","weighbridge_receipt","recycler_permit","recycling_certificate"]
    details: dict[str,Any] = {}
class ReviewIn(BaseModel):
    decision: str = Field(pattern=r"^(accept|request_changes|escalate)$")
    comments: str = Field(default="", max_length=5000)
class DemoReviewIn(BaseModel):
    decision: str = Field(pattern=r"^(mark_for_further_review|request_changes|escalate)$")
    comments: str = Field(default="", max_length=2000)
class DocumentFieldsIn(BaseModel):
    extracted_fields: dict[str,Any] = {}


def profile(user): return {"id":user.id,"name":user.name,"user_id":user.user_id,"email":user.email}
def claim_out(c):
    return {"id":c.id,"recycler":c.recycler,"facility":c.facility,"material_category":c.material_category,"claimed_quantity":c.claimed_quantity,"units":c.units,"processing_date":str(c.processing_date) if c.processing_date else None,"shipment_quantity":c.shipment_quantity,"shipment_ids":c.shipment_ids or [],"invoice_ids":c.invoice_ids or [],"certificate_ids":c.certificate_ids or [],"permit_expiry":str(c.permit_expiry) if c.permit_expiry else None,"permit_categories":c.permit_categories or [],"evidence_expected":c.evidence_expected or [],"details":c.details or {},"status":c.status,"priority_score":c.priority_score,"created_at":c.created_at.isoformat() if c.created_at else None}
def doc_out(d): return {"id":d.id,"document_type":d.document_type,"filename":d.filename,"content_type":d.content_type,"size_bytes":d.size_bytes,"storage_provider":d.storage_provider,"extraction_status":d.extraction_status,"extracted_text":d.extracted_text,"extracted_fields":d.extracted_fields or {},"extraction_confidence":d.extraction_confidence,"created_at":d.created_at.isoformat() if d.created_at else None}
def run_out(r): return {"id":r.id,"status":r.status,"priority_score":r.priority_score,"priority":r.priority,"score_explanation":r.score_explanation,"checks":r.checks,"missing_evidence":r.missing_evidence,"recommended_action":r.recommended_action,"created_at":r.created_at.isoformat() if r.created_at else None,"findings":[{"id":f.id,"code":f.code,"severity":f.severity,"title":f.title,"description":f.description,"values_compared":f.values_compared,"document_refs":f.document_refs,"recommendation":f.recommendation} for f in r.findings]}
def owned_claim(db, claim_id, user):
    c=db.query(Claim).filter(Claim.id==claim_id,Claim.owner_id==user.id).first()
    if not c: raise HTTPException(404,"Claim not found.")
    return c

def send_otp(email, code):
    if not settings.smtp_ready:
        if settings.app_env != "production" and settings.dev_otp_enabled:
            # Development-only diagnostic; never returned by any production API response.
            print(f"[DEV OTP ONLY] recipient={email} code={code}", flush=True)
            return "development_console"
        raise HTTPException(503,"SMTP is not configured. Set SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, and SMTP_FROM_EMAIL, or explicitly enable DEV_OTP_ENABLED=true for local testing only.")
    message=EmailMessage(); message["Subject"]="Your RecycleProof sign-in code"; message["From"]=settings.smtp_from_email; message["To"]=email
    message.set_content(f"Your RecycleProof verification code is {code}. It expires in five minutes. If you did not request it, ignore this message.")
    try:
        with smtplib.SMTP(settings.smtp_host,settings.smtp_port,timeout=15) as server:
            if settings.smtp_use_tls: server.starttls()
            server.login(settings.smtp_username,settings.smtp_password); server.send_message(message)
        return "email"
    except Exception as exc: raise HTTPException(502,f"Email delivery failed ({type(exc).__name__}). Check SMTP settings.") from exc

@app.post("/api/demo/session", status_code=201)
def create_demo_session(request: Request, db: Session = Depends(get_db)):
    peer = request.client.host if request.client else "unknown"
    throttle("demo-session:" + peer, 8, 3600)
    ttl = settings.demo_session_ttl_minutes
    if ttl < 5 or ttl > 480:
        raise HTTPException(503, "DEMO_SESSION_TTL_MINUTES must be between 5 and 480.")
    if not settings.jwt_secret and settings.app_env == "production":
        raise HTTPException(503, "JWT_SECRET must be configured before demo sessions are available.")
    # Opportunistic bounded cleanup; immutable shared seed files are never removed.
    cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    for old in db.query(DemoSession).filter(DemoSession.expires_at < cutoff).limit(25).all():
        db.delete(old)
    provider = ensure_demo_seed_assets()
    now = datetime.now(timezone.utc)
    demo = DemoSession(id=secrets.token_urlsafe(32), created_at=now,
                       expires_at=now + timedelta(minutes=ttl), last_seen_at=now)
    try:
        db.add(demo)
        db.flush()
        seed_demo_claims(db, demo, provider)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(500, "Could not initialize the isolated demo workspace. Please retry.")
    return {"access_token": issue_demo_token(demo.id, demo.expires_at), "token_type": "Bearer",
            "mode": "demo", "scope": ["demo"], "expires_in": ttl * 60,
            "expires_at": demo.expires_at.isoformat()}


@app.get("/api/demo/status")
def demo_status(session: DemoSession = Depends(current_demo_session)):
    expires = session.expires_at.replace(tzinfo=timezone.utc) if session.expires_at.tzinfo is None else session.expires_at
    return {"mode": "demo", "label": "DEMO MODE — SYNTHETIC DATA",
            "expires_at": expires.isoformat(), "seconds_remaining": max(0, int((expires - datetime.now(timezone.utc)).total_seconds())),
            "storage": demo_storage_status()}


@app.get("/api/demo/claims")
def list_demo_claims(session: DemoSession = Depends(current_demo_session), db: Session = Depends(get_db)):
    rows = db.query(DemoClaim).filter(DemoClaim.demo_session_id == session.id).all()
    positions = {scenario["key"]: i for i, scenario in enumerate(SCENARIOS)}
    rows.sort(key=lambda c: positions.get(c.scenario_key, 999))
    return [demo_claim_out(claim) for claim in rows]


def owned_demo_claim(db: Session, claim_id: int, session: DemoSession) -> DemoClaim:
    claim = db.query(DemoClaim).filter(DemoClaim.id == claim_id,
                                       DemoClaim.demo_session_id == session.id).first()
    if not claim:
        raise HTTPException(404, "Demo claim not found in this session.")
    return claim


@app.get("/api/demo/claims/{claim_id}")
def get_demo_claim(claim_id: int, session: DemoSession = Depends(current_demo_session), db: Session = Depends(get_db)):
    return demo_detail_out(db, owned_demo_claim(db, claim_id, session))


@app.get("/api/demo/claims/{claim_id}/documents/{document_id}/download")
def download_demo_document(claim_id: int, document_id: int,
                           session: DemoSession = Depends(current_demo_session), db: Session = Depends(get_db)):
    owned_demo_claim(db, claim_id, session)
    doc = db.query(DemoDocument).filter(DemoDocument.id == document_id,
                                        DemoDocument.claim_id == claim_id,
                                        DemoDocument.demo_session_id == session.id).first()
    if not doc:
        raise HTTPException(404, "Demo document not found in this session.")
    content = read_demo_asset(doc.storage_provider, doc.object_key)
    return Response(content, media_type=doc.content_type,
                    headers={"Content-Disposition": f'attachment; filename="{Path(doc.filename).name}"',
                             "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@app.post("/api/demo/claims/{claim_id}/analyze")
def analyze_demo_claim(claim_id: int, session: DemoSession = Depends(current_demo_session), db: Session = Depends(get_db)):
    throttle("demo-verify:" + session.id, 12, 3600)
    claim = owned_demo_claim(db, claim_id, session)
    documents = db.query(DemoDocument).filter(DemoDocument.demo_session_id == session.id,
                                               DemoDocument.claim_id == claim.id).all()
    siblings = db.query(DemoClaim).filter(DemoClaim.demo_session_id == session.id).all()
    result = verify_claim(claim, documents, siblings)
    run = DemoVerificationRun(demo_session_id=session.id, claim_id=claim.id,
                              status=result["status"], priority_score=result["priority_score"],
                              priority=result["priority"], score_explanation=result["score_explanation"],
                              checks=result["checks"], missing_evidence=result["missing_evidence"],
                              recommended_action=result["recommended_action"])
    db.add(run)
    db.flush()
    for finding in result["findings"]:
        db.add(DemoFinding(run_id=run.id, **finding))
    claim.status = result["status"]
    claim.priority_score = result["priority_score"]
    db.commit()
    db.refresh(run)
    return demo_run_out(run)


@app.post("/api/demo/claims/{claim_id}/review", status_code=201)
def review_demo_claim(claim_id: int, body: DemoReviewIn,
                      session: DemoSession = Depends(current_demo_session), db: Session = Depends(get_db)):
    throttle("demo-review:" + session.id, 60, 3600)
    claim = owned_demo_claim(db, claim_id, session)
    row = DemoReview(demo_session_id=session.id, claim_id=claim.id,
                     decision=body.decision, comments=body.comments)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "decision": row.decision, "comments": row.comments,
            "reviewer_label": row.reviewer_label, "created_at": row.created_at.isoformat()}


@app.post("/api/demo/reset")
def reset_demo(session: DemoSession = Depends(current_demo_session), db: Session = Depends(get_db)):
    throttle("demo-reset:" + session.id, 4, 3600)
    provider = ensure_demo_seed_assets()
    claims = reset_demo_claims(db, session, provider)
    return {"message": "This demo session has been reset to the original fictional scenarios.",
            "claims": len(claims), "mode": "demo"}


@app.post("/api/demo/session/revoke")
def revoke_demo_session(session: DemoSession = Depends(current_demo_session), db: Session = Depends(get_db)):
    session.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Demo session revoked. Shared synthetic seed files were retained."}


@app.get("/api/health")
def health():
    return {"status":"ok","environment":settings.app_env,"smtp":{"configured":settings.smtp_ready,"diagnostic":"SMTP ready" if settings.smtp_ready else "SMTP not configured; real email OTP login will be unavailable."},"storage":{"provider":settings.storage_provider,"configured":settings.storage_provider=="local" or settings.s3_ready,"diagnostic":"S3 configured" if settings.s3_ready else "Local-development storage" if settings.storage_provider=="local" else "S3 settings incomplete"}}

@app.post("/api/auth/register",status_code=201)
def register(body:RegisterIn,request:Request,db:Session=Depends(get_db)):
    throttle("register:"+ (request.client.host if request.client else "unknown"),10,3600)
    uid=body.user_id.strip()
    if db.query(User).filter((User.user_id==uid)|(User.email==str(body.email).lower())).first(): raise HTTPException(409,"That user ID or email is already registered.")
    user=User(name=body.name.strip(),user_id=uid,email=str(body.email).lower(),password_hash=hash_password(body.password)); db.add(user)
    try: db.commit()
    except Exception: db.rollback(); raise HTTPException(409,"Could not create account; user ID or email may already exist.")
    return {"message":"Account created. Sign in with your user ID and password to receive an email OTP."}

@app.post("/api/auth/login")
def login(body:LoginIn,request:Request,db:Session=Depends(get_db)):
    throttle("login:"+(request.client.host if request.client else "unknown"),10,900)
    user=db.query(User).filter(User.user_id==body.user_id.strip()).first()
    if not user or not verify_password(body.password,user.password_hash): raise HTTPException(401,"Invalid user ID or password.")
    code=f"{secrets.randbelow(1_000_000):06d}"
    sent_via=send_otp(user.email,code)
    challenge=OtpChallenge(user_id=user.id,otp_hash=otp_hash(code),expires_at=datetime.now(timezone.utc)+timedelta(minutes=5),last_sent_at=datetime.now(timezone.utc))
    db.add(challenge);db.commit();db.refresh(challenge)
    result={"challenge_id":challenge.id,"expires_in":300,"message":"A six-digit code was sent to your registered email."}
    # In local opt-in development only, provide the code to make the flow testable without SMTP.
    if sent_via=="development_console" and settings.app_env!="production" and settings.dev_otp_enabled: result["dev_otp"]=code
    return result

@app.post("/api/auth/verify-otp")
def verify_otp(body:OtpIn,request:Request,db:Session=Depends(get_db)):
    throttle("otp:"+(request.client.host if request.client else "unknown"),20,900)
    ch=db.get(OtpChallenge,body.challenge_id)
    if not ch or ch.consumed: raise HTTPException(400,"This OTP challenge is invalid or already used.")
    if ch.attempts>=5: raise HTTPException(429,"Maximum attempts reached. Start login again.")
    expiry=ch.expires_at.replace(tzinfo=timezone.utc) if ch.expires_at.tzinfo is None else ch.expires_at
    if expiry < datetime.now(timezone.utc): ch.consumed=True;db.commit();raise HTTPException(400,"OTP expired. Start login again.")
    ch.attempts+=1
    if not hmac.compare_digest(ch.otp_hash,otp_hash(body.code)):
        if ch.attempts>=5: ch.consumed=True
        db.commit();raise HTTPException(400,"Incorrect OTP.")
    ch.consumed=True;db.commit()
    return {"access_token":issue_token(db.get(User,ch.user_id)),"token_type":"bearer"}

@app.post("/api/auth/resend")
def resend(body:ResendIn,request:Request,db:Session=Depends(get_db)):
    throttle("resend:"+(request.client.host if request.client else "unknown"),5,3600)
    ch=db.get(OtpChallenge,body.challenge_id)
    if not ch or ch.consumed: raise HTTPException(404,"Challenge not found or already used.")
    last=ch.last_sent_at.replace(tzinfo=timezone.utc) if ch.last_sent_at.tzinfo is None else ch.last_sent_at
    if (datetime.now(timezone.utc)-last).total_seconds()<60: raise HTTPException(429,"Please wait 60 seconds between OTP requests.")
    user=db.get(User,ch.user_id);code=f"{secrets.randbelow(1_000_000):06d}";sent=send_otp(user.email,code)
    ch.otp_hash=otp_hash(code);ch.expires_at=datetime.now(timezone.utc)+timedelta(minutes=5);ch.attempts=0;ch.last_sent_at=datetime.now(timezone.utc);db.commit()
    result={"message":"A new code was sent.","expires_in":300}
    if sent=="development_console" and settings.app_env!="production" and settings.dev_otp_enabled:result["dev_otp"]=code
    return result

@app.post("/api/auth/logout")
def logout(user:User=Depends(current_user)):
    return {"message":"Signed out. Remove the local bearer token to end this client session."}

@app.get("/api/auth/me")
def me(user:User=Depends(current_user)): return profile(user)

@app.get("/api/claims")
def list_claims(q:str="",status:str="",user:User=Depends(current_user),db:Session=Depends(get_db)):
    query=db.query(Claim).filter(Claim.owner_id==user.id)
    if q: query=query.filter((Claim.recycler.ilike(f"%{q}%"))|(Claim.facility.ilike(f"%{q}%"))|(Claim.material_category.ilike(f"%{q}%")))
    if status: query=query.filter(Claim.status==status)
    return [claim_out(c) for c in query.order_by(Claim.created_at.desc()).all()]

@app.post("/api/claims",status_code=201)
def create_claim(body:ClaimIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if body.units.lower() not in {"kg","kilogram","kilograms","tonne","tonnes","t","g","lb","lbs"}: raise HTTPException(422,"Supported units: kg, tonne, g, lb.")
    data=body.model_dump()
    c=Claim(owner_id=user.id,**data);db.add(c);db.commit();db.refresh(c);return claim_out(c)

@app.get("/api/claims/{claim_id}")
def get_claim(claim_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    c=owned_claim(db,claim_id,user); latest=sorted(c.runs,key=lambda r:r.created_at or datetime.min,reverse=True)
    reviews=db.query(Review).filter(Review.claim_id==c.id).order_by(Review.created_at.desc()).all()
    return {**claim_out(c),"documents":[doc_out(d) for d in c.documents],"verification_runs":[run_out(r) for r in latest],"reviews":[{"decision":r.decision,"comments":r.comments,"created_at":r.created_at.isoformat()} for r in reviews]}

@app.put("/api/claims/{claim_id}")
def update_claim(claim_id:int,body:ClaimIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    c=owned_claim(db,claim_id,user);data=body.model_dump()
    for k,v in data.items():setattr(c,k,v)
    db.commit();db.refresh(c);return claim_out(c)

@app.post("/api/claims/{claim_id}/documents",status_code=201)
async def upload_document(claim_id:int,file:UploadFile=File(...),document_type:str=Form(...),user:User=Depends(current_user),db:Session=Depends(get_db)):
    c=owned_claim(db,claim_id,user)
    if document_type not in {"invoice","shipment_manifest","weighbridge_receipt","recycler_permit","recycling_certificate","other"}:raise HTTPException(422,"Invalid document type.")
    data=await file.read(settings.max_upload_bytes+1);provider,key=save_file(data,file.content_type or "",file.filename or "evidence",user.id)
    text,status,confidence=extract_pdf(data) if file.content_type=="application/pdf" else ("","MANUAL_ENTRY_REQUIRED",None)
    extracted_fields = {}
    if file.content_type in ALLOWED:
        extraction = extract_document_fields(data, file.content_type, document_type)
        extracted_fields = extraction.fields.model_dump(mode="json", exclude_none=True)
        status = extraction.status
        confidence = extraction.fields.confidence
    d=Document(claim_id=c.id,owner_id=user.id,document_type=document_type,filename=Path(file.filename or "evidence").name[:255],content_type=file.content_type or "application/octet-stream",size_bytes=len(data),storage_provider=provider,object_key=key,extracted_text=text,extracted_fields=extracted_fields,extraction_status=status,extraction_confidence=confidence)
    db.add(d);db.commit();db.refresh(d);return doc_out(d)

@app.get("/api/claims/{claim_id}/documents/{document_id}/download")
def download_document(claim_id:int,document_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    owned_claim(db,claim_id,user);d=db.query(Document).filter(Document.id==document_id,Document.claim_id==claim_id,Document.owner_id==user.id).first()
    if not d:raise HTTPException(404,"Document not found.")
    content=read_file(d.storage_provider,d.object_key)
    return Response(content,media_type=d.content_type,headers={"Content-Disposition":f'attachment; filename="{d.filename}"','Cache-Control':'private, no-store'})

@app.patch("/api/claims/{claim_id}/documents/{document_id}/fields")
def correct_fields(claim_id:int,document_id:int,body:DocumentFieldsIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    owned_claim(db,claim_id,user);d=db.query(Document).filter(Document.id==document_id,Document.claim_id==claim_id,Document.owner_id==user.id).first()
    if not d:raise HTTPException(404,"Document not found.")
    d.extracted_fields=body.extracted_fields;d.extraction_status="USER_CONFIRMED";db.commit();return doc_out(d)

@app.post("/api/claims/{claim_id}/verify")
def run_verification(claim_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    c=owned_claim(db,claim_id,user);apply_extracted_fields(c,c.documents);siblings=db.query(Claim).filter(Claim.owner_id==user.id).all();result=verify_claim(c,c.documents,siblings)
    run=VerificationRun(claim_id=c.id,status=result["status"],priority_score=result["priority_score"],priority=result["priority"],score_explanation=result["score_explanation"],checks=result["checks"],missing_evidence=result["missing_evidence"],recommended_action=result["recommended_action"])
    db.add(run);db.flush()
    for f in result["findings"]:db.add(Finding(run_id=run.id,**f))
    c.status=result["status"];c.priority_score=result["priority_score"];db.commit();db.refresh(run);return run_out(run)

@app.get("/api/claims/{claim_id}/reports/latest")
def latest_report(claim_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    c=owned_claim(db,claim_id,user);r=db.query(VerificationRun).filter(VerificationRun.claim_id==c.id).order_by(VerificationRun.created_at.desc()).first()
    if not r:raise HTTPException(404,"No verification run yet.")
    return run_out(r)

@app.post("/api/claims/{claim_id}/reviews",status_code=201)
def review_claim(claim_id:int,body:ReviewIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    c=owned_claim(db,claim_id,user);r=Review(claim_id=c.id,reviewer_id=user.id,decision=body.decision,comments=body.comments);db.add(r);db.commit();db.refresh(r)
    return {"id":r.id,"decision":r.decision,"comments":r.comments,"created_at":r.created_at.isoformat()}

@app.get("/api/dashboard")
def dashboard(user:User=Depends(current_user),db:Session=Depends(get_db)):
    claims=db.query(Claim).filter(Claim.owner_id==user.id).order_by(Claim.created_at.desc()).all()
    return {"total_claims":len(claims),"needs_review":sum(1 for c in claims if c.status=="NEEDS_REVIEW"),"high_priority":sum(1 for c in claims if c.priority_score>=60),"recent_claims":[claim_out(c) for c in claims[:5]],"findings_count":sum(len(r.findings) for c in claims for r in c.runs)}

@app.get("/api/storage/status")
def storage_status(user:User=Depends(current_user),db:Session=Depends(get_db)):
    count=db.query(Document).filter(Document.owner_id==user.id).count()
    return {"provider":settings.storage_provider,"configured":settings.storage_provider=="local" or settings.s3_ready,"successful_uploads":count,"bucket":settings.s3_bucket if settings.s3_ready else None,"label":"AWS S3" if settings.storage_provider=="s3" and settings.s3_ready else "Local development storage" if settings.storage_provider=="local" else "S3 not configured"}
