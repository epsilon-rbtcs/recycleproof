"""Session-scoped demo records and API serializers."""
from datetime import date
from typing import Any
from sqlalchemy.orm import Session
from .demo_data import SCENARIOS, EXPECTED_TYPES, document_asset
from .models import DemoClaim, DemoDocument, DemoFinding, DemoReview, DemoSession, DemoVerificationRun


def seed_demo_claims(db: Session, session: DemoSession, storage_provider: str) -> list[DemoClaim]:
    claims = []
    for scenario in SCENARIOS:
        claim = DemoClaim(
            demo_session_id=session.id, scenario_key=scenario["key"], reference=scenario["reference"],
            recycler=scenario["recycler"], facility=scenario["facility"],
            material_category=scenario["material_category"], claimed_quantity=scenario["claimed_quantity"],
            units=scenario["units"], shipment_quantity=scenario["shipment_quantity"],
            shipment_ids=list(scenario["shipment_ids"]), invoice_ids=list(scenario["invoice_ids"]),
            certificate_ids=list(scenario["certificate_ids"]),
            permit_expiry=date.fromisoformat(scenario["permit_expiry"]),
            processing_date=date.fromisoformat(scenario["processing_date"]),
            permit_categories=list(scenario["permit_categories"]), evidence_expected=list(EXPECTED_TYPES),
            details={**scenario["details"], "scenario_title": scenario["title"],
                     "scenario_description": scenario["scenario_description"], "fictional": True},
            status="NOT_VERIFIED", priority_score=0,
        )
        db.add(claim)
        db.flush()
        for spec in scenario["documents"]:
            key, payload = document_asset(scenario, spec)
            db.add(DemoDocument(
                demo_session_id=session.id, claim_id=claim.id, document_type=spec["document_type"],
                filename=spec["filename"], content_type="application/pdf", size_bytes=len(payload),
                storage_provider=storage_provider, object_key=key, summary=spec["summary"],
                extracted_text="\n".join(spec["body"]), extracted_fields=spec["extracted_fields"],
                extraction_status="SYNTHETIC_SOURCE",
            ))
        claims.append(claim)
    return claims


def reset_demo_claims(db: Session, session: DemoSession, storage_provider: str) -> list[DemoClaim]:
    # ORM deletes honor relationship cascades for reports, findings, documents, and reviews.
    for claim in db.query(DemoClaim).filter(DemoClaim.demo_session_id == session.id).all():
        db.delete(claim)
    db.flush()
    claims = seed_demo_claims(db, session, storage_provider)
    db.commit()
    return claims


def demo_finding_out(f: DemoFinding) -> dict[str, Any]:
    return {"id": f.id, "code": f.code, "severity": f.severity, "title": f.title,
            "description": f.description, "values_compared": f.values_compared or {},
            "document_refs": f.document_refs or [], "recommendation": f.recommendation}


def demo_run_out(run: DemoVerificationRun) -> dict[str, Any]:
    return {"id": run.id, "status": run.status, "priority_score": run.priority_score,
            "priority": run.priority, "score_explanation": run.score_explanation,
            "checks": run.checks or [], "missing_evidence": run.missing_evidence or [],
            "recommended_action": run.recommended_action,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "findings": [demo_finding_out(f) for f in run.findings]}


def demo_claim_out(claim: DemoClaim) -> dict[str, Any]:
    return {"id": claim.id, "scenario_key": claim.scenario_key, "reference": claim.reference,
            "scenario_title": claim.details.get("scenario_title", "Synthetic claim"),
            "scenario_description": claim.details.get("scenario_description", "Fictional demo data."),
            "recycler": claim.recycler, "facility": claim.facility,
            "material_category": claim.material_category, "claimed_quantity": claim.claimed_quantity,
            "units": claim.units, "processing_date": str(claim.processing_date) if claim.processing_date else None,
            "shipment_quantity": claim.shipment_quantity, "shipment_ids": claim.shipment_ids or [],
            "invoice_ids": claim.invoice_ids or [], "certificate_ids": claim.certificate_ids or [],
            "permit_expiry": str(claim.permit_expiry) if claim.permit_expiry else None,
            "permit_categories": claim.permit_categories or [], "evidence_expected": claim.evidence_expected or [],
            "status": claim.status, "priority_score": claim.priority_score,
            "created_at": claim.created_at.isoformat() if claim.created_at else None}


def demo_doc_out(doc: DemoDocument) -> dict[str, Any]:
    return {"id": doc.id, "document_type": doc.document_type, "filename": doc.filename,
            "content_type": doc.content_type, "size_bytes": doc.size_bytes,
            "storage_provider": doc.storage_provider, "summary": doc.summary,
            "extracted_text": doc.extracted_text, "extracted_fields": doc.extracted_fields or {},
            "extraction_status": doc.extraction_status}


def demo_detail_out(db: Session, claim: DemoClaim) -> dict[str, Any]:
    docs = db.query(DemoDocument).filter(DemoDocument.demo_session_id == claim.demo_session_id,
                                         DemoDocument.claim_id == claim.id).order_by(DemoDocument.id).all()
    runs = db.query(DemoVerificationRun).filter(DemoVerificationRun.demo_session_id == claim.demo_session_id,
                                                DemoVerificationRun.claim_id == claim.id).order_by(DemoVerificationRun.created_at.desc()).all()
    reviews = db.query(DemoReview).filter(DemoReview.demo_session_id == claim.demo_session_id,
                                          DemoReview.claim_id == claim.id).order_by(DemoReview.created_at.desc()).all()
    result = demo_claim_out(claim)
    result.update({"documents": [demo_doc_out(d) for d in docs],
                   "verification_runs": [demo_run_out(r) for r in runs],
                   "reviews": [{"id": r.id, "decision": r.decision, "comments": r.comments,
                                "reviewer_label": r.reviewer_label, "created_at": r.created_at.isoformat()}
                               for r in reviews]})
    return result
