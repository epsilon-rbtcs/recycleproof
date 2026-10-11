from datetime import date

UNIT_TO_KG = {"kg": 1.0, "kilogram": 1.0, "kilograms": 1.0, "tonne": 1000.0, "tonnes": 1000.0, "t": 1000.0, "g": 0.001, "lb": 0.45359237, "lbs": 0.45359237}

def normalize_kg(qty, unit):
    factor = UNIT_TO_KG.get((unit or "").strip().lower())
    return float(qty) * factor if factor else None

def verify_claim(claim, documents, other_claims=None):
    findings, checks = [], []
    def add_check(code, outcome, detail): checks.append({"code":code,"outcome":outcome,"detail":detail})
    def finding(code, severity, title, description, values=None, refs=None, recommendation=None):
        findings.append({"code":code,"severity":severity,"title":title,"description":description,"values_compared":values or {},"document_refs":refs or [],"recommendation":recommendation or "Request and reconcile source records before closing this review."})
    kinds = {d.document_type for d in documents}
    missing = [x for x in (claim.evidence_expected or []) if x not in kinds]
    if missing:
        add_check("EVIDENCE_COMPLETENESS","UNAVAILABLE",f"Missing evidence types: {', '.join(missing)}")
        finding("MISSING_EVIDENCE","medium","Evidence package is incomplete",f"No uploaded document was classified as: {', '.join(missing)}.",{"missing":missing},[d.id for d in documents],"Upload the missing evidence or document why it is unavailable.")
    else: add_check("EVIDENCE_COMPLETENESS","PASSED","All expected document types have at least one upload.")
    if claim.permit_expiry:
        if claim.processing_date and claim.permit_expiry < claim.processing_date:
            add_check("PERMIT_VALIDITY","FAILED",f"Permit expired {claim.permit_expiry} before processing date {claim.processing_date}.")
            permit_refs = [d.id for d in documents if d.document_type == "recycler_permit"]
            finding("EXPIRED_PERMIT","high","Permit appears expired on processing date",f"Recorded permit expiry {claim.permit_expiry} precedes processing date {claim.processing_date}.",{"permit_expiry":str(claim.permit_expiry),"processing_date":str(claim.processing_date)},permit_refs,"Confirm the permit and processing date with the competent authority.")
        else: add_check("PERMIT_VALIDITY","PASSED","Recorded permit covers the relevant processing date.")
    else:
        add_check("PERMIT_VALIDITY","UNAVAILABLE","Permit expiry date was not provided.")
        finding("PERMIT_DATE_UNAVAILABLE","medium","Permit validity cannot be assessed","Enter the permit expiry date and processing date.",{},[],"Review the valid permit and enter its effective dates.")
    cats = [str(c).lower() for c in (claim.permit_categories or [])]
    if cats:
        if claim.material_category.lower() not in cats:
            add_check("FACILITY_CATEGORY","FAILED","Claimed material is not in recorded permit categories.")
            finding("CATEGORY_MISMATCH","high","Material category is not listed on recorded permit","The claim category does not match the permit categories entered.",{"claim_category":claim.material_category,"permit_categories":claim.permit_categories},[],"Verify authorized waste codes and correct any data-entry errors.")
        else: add_check("FACILITY_CATEGORY","PASSED","Claim category matches the recorded permit categories.")
    else: add_check("FACILITY_CATEGORY","UNAVAILABLE","No permit category data entered; identity/authorization is not independently verified.")
    claimed = normalize_kg(claim.claimed_quantity, claim.units)
    shipped = normalize_kg(claim.shipment_quantity, claim.units) if claim.shipment_quantity is not None else None
    if claimed is None:
        add_check("QUANTITY_RECONCILIATION","UNAVAILABLE",f"Unsupported unit: {claim.units}.")
        finding("UNIT_AMBIGUOUS","medium","Quantity unit is unsupported","No conversion was attempted because the unit is ambiguous.",{"quantity":claim.claimed_quantity,"unit":claim.units},[],"Enter a supported unit (kg, tonne, g, or lb) and reconcile quantities.")
    elif shipped is None:
        add_check("QUANTITY_RECONCILIATION","UNAVAILABLE","Linked shipment/weighbridge total was not entered.")
        finding("SHIPMENT_TOTAL_MISSING","medium","Claim quantity cannot be reconciled","Enter the shipment or weighbridge total to compare it with the claim.",{"claimed_kg":claimed},[],"Enter sourced shipment/weighbridge values and link the documents.")
    elif abs(claimed-shipped) > max(1.0, claimed*0.02):
        add_check("QUANTITY_RECONCILIATION","FAILED",f"Claim {claimed:g} kg differs from linked shipment total {shipped:g} kg.")
        difference = float(claim.claimed_quantity) - float(claim.shipment_quantity)
        quantity_refs = [d.id for d in documents if d.document_type in {"invoice", "shipment_manifest", "weighbridge_receipt"}]
        finding("QUANTITY_DISCREPANCY","high","Claim and shipment quantities differ",f"Claim {claim.claimed_quantity:g} {claim.units} differs from linked shipment total {claim.shipment_quantity:g} {claim.units}; the difference is {abs(difference):g} {claim.units} and exceeds the 2% or 1 kg tolerance.",{"claimed_quantity":claim.claimed_quantity,"shipment_quantity":claim.shipment_quantity,"difference":difference,"units":claim.units,"claimed_kg":claimed,"shipment_kg":shipped,"difference_kg":claimed-shipped},quantity_refs,"Reconcile the invoice, manifests, and weighbridge tickets; request records for any additional inventory or shipments. This automated discrepancy is not proof of misconduct.")
    else: add_check("QUANTITY_RECONCILIATION","PASSED",f"Claim and shipment values reconcile within tolerance ({claimed:g} kg vs {shipped:g} kg).")
    other_claims = other_claims or []
    for field, title in [("shipment_ids","Duplicate shipment identifier"),("invoice_ids","Duplicate invoice identifier"),("certificate_ids","Duplicate certificate identifier")]:
        vals = [str(x).strip().lower() for x in (getattr(claim, field) or []) if str(x).strip()]
        duplicates = sorted({x for x in vals if vals.count(x) > 1})
        cross_claim = {str(x).strip().lower(): [c.id for c in other_claims if c.id != claim.id and str(x).strip().lower() in [str(y).strip().lower() for y in (getattr(c, field) or [])]] for x in vals}
        cross_claim = {key: ids for key, ids in cross_claim.items() if ids}
        duplicates = sorted(set(duplicates) | set(cross_claim))
        if duplicates:
            add_check(field.upper(),"FAILED",f"Repeated identifiers: {', '.join(duplicates)}")
            duplicate_refs = []
            for d in documents:
                fields = d.extracted_fields or {}
                values = [fields.get(k) for k in ("identifier", "reference_id", "transaction_id", "shipment_id", "invoice_id", "certificate_id")]
                values = [str(v).strip().lower() for v in values if v is not None]
                if any(v in duplicates for v in values): duplicate_refs.append(d.id)
            finding("DUPLICATE_IDENTIFIER","high",title,f"Repeated values found within this claim or another claim in this account: {', '.join(duplicates)}.",{"identifiers":duplicates,"other_claim_ids":cross_claim},duplicate_refs,"Compare both supporting source records and check whether the same transaction was counted more than once.")
        else: add_check(field.upper(),"PASSED" if vals else "UNAVAILABLE","No duplicate within provided identifiers." if vals else "No identifiers were entered.")
    dates = claim.details.get("event_dates", []) if claim.details else []
    bad_dates = [str(x) for x in dates if claim.processing_date and str(x)[:10] > str(claim.processing_date)]
    if bad_dates:
        add_check("CHRONOLOGY","FAILED",f"Events occur after processing date: {', '.join(bad_dates)}")
        chronology_refs = [d.id for d in documents if d.extracted_fields and str(d.extracted_fields.get("event_date", ""))[:10] in bad_dates]
        finding("CHRONOLOGY_CONFLICT","medium","Document chronology needs review","One or more entered event dates occur after the processing date.",{"processing_date":str(claim.processing_date),"later_dates":bad_dates},chronology_refs,"Check the source dates, time zones, and whether the event was linked to the correct claim.")
    else: add_check("CHRONOLOGY","PASSED" if dates else "UNAVAILABLE","Entered event dates are not later than processing date." if dates else "No linked event dates entered.")
    # Explicitly only check material balance if complete documented fields are present.
    bal = claim.details.get("material_balance", {}) if claim.details else {}
    required = ["opening_kg","input_kg","output_kg","losses_kg","closing_kg"]
    if all(isinstance(bal.get(k), (int,float)) for k in required):
        residual = bal["opening_kg"] + bal["input_kg"] - bal["output_kg"] - bal["losses_kg"] - bal["closing_kg"]
        if abs(residual) > max(1.0, (bal["opening_kg"]+bal["input_kg"])*0.02):
            add_check("MATERIAL_BALANCE","FAILED",f"Material balance residual {residual:g} kg exceeds tolerance.")
            finding("MATERIAL_BALANCE_VARIANCE","medium","Material balance does not reconcile","Provided inventory and process values leave a residual outside the documented 2%/1 kg tolerance.",{"balance":bal,"residual_kg":residual},[],"Validate opening/closing stock and documented output/loss values against source records.")
        else: add_check("MATERIAL_BALANCE","PASSED",f"Material balance reconciles (residual {residual:g} kg).")
    else: add_check("MATERIAL_BALANCE","UNAVAILABLE","Opening/closing inventory, input, output, and losses were not all supplied; no inference made.")
    # Company/facility mismatch is only testable when source facility is manually extracted.
    extracted_names = [d.extracted_fields.get("facility") for d in documents if d.extracted_fields and d.extracted_fields.get("facility")]
    if extracted_names and any(n.strip().lower() != claim.facility.strip().lower() for n in extracted_names):
        add_check("FACILITY_IDENTITY","FAILED","An entered extracted facility name differs from the claim facility.")
        facility_refs = [d.id for d in documents if d.extracted_fields and d.extracted_fields.get("facility") and d.extracted_fields["facility"].strip().lower() != claim.facility.strip().lower()]
        finding("FACILITY_IDENTITY_MISMATCH","high","Facility name differs across claim and evidence","At least one user-confirmed extracted facility name is inconsistent with the claim record.",{"claim_facility":claim.facility,"document_facilities":extracted_names},facility_refs,"Review the referenced source records and confirm the legal facility identity.")
    else: add_check("FACILITY_IDENTITY","PASSED" if extracted_names else "UNAVAILABLE","Facility name matches entered document data." if extracted_names else "No sourced facility identity data available for comparison.")
    weights = {"low":8,"medium":18,"high":30}
    score = min(100, sum(weights.get(f["severity"],0) for f in findings))
    priority = "high" if score >= 60 else "medium" if score >= 25 else "low"
    failed = sum(c["outcome"] == "FAILED" for c in checks)
    core_unavailable = claimed is None or shipped is None or claim.permit_expiry is None
    status = "NEEDS_REVIEW" if failed else "INSUFFICIENT_EVIDENCE" if missing or core_unavailable else "NO_MAJOR_INCONSISTENCY_DETECTED"
    explanation = f"Score {score}/100: {len(findings)} review finding(s), weighted by severity (high 30, medium 18, low 8), capped at 100. This prioritizes human review; it is not a fraud determination."
    action = "Escalate high-severity discrepancies for human review and request missing or corrected source documents." if findings else "Retain source records and complete human review; automated checks did not identify a major inconsistency."
    return {"status":status,"priority_score":score,"priority":priority,"score_explanation":explanation,"checks":checks,"findings":findings,"missing_evidence":missing,"recommended_action":action}
