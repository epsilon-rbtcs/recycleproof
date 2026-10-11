"""Deterministic, clearly synthetic demo input records and their PDF source documents."""
from __future__ import annotations
from typing import Any

EXPECTED_TYPES = ["invoice", "shipment_manifest", "weighbridge_receipt", "recycler_permit", "recycling_certificate"]


def _doc(kind: str, filename: str, summary: str, fields: dict[str, Any], body: list[str]) -> dict[str, Any]:
    return {"document_type": kind, "filename": filename, "summary": summary,
            "extracted_fields": fields, "body": body}


SCENARIOS: list[dict[str, Any]] = [
    {
        "key": "consistent", "reference": "RP-DEMO-A-101", "title": "Consistent recycling claim",
        "material_category": "Circuit boards", "recycler": "Alder Circuit Recovery (fictional)",
        "facility": "North Loop Works (fictional)", "claimed_quantity": 82, "units": "tonnes",
        "shipment_quantity": 82, "shipment_ids": ["SYN-A-SHIP-101"], "invoice_ids": ["SYN-A-INV-101"],
        "certificate_ids": ["SYN-A-CERT-101"], "permit_expiry": "2027-12-31", "processing_date": "2026-10-02",
        "permit_categories": ["circuit boards"], "scenario_description": "A fictional claim whose quantities, permit dates, facility name, transaction references, and evidence types are internally consistent.",
        "details": {"event_dates": ["2026-10-02"], "material_balance": {"opening_kg": 0, "input_kg": 82000, "output_kg": 80000, "losses_kg": 2000, "closing_kg": 0}},
        "documents": [
            _doc("invoice", "case_a_invoice.pdf", "Invoice records 82 tonnes of circuit boards for the fictional North Loop Works facility.", {"facility": "North Loop Works (fictional)", "transaction_id": "SYN-A-INV-101", "quantity": 82, "units": "tonnes"}, ["FICTIONAL SAMPLE — NOT A REAL TRANSACTION", "Invoice SYN-A-INV-101", "Alder Circuit Recovery to North Loop Works", "Circuit boards received: 82 tonnes", "Transaction date: 2026-10-02"]),
            _doc("shipment_manifest", "case_a_shipment.pdf", "Shipment manifest SYN-A-SHIP-101 records the matching 82-tonne delivery.", {"facility": "North Loop Works (fictional)", "shipment_id": "SYN-A-SHIP-101", "quantity": 82, "units": "tonnes", "event_date": "2026-10-02"}, ["FICTIONAL SAMPLE — NOT A REAL TRANSACTION", "Shipment manifest SYN-A-SHIP-101", "Destination: North Loop Works", "Circuit boards: 82 tonnes", "Dispatch date: 2026-10-02"]),
            _doc("weighbridge_receipt", "case_a_weighbridge.pdf", "Weighbridge receipt records an 82-tonne net load.", {"facility": "North Loop Works (fictional)", "shipment_id": "SYN-A-SHIP-101", "quantity": 82, "units": "tonnes", "event_date": "2026-10-02"}, ["FICTIONAL SAMPLE — NOT A REAL RECEIPT", "Weighbridge ticket WB-A-101", "Facility: North Loop Works", "Net load: 82 tonnes", "Weigh date: 2026-10-02"]),
            _doc("recycler_permit", "case_a_permit.pdf", "Recorded permit covers circuit boards through 2027-12-31.", {"facility": "North Loop Works (fictional)", "permit_expiry": "2027-12-31", "permit_categories": ["circuit boards"]}, ["FICTIONAL SAMPLE — NOT AN AUTHORIZATION", "Recycler permit PERMIT-A-101", "Facility: North Loop Works", "Material category: circuit boards", "Recorded validity through: 2027-12-31"]),
            _doc("recycling_certificate", "case_a_certificate.pdf", "Certificate records 82 tonnes processed at the named fictional facility.", {"facility": "North Loop Works (fictional)", "certificate_id": "SYN-A-CERT-101", "quantity": 82, "units": "tonnes"}, ["FICTIONAL SAMPLE — NOT A REAL CERTIFICATE", "Processing certificate SYN-A-CERT-101", "Facility: North Loop Works", "Circuit boards processed: 82 tonnes", "Processing date: 2026-10-02"]),
        ],
    },
    {
        "key": "quantity_discrepancy", "reference": "RP-DEMO-B-204", "title": "Quantity discrepancy",
        "material_category": "Mixed e-waste", "recycler": "Juniper Materials Loop (fictional)",
        "facility": "Harborlight Recovery Hall (fictional)", "claimed_quantity": 500, "units": "tonnes",
        "shipment_quantity": 320, "shipment_ids": ["SYN-B-SHIP-204"], "invoice_ids": ["SYN-B-INV-204"],
        "certificate_ids": ["SYN-B-CERT-204"], "permit_expiry": "2027-08-31", "processing_date": "2026-10-05",
        "permit_categories": ["mixed e-waste"], "scenario_description": "The fictional claim reports 500 tonnes, while the linked shipment and weighbridge evidence total 320 tonnes. The 180-tonne gap has no additional inventory or shipment record in this case.",
        "details": {"event_dates": ["2026-10-04"]},
        "documents": [
            _doc("invoice", "case_b_invoice.pdf", "Fictional invoice states 500 tonnes of mixed e-waste claimed for processing.", {"facility": "Harborlight Recovery Hall (fictional)", "transaction_id": "SYN-B-INV-204", "quantity": 500, "units": "tonnes"}, ["FICTIONAL SAMPLE — NOT A REAL TRANSACTION", "Invoice SYN-B-INV-204", "Juniper Materials Loop to Harborlight Recovery Hall", "Claimed quantity: 500 tonnes", "Invoice date: 2026-10-04"]),
            _doc("shipment_manifest", "case_b_shipment.pdf", "Linked shipment manifest records 320 tonnes, 180 tonnes below the claim.", {"facility": "Harborlight Recovery Hall (fictional)", "shipment_id": "SYN-B-SHIP-204", "quantity": 320, "units": "tonnes", "event_date": "2026-10-04"}, ["FICTIONAL SAMPLE — NOT A REAL SHIPMENT", "Shipment manifest SYN-B-SHIP-204", "Destination: Harborlight Recovery Hall", "Mixed e-waste shipped: 320 tonnes", "Dispatch date: 2026-10-04", "No additional shipment is recorded in this scenario."]),
            _doc("weighbridge_receipt", "case_b_weighbridge.pdf", "Weighbridge receipt independently records 320 tonnes received.", {"facility": "Harborlight Recovery Hall (fictional)", "shipment_id": "SYN-B-SHIP-204", "quantity": 320, "units": "tonnes", "event_date": "2026-10-05"}, ["FICTIONAL SAMPLE — NOT A REAL RECEIPT", "Weighbridge ticket WB-B-204", "Facility: Harborlight Recovery Hall", "Net received weight: 320 tonnes", "Weigh date: 2026-10-05"]),
            _doc("recycler_permit", "case_b_permit.pdf", "Fictional facility permit is valid through 2027-08-31.", {"facility": "Harborlight Recovery Hall (fictional)", "permit_expiry": "2027-08-31", "permit_categories": ["mixed e-waste"]}, ["FICTIONAL SAMPLE — NOT AN AUTHORIZATION", "Recycler permit PERMIT-B-204", "Facility: Harborlight Recovery Hall", "Material category: mixed e-waste", "Recorded validity through: 2027-08-31"]),
            _doc("recycling_certificate", "case_b_certificate.pdf", "Certificate reflects the 500-tonne claim and can be reconciled against the shipment evidence.", {"facility": "Harborlight Recovery Hall (fictional)", "certificate_id": "SYN-B-CERT-204", "quantity": 500, "units": "tonnes"}, ["FICTIONAL SAMPLE — NOT A REAL CERTIFICATE", "Processing certificate SYN-B-CERT-204", "Facility: Harborlight Recovery Hall", "Reported quantity: 500 tonnes", "Processing date: 2026-10-05"]),
        ],
    },
    {
        "key": "duplicate_shipment", "reference": "RP-DEMO-C-317", "title": "Duplicate shipment reference",
        "material_category": "Small appliances", "recycler": "Cedarline Recovery Studio (fictional)",
        "facility": "Cedarline East Works (fictional)", "claimed_quantity": 76, "units": "tonnes",
        "shipment_quantity": 76, "shipment_ids": ["SYN-C-DUP-317", "SYN-C-DUP-317"], "invoice_ids": ["SYN-C-INV-317"],
        "certificate_ids": ["SYN-C-CERT-317"], "permit_expiry": "2027-06-30", "processing_date": "2026-10-06",
        "permit_categories": ["small appliances"], "scenario_description": "Two separate fictional manifest records carry the same shipment reference. The verifier should identify both documents for a reviewer to reconcile.",
        "details": {"event_dates": ["2026-10-06"]},
        "documents": [
            _doc("invoice", "case_c_invoice.pdf", "Invoice for 76 tonnes of small appliances.", {"facility": "Cedarline East Works (fictional)", "transaction_id": "SYN-C-INV-317", "quantity": 76, "units": "tonnes"}, ["FICTIONAL SAMPLE — NOT A REAL TRANSACTION", "Invoice SYN-C-INV-317", "Cedarline Recovery Studio", "Small appliances: 76 tonnes"]),
            _doc("shipment_manifest", "case_c_manifest_1.pdf", "First delivery record uses shipment reference SYN-C-DUP-317.", {"facility": "Cedarline East Works (fictional)", "shipment_id": "SYN-C-DUP-317", "quantity": 38, "units": "tonnes", "event_date": "2026-10-06"}, ["FICTIONAL SAMPLE — NOT A REAL SHIPMENT", "Delivery record 1 of 2", "Shipment reference: SYN-C-DUP-317", "Small appliances: 38 tonnes", "Delivery date: 2026-10-06"]),
            _doc("shipment_manifest", "case_c_manifest_2.pdf", "Second separate delivery record repeats shipment reference SYN-C-DUP-317.", {"facility": "Cedarline East Works (fictional)", "shipment_id": "SYN-C-DUP-317", "quantity": 38, "units": "tonnes", "event_date": "2026-10-06"}, ["FICTIONAL SAMPLE — NOT A REAL SHIPMENT", "Delivery record 2 of 2", "Shipment reference: SYN-C-DUP-317", "Small appliances: 38 tonnes", "Delivery date: 2026-10-06"]),
            _doc("weighbridge_receipt", "case_c_weighbridge.pdf", "Weighbridge receipt records 76 tonnes across the two fictional deliveries.", {"facility": "Cedarline East Works (fictional)", "quantity": 76, "units": "tonnes", "event_date": "2026-10-06"}, ["FICTIONAL SAMPLE — NOT A REAL RECEIPT", "Weighbridge ticket WB-C-317", "Net weight: 76 tonnes", "Weigh date: 2026-10-06"]),
            _doc("recycler_permit", "case_c_permit.pdf", "Fictional facility permit is current for small appliances.", {"facility": "Cedarline East Works (fictional)", "permit_expiry": "2027-06-30", "permit_categories": ["small appliances"]}, ["FICTIONAL SAMPLE — NOT AN AUTHORIZATION", "Permit PERMIT-C-317", "Facility: Cedarline East Works", "Small appliances; valid through 2027-06-30"]),
            _doc("recycling_certificate", "case_c_certificate.pdf", "Certificate records 76 tonnes processed.", {"facility": "Cedarline East Works (fictional)", "certificate_id": "SYN-C-CERT-317", "quantity": 76, "units": "tonnes"}, ["FICTIONAL SAMPLE — NOT A REAL CERTIFICATE", "Certificate SYN-C-CERT-317", "Quantity processed: 76 tonnes"]),
        ],
    },
    {
        "key": "expired_permit", "reference": "RP-DEMO-D-422", "title": "Expired recycler permit",
        "material_category": "Lead-acid batteries", "recycler": "Fableton Battery Reclaim (fictional)",
        "facility": "Fableton West Yard (fictional)", "claimed_quantity": 44, "units": "tonnes",
        "shipment_quantity": 44, "shipment_ids": ["SYN-D-SHIP-422"], "invoice_ids": ["SYN-D-INV-422"],
        "certificate_ids": ["SYN-D-CERT-422"], "permit_expiry": "2025-12-31", "processing_date": "2026-07-15",
        "permit_categories": ["lead-acid batteries"], "scenario_description": "The recorded fictional recycler permit expired on 2025-12-31, before the claim's 2026-07-15 processing date.",
        "details": {"event_dates": ["2026-07-15"]},
        "documents": [
            _doc("invoice", "case_d_invoice.pdf", "Invoice for 44 tonnes dated 2026-07-14.", {"facility": "Fableton West Yard (fictional)", "transaction_id": "SYN-D-INV-422", "quantity": 44, "units": "tonnes"}, ["FICTIONAL SAMPLE — NOT A REAL TRANSACTION", "Invoice SYN-D-INV-422", "Lead-acid batteries: 44 tonnes", "Invoice date: 2026-07-14"]),
            _doc("shipment_manifest", "case_d_shipment.pdf", "Shipment manifest for 44 tonnes, delivered 2026-07-15.", {"facility": "Fableton West Yard (fictional)", "shipment_id": "SYN-D-SHIP-422", "quantity": 44, "units": "tonnes", "event_date": "2026-07-15"}, ["FICTIONAL SAMPLE — NOT A REAL SHIPMENT", "Manifest SYN-D-SHIP-422", "Destination: Fableton West Yard", "Quantity: 44 tonnes", "Date: 2026-07-15"]),
            _doc("weighbridge_receipt", "case_d_weighbridge.pdf", "Weighbridge receipt for 44 tonnes dated 2026-07-15.", {"facility": "Fableton West Yard (fictional)", "shipment_id": "SYN-D-SHIP-422", "quantity": 44, "units": "tonnes", "event_date": "2026-07-15"}, ["FICTIONAL SAMPLE — NOT A REAL RECEIPT", "Ticket WB-D-422", "Net weight: 44 tonnes", "Date: 2026-07-15"]),
            _doc("recycler_permit", "case_d_permit.pdf", "Permit ended on 2025-12-31, before the claim processing date.", {"facility": "Fableton West Yard (fictional)", "permit_expiry": "2025-12-31", "permit_categories": ["lead-acid batteries"]}, ["FICTIONAL SAMPLE — NOT AN AUTHORIZATION", "Permit PERMIT-D-422", "Facility: Fableton West Yard", "Lead-acid batteries", "Validity ended: 2025-12-31"]),
            _doc("recycling_certificate", "case_d_certificate.pdf", "Certificate for 44 tonnes dated 2026-07-15.", {"facility": "Fableton West Yard (fictional)", "certificate_id": "SYN-D-CERT-422", "quantity": 44, "units": "tonnes"}, ["FICTIONAL SAMPLE — NOT A REAL CERTIFICATE", "Certificate SYN-D-CERT-422", "Quantity: 44 tonnes", "Processing date: 2026-07-15"]),
        ],
    },
    {
        "key": "identity_chronology", "reference": "RP-DEMO-E-509", "title": "Identity and chronology mismatch",
        "material_category": "Small appliances", "recycler": "Morrowline Circular Exchange (fictional)",
        "facility": "Morrowline North Plant (fictional)", "claimed_quantity": 25, "units": "tonnes",
        "shipment_quantity": 25, "shipment_ids": ["SYN-E-SHIP-509"], "invoice_ids": ["SYN-E-INV-509"],
        "certificate_ids": ["SYN-E-CERT-509"], "permit_expiry": "2027-09-30", "processing_date": "2026-07-20",
        "permit_categories": ["small appliances"], "scenario_description": "Fictional source records name a different facility and include a transaction date after the claimed processing date.",
        "details": {"event_dates": ["2026-08-03"]},
        "documents": [
            _doc("invoice", "case_e_invoice.pdf", "Invoice identifies Morrowline South Annex, not the claimed North Plant.", {"facility": "Morrowline South Annex (fictional)", "transaction_id": "SYN-E-INV-509", "quantity": 25, "units": "tonnes", "event_date": "2026-08-03"}, ["FICTIONAL SAMPLE — NOT A REAL TRANSACTION", "Invoice SYN-E-INV-509", "Facility: Morrowline South Annex", "Small appliances: 25 tonnes", "Invoice date: 2026-08-03"]),
            _doc("shipment_manifest", "case_e_shipment.pdf", "Shipment manifest names South Annex and is dated after claimed processing.", {"facility": "Morrowline South Annex (fictional)", "shipment_id": "SYN-E-SHIP-509", "quantity": 25, "units": "tonnes", "event_date": "2026-08-03"}, ["FICTIONAL SAMPLE — NOT A REAL SHIPMENT", "Manifest SYN-E-SHIP-509", "Destination: Morrowline South Annex", "Quantity: 25 tonnes", "Dispatch date: 2026-08-03"]),
            _doc("weighbridge_receipt", "case_e_weighbridge.pdf", "Weighbridge receipt names South Annex and is dated 2026-08-03.", {"facility": "Morrowline South Annex (fictional)", "quantity": 25, "units": "tonnes", "event_date": "2026-08-03"}, ["FICTIONAL SAMPLE — NOT A REAL RECEIPT", "Ticket WB-E-509", "Facility: Morrowline South Annex", "Net weight: 25 tonnes", "Date: 2026-08-03"]),
            _doc("recycler_permit", "case_e_permit.pdf", "Permit names the North Plant and is valid through 2027-09-30.", {"facility": "Morrowline North Plant (fictional)", "permit_expiry": "2027-09-30", "permit_categories": ["small appliances"]}, ["FICTIONAL SAMPLE — NOT AN AUTHORIZATION", "Permit PERMIT-E-509", "Facility: Morrowline North Plant", "Small appliances", "Valid through: 2027-09-30"]),
            _doc("recycling_certificate", "case_e_certificate.pdf", "Certificate names South Annex, records 25 tonnes, and is dated after processing.", {"facility": "Morrowline South Annex (fictional)", "certificate_id": "SYN-E-CERT-509", "quantity": 25, "units": "tonnes", "event_date": "2026-08-03"}, ["FICTIONAL SAMPLE — NOT A REAL CERTIFICATE", "Certificate SYN-E-CERT-509", "Facility: Morrowline South Annex", "Quantity: 25 tonnes", "Certificate date: 2026-08-03"]),
        ],
    },
]


def pdf_bytes(lines: list[str]) -> bytes:
    """Produce a tiny valid text PDF using only the Python standard library."""
    def escape(text: str) -> str:
        ascii_text = text.encode("ascii", "replace").decode("ascii")
        return ascii_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content_lines = ["BT", "/F1 11 Tf", "50 748 Td"]
    for i, line in enumerate(lines[:24]):
        if i:
            content_lines.append("0 -24 Td")
        content_lines.append(f"({escape(line)[:190]}) Tj")
    content_lines.append("ET")
    stream = ("\n".join(content_lines) + "\n").encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"endstream",
    ]
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode("ascii")); out.extend(obj); out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    out.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    return bytes(out)


def document_asset(scenario: dict[str, Any], document: dict[str, Any]) -> tuple[str, bytes]:
    key = f"demo-assets/seed/{scenario['key']}/{document['filename']}"
    body = ["RECYCLEPROOF — DEMO MODE / SYNTHETIC DATA", f"Scenario: {scenario['reference']} — {scenario['title']}", *document["body"]]
    return key, pdf_bytes(body)


def all_seed_assets() -> list[tuple[str, bytes]]:
    return [document_asset(scenario, doc) for scenario in SCENARIOS for doc in scenario["documents"]]
