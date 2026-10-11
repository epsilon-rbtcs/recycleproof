"""Seed a fictional demo user and five fictional claims; safe to re-run."""
import sys
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from app.db import Base, engine, SessionLocal
from app.models import Claim, User
from app.security import hash_password
from app.verifier import verify_claim
Base.metadata.create_all(bind=engine)
db=SessionLocal()
try:
    user=db.query(User).filter_by(user_id="demo.audit").first()
    if not user:
        user=User(name="Demo Auditor",user_id="demo.audit",email="demo@example.test",password_hash=hash_password("DemoAudit2026!"))
        db.add(user);db.commit();db.refresh(user)
    existing={c.details.get("scenario") for c in db.query(Claim).filter_by(owner_id=user.id).all()}
    cases=[
      ("Consistent claim","Fictional Circular Works","Fictional North Plant","lithium-ion batteries",1250,"kg",1250,["SHIP-A-101"],date(2027,3,31),date(2026,9,1),["lithium-ion batteries"],"consistent"),
      ("Quantity discrepancy","Fictional Reclaim Lab","Fictional South Plant","mixed e-waste",2400,"kg",1980,["SHIP-B-205"],date(2027,3,31),date(2026,9,5),["mixed e-waste"],"quantity"),
      ("Duplicate shipment identifier","Fictional Metro Recovery","Fictional East Plant","printed circuit boards",900,"kg",900,["SHIP-C-001","SHIP-C-001"],date(2027,3,31),date(2026,9,10),["printed circuit boards"],"duplicate"),
      ("Expired permit","Fictional Old Permit Recycling","Fictional West Plant","lead-acid batteries",500,"kg",500,["SHIP-D-009"],date(2026,8,31),date(2026,9,12),["lead-acid batteries"],"expired"),
      ("Chronology / facility mismatch","Fictional Open Loop Co.","Fictional Central Plant","small appliances",670,"kg",670,["SHIP-E-010"],date(2027,5,31),date(2026,9,14),["small appliances"],"identity")]
    for name,recycler,facility,material,qty,unit,ship_qty,ship_ids,expiry,proc,cats,scenario in cases:
        if scenario in existing: continue
        c=Claim(owner_id=user.id,recycler=recycler,facility=facility,material_category=material,claimed_quantity=qty,units=unit,shipment_quantity=ship_qty,shipment_ids=ship_ids,invoice_ids=[f"INV-{scenario.upper()}-1"],certificate_ids=[f"CERT-{scenario.upper()}-1"],processing_date=proc,permit_expiry=expiry,permit_categories=cats,evidence_expected=[],details={"scenario":scenario,"fictional":True,"event_dates":[str(date(2026,9,20))] if scenario=="identity" else []})
        db.add(c);db.flush()
        result=verify_claim(c,[]);c.status=result["status"];c.priority_score=result["priority_score"]
    db.commit()
    print("Seeded fictional demo login: demo.audit / DemoAudit2026! (OTP still required; use DEV_OTP_ENABLED=true for local demos).")
    print("Five synthetic scenarios are saved as ordinary claims and can be re-run through the verification engine.")
finally: db.close()
