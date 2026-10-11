from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .config import settings


class ExtractedDocumentFields(BaseModel):
    """Nullable facts that Gemini can read from an invoice or shipment record."""

    model_config = ConfigDict(extra="forbid")

    document_id: str | None = Field(default=None, description="Invoice, manifest, or document number.")
    organization: str | None = None
    material_category: str | None = None
    quantity: float | None = Field(default=None, ge=0)
    unit: str | None = None
    document_date: date | None = None
    shipment_date: date | None = None
    shipment_reference: str | None = None
    invoice_reference: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class ExtractionResult(BaseModel):
    fields: ExtractedDocumentFields
    status: Literal["EXTRACTED", "NO_CONFIDENT_FIELDS", "CONFIGURATION_REQUIRED", "API_ERROR", "MALFORMED_RESPONSE"]
    message: str | None = None


class GeminiExtractionError(Exception):
    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _prompt(document_type: str) -> str:
    return f"""
Extract only facts that are explicitly readable in this {document_type} document.
Do not infer, calculate, normalize, or guess missing or uncertain values. Use null for
anything absent, illegible, or ambiguous. Return JSON matching the supplied schema.
Dates must be ISO YYYY-MM-DD when unambiguous. Quantity must be the document's stated
quantity and unit, not a converted quantity. This is evidence extraction, not a
verification decision.
""".strip()


def extract_document_fields(data: bytes, content_type: str, document_type: str) -> ExtractionResult:
    if not settings.gemini_api_key:
        return ExtractionResult(
            fields=ExtractedDocumentFields(),
            status="CONFIGURATION_REQUIRED",
            message="Gemini extraction is unavailable because GEMINI_API_KEY is not configured.",
        )

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        return ExtractionResult(
            fields=ExtractedDocumentFields(),
            status="API_ERROR",
            message="Gemini extraction is unavailable because the official SDK is not installed.",
        )

    try:
        client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=settings.gemini_timeout_seconds * 1000),
        )
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=[
                types.Part.from_bytes(data=data, mime_type=content_type),
                _prompt(document_type),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ExtractedDocumentFields,
                temperature=0,
            ),
        )
        raw = response.parsed
        if raw is None:
            raw = response.text
        fields = raw if isinstance(raw, ExtractedDocumentFields) else ExtractedDocumentFields.model_validate(raw)
    except ValidationError:
        return ExtractionResult(
            fields=ExtractedDocumentFields(),
            status="MALFORMED_RESPONSE",
            message="Gemini returned data that did not match the extraction schema.",
        )
    except Exception as exc:
        return ExtractionResult(
            fields=ExtractedDocumentFields(),
            status="API_ERROR",
            message=f"Gemini extraction failed ({type(exc).__name__}).",
        )

    if not fields.model_dump(exclude_none=True):
        return ExtractionResult(
            fields=fields,
            status="NO_CONFIDENT_FIELDS",
            message="Gemini found no sufficiently certain supported fields.",
        )
    return ExtractionResult(fields=fields, status="EXTRACTED")


def apply_extracted_fields(claim, documents) -> None:
    """Fill only absent claim inputs from explicit, typed document facts."""

    shipment_docs = [d for d in documents if d.document_type in {"shipment_manifest", "weighbridge_receipt"}]
    invoice_docs = [d for d in documents if d.document_type == "invoice"]

    def field(documents, name):
        for document in documents:
            value = (document.extracted_fields or {}).get(name)
            if value not in (None, ""):
                return value
        return None

    if claim.shipment_quantity is None:
        quantity = field(shipment_docs, "quantity")
        if quantity is not None:
            claim.shipment_quantity = quantity
            unit = field(shipment_docs, "unit")
            if unit and not claim.units:
                claim.units = unit
    if not claim.shipment_ids:
        references = [field(shipment_docs, name) for name in ("shipment_reference", "document_id")]
        claim.shipment_ids = [value for value in references if value]
    if not claim.invoice_ids:
        references = [field(invoice_docs, name) for name in ("invoice_reference", "document_id")]
        claim.invoice_ids = [value for value in references if value]

    dates = list((claim.details or {}).get("event_dates", []))
    for document in documents:
        fields = document.extracted_fields or {}
        for name in ("document_date", "shipment_date"):
            value = fields.get(name)
            if value and value not in dates:
                dates.append(value)
    if dates:
        details = dict(claim.details or {})
        details["event_dates"] = dates
        claim.details = details
