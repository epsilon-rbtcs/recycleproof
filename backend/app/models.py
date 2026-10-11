from datetime import datetime, timezone
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from .db import Base

def now_utc(): return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

class OtpChallenge(Base):
    __tablename__ = "otp_challenges"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    otp_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)
    last_sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

class Claim(Base):
    __tablename__ = "claims"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    recycler: Mapped[str] = mapped_column(String(200))
    facility: Mapped[str] = mapped_column(String(200))
    material_category: Mapped[str] = mapped_column(String(100))
    claimed_quantity: Mapped[float] = mapped_column(Float)
    units: Mapped[str] = mapped_column(String(24), default="kg")
    processing_date: Mapped[datetime] = mapped_column(Date, nullable=True)
    shipment_ids: Mapped[list] = mapped_column(JSON, default=list)
    shipment_quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    invoice_ids: Mapped[list] = mapped_column(JSON, default=list)
    certificate_ids: Mapped[list] = mapped_column(JSON, default=list)
    permit_expiry: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    permit_categories: Mapped[list] = mapped_column(JSON, default=list)
    evidence_expected: Mapped[list] = mapped_column(JSON, default=lambda: ["invoice", "shipment_manifest", "weighbridge_receipt", "recycler_permit", "recycling_certificate"])
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(48), default="INSUFFICIENT_EVIDENCE")
    priority_score: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    documents = relationship("Document", back_populates="claim", cascade="all, delete-orphan")
    runs = relationship("VerificationRun", back_populates="claim", cascade="all, delete-orphan")

class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    document_type: Mapped[str] = mapped_column(String(48))
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_provider: Mapped[str] = mapped_column(String(16))
    object_key: Mapped[str] = mapped_column(String(512), unique=True)
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    extracted_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    extraction_status: Mapped[str] = mapped_column(String(32), default="NOT_PROCESSED")
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    claim = relationship("Claim", back_populates="documents")

class VerificationRun(Base):
    __tablename__ = "verification_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), index=True)
    status: Mapped[str] = mapped_column(String(48))
    priority_score: Mapped[int] = mapped_column(Integer)
    priority: Mapped[str] = mapped_column(String(16))
    score_explanation: Mapped[str] = mapped_column(Text)
    checks: Mapped[list] = mapped_column(JSON)
    missing_evidence: Mapped[list] = mapped_column(JSON)
    recommended_action: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    claim = relationship("Claim", back_populates="runs")
    findings = relationship("Finding", back_populates="run", cascade="all, delete-orphan")

class Finding(Base):
    __tablename__ = "findings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("verification_runs.id"), index=True)
    code: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    values_compared: Mapped[dict] = mapped_column(JSON, default=dict)
    document_refs: Mapped[list] = mapped_column(JSON, default=list)
    recommendation: Mapped[str] = mapped_column(Text)
    run = relationship("VerificationRun", back_populates="findings")

class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(32))
    comments: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class DemoSession(Base):
    """Opaque, revocable sandbox identity; deliberately unrelated to User."""
    __tablename__ = "demo_sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    claims = relationship("DemoClaim", back_populates="session", cascade="all, delete-orphan")


class DemoClaim(Base):
    """Synthetic claim stored in a per-session namespace, never owned by a User."""
    __tablename__ = "demo_claims"
    __table_args__ = (UniqueConstraint("demo_session_id", "scenario_key", name="uq_demo_session_scenario"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    demo_session_id: Mapped[str] = mapped_column(ForeignKey("demo_sessions.id", ondelete="CASCADE"), index=True)
    scenario_key: Mapped[str] = mapped_column(String(40))
    reference: Mapped[str] = mapped_column(String(48))
    recycler: Mapped[str] = mapped_column(String(200))
    facility: Mapped[str] = mapped_column(String(200))
    material_category: Mapped[str] = mapped_column(String(100))
    claimed_quantity: Mapped[float] = mapped_column(Float)
    units: Mapped[str] = mapped_column(String(24), default="kg")
    processing_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    shipment_ids: Mapped[list] = mapped_column(JSON, default=list)
    shipment_quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    invoice_ids: Mapped[list] = mapped_column(JSON, default=list)
    certificate_ids: Mapped[list] = mapped_column(JSON, default=list)
    permit_expiry: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    permit_categories: Mapped[list] = mapped_column(JSON, default=list)
    evidence_expected: Mapped[list] = mapped_column(JSON, default=list)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(48), default="INSUFFICIENT_EVIDENCE")
    priority_score: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    session = relationship("DemoSession", back_populates="claims")
    documents = relationship("DemoDocument", back_populates="claim", cascade="all, delete-orphan")
    runs = relationship("DemoVerificationRun", back_populates="claim", cascade="all, delete-orphan")
    reviews = relationship("DemoReview", back_populates="claim", cascade="all, delete-orphan")


class DemoDocument(Base):
    __tablename__ = "demo_documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    demo_session_id: Mapped[str] = mapped_column(ForeignKey("demo_sessions.id", ondelete="CASCADE"), index=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("demo_claims.id", ondelete="CASCADE"), index=True)
    document_type: Mapped[str] = mapped_column(String(48))
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100), default="application/pdf")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    storage_provider: Mapped[str] = mapped_column(String(16))
    object_key: Mapped[str] = mapped_column(String(512), index=True)
    summary: Mapped[str] = mapped_column(Text)
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    extracted_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    extraction_status: Mapped[str] = mapped_column(String(32), default="SYNTHETIC_SOURCE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    claim = relationship("DemoClaim", back_populates="documents")


class DemoVerificationRun(Base):
    __tablename__ = "demo_verification_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    demo_session_id: Mapped[str] = mapped_column(ForeignKey("demo_sessions.id", ondelete="CASCADE"), index=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("demo_claims.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(48))
    priority_score: Mapped[int] = mapped_column(Integer)
    priority: Mapped[str] = mapped_column(String(16))
    score_explanation: Mapped[str] = mapped_column(Text)
    checks: Mapped[list] = mapped_column(JSON)
    missing_evidence: Mapped[list] = mapped_column(JSON)
    recommended_action: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    claim = relationship("DemoClaim", back_populates="runs")
    findings = relationship("DemoFinding", back_populates="run", cascade="all, delete-orphan")


class DemoFinding(Base):
    __tablename__ = "demo_findings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("demo_verification_runs.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    values_compared: Mapped[dict] = mapped_column(JSON, default=dict)
    document_refs: Mapped[list] = mapped_column(JSON, default=list)
    recommendation: Mapped[str] = mapped_column(Text)
    run = relationship("DemoVerificationRun", back_populates="findings")


class DemoReview(Base):
    __tablename__ = "demo_reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    demo_session_id: Mapped[str] = mapped_column(ForeignKey("demo_sessions.id", ondelete="CASCADE"), index=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("demo_claims.id", ondelete="CASCADE"), index=True)
    reviewer_label: Mapped[str] = mapped_column(String(48), default="Demo reviewer")
    decision: Mapped[str] = mapped_column(String(40))
    comments: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    claim = relationship("DemoClaim", back_populates="reviews")
