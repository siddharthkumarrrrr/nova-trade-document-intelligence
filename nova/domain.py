from __future__ import annotations

from pydantic import BaseModel, Field

FIELDS = (
    "consignee_name",
    "hs_code",
    "port_of_loading",
    "port_of_discharge",
    "incoterms",
    "description_of_goods",
    "gross_weight",
    "invoice_number",
)


class ExtractedField(BaseModel):
    value: str | None
    confidence: float = Field(ge=0, le=1)
    evidence: str
    page: int | None


class ExtractionResult(BaseModel):
    document_type: str
    fields: dict[str, ExtractedField]
    warnings: list[str]


EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "document_type": {"type": "string"},
        "fields": {
            "type": "object",
            "properties": {
                name: {
                    "type": "object",
                    "properties": {
                        "value": {"type": ["string", "null"]},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "evidence": {"type": "string"},
                        "page": {"type": ["integer", "null"]},
                    },
                    "required": ["value", "confidence", "evidence", "page"],
                    "additionalProperties": False,
                }
                for name in FIELDS
            },
            "required": list(FIELDS),
            "additionalProperties": False,
        },
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["document_type", "fields", "warnings"],
    "additionalProperties": False,
}

VALIDATION_AGENT_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "enum": list(FIELDS)},
                    "status": {"type": "string", "enum": ["match", "mismatch", "uncertain"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "reason": {"type": "string"},
                },
                "required": ["field", "status", "confidence", "reason"],
                "additionalProperties": False,
            },
            "minItems": len(FIELDS),
            "maxItems": len(FIELDS),
        }
    },
    "required": ["results"],
    "additionalProperties": False,
}

ROUTER_AGENT_SCHEMA = {
    "type": "object",
    "properties": {
        "outcome": {
            "type": "string",
            "enum": ["auto_approve", "human_review", "amendment_request"],
        },
        "reasoning": {"type": "string"},
        "draft_amendment": {"type": ["string", "null"]},
    },
    "required": ["outcome", "reasoning", "draft_amendment"],
    "additionalProperties": False,
}

