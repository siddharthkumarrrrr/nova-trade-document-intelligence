from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv

from nova.domain import (
    EXTRACTION_SCHEMA,
    FIELDS,
    ROUTER_AGENT_SCHEMA,
    VALIDATION_AGENT_SCHEMA,
    ExtractionResult,
)
from nova.settings import SETTINGS
from nova.http_transport import parse_multipart_form

ROOT = SETTINGS.root
load_dotenv(SETTINGS.env_path)
DB_PATH = SETTINGS.database_path
RULES_PATH = SETTINGS.rules_path
WEB_DIR = SETTINGS.web_path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute(
        """CREATE TABLE IF NOT EXISTS runs (
        id TEXT PRIMARY KEY, created_at TEXT NOT NULL, filename TEXT NOT NULL,
        status TEXT NOT NULL, mode TEXT NOT NULL, stage TEXT NOT NULL,
        extracted_json TEXT, validation_json TEXT, decision_json TEXT,
        error TEXT, content_hash TEXT NOT NULL)"""
    )
    db.commit()
    return db


def save_run(run: dict) -> None:
    with connect() as db:
        db.execute(
            """INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET status=excluded.status,
            stage=excluded.stage, extracted_json=excluded.extracted_json,
            validation_json=excluded.validation_json,
            decision_json=excluded.decision_json, error=excluded.error""",
            (
                run["id"], run["created_at"], run["filename"], run["status"],
                run["mode"], run["stage"], json.dumps(run.get("extracted")),
                json.dumps(run.get("validation")), json.dumps(run.get("decision")),
                run.get("error"), run["content_hash"],
            ),
        )


def field(value, confidence, evidence, page=1):
    return {"value": value, "confidence": confidence, "evidence": evidence, "page": page}


def demo_extract(filename: str) -> dict:
    messy = any(x in filename.lower() for x in ("messy", "scan", "low"))
    if messy:
        return {
            "document_type": "commercial_invoice",
            "fields": {
                "consignee_name": field("Acme Retail India Pvt Ltd", .93, "Consignee: Acme Retail India Pvt Ltd"),
                "hs_code": field("8471?0", .54, "HS: 8471?0"),
                "port_of_loading": field("Shanghai, China", .89, "Port of Loading: Shanghai"),
                "port_of_discharge": field("Nhava Sheva, India", .91, "Discharge: Nhava Sheva"),
                "incoterms": field(None, .18, "Incoterm: [illegible]"),
                "description_of_goods": field("Laptop computer accessories", .86, "Goods: laptop computer accessories"),
                "gross_weight": field("1,275 KG", .92, "Gross Wt: 1275 KG"),
                "invoice_number": field("INV-2026-0714", .96, "Invoice No: INV-2026-0714"),
            },
            "warnings": ["Low-quality scan: HS code character unclear", "Incoterm not legible"],
        }
    return {
        "document_type": "commercial_invoice",
        "fields": {
            "consignee_name": field("Acme Retail India Pvt Ltd", .99, "Consignee: ACME RETAIL INDIA PVT LTD"),
            "hs_code": field("847130", .98, "HS Code: 847130"),
            "port_of_loading": field("Shanghai, China", .98, "Port of Loading: Shanghai, China"),
            "port_of_discharge": field("Nhava Sheva, India", .99, "Port of Discharge: Nhava Sheva, India"),
            "incoterms": field("CIF", .99, "Incoterms: CIF"),
            "description_of_goods": field("Laptop computer accessories", .97, "Description: Laptop computer accessories"),
            "gross_weight": field("1,250 KG", .98, "Gross Weight: 1,250 KG"),
            "invoice_number": field("INV-2026-0713", .99, "Invoice Number: INV-2026-0713"),
        },
        "warnings": [],
    }


def groq_extract(filename: str, content: bytes, content_type: str) -> dict:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY is not set. Select Demo mode or provide a fresh Groq key.")
    model = os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b")
    images = []
    if content_type == "application/pdf":
        try:
            import pypdfium2 as pdfium
        except ImportError as exc:
            raise RuntimeError("PDF processing requires pypdfium2. Run: pip install pypdfium2 Pillow") from exc
        document = pdfium.PdfDocument(content)
        if len(document) > 5:
            raise ValueError("Groq vision mode supports a maximum of 5 rendered PDF pages per run.")
        from io import BytesIO
        for page in document:
            rendered = page.render(scale=1.5).to_pil()
            buffer = BytesIO()
            rendered.convert("RGB").save(buffer, format="JPEG", quality=88)
            encoded = base64.b64encode(buffer.getvalue()).decode()
            images.append({"type": "input_image", "image_url": f"data:image/jpeg;base64,{encoded}", "detail": "high"})
    else:
        encoded = base64.b64encode(content).decode()
        images.append({"type": "input_image", "image_url": f"data:{content_type};base64,{encoded}", "detail": "high"})
    prompt = """You are an evidence-bound trade-document extractor. Return JSON only.
Extract exactly these fields: consignee_name, hs_code, port_of_loading,
port_of_discharge, incoterms, description_of_goods, gross_weight, invoice_number.
For each return value (string or null), confidence (0..1), evidence (a short
verbatim snippet visible in the document), and page (integer or null). Never infer
missing text. Use null and low confidence when absent or illegible. Also return
document_type and warnings. Schema:
{"document_type":"...", "fields":{"consignee_name":{"value":null,
"confidence":0,"evidence":"","page":null}}, "warnings":[]}"""
    payload = json.dumps({
        "model": model,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}, *images]}],
        "text": {"format": {"type": "json_object"}},
    }).encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/responses", data=payload,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Groq-Beta": "inference-metrics"},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as res:
            body = json.load(res)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Model request failed ({exc.code}): {exc.read().decode()[:300]}") from exc
    text = body.get("output_text")
    if not text:
        for item in body.get("output", []):
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    text = part.get("text")
    result = json.loads(text)
    validate_extraction_shape(result)
    return result


def gemini_extract(filename: str, content: bytes, content_type: str) -> dict:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set. Select Demo/Groq mode or provide a Google AI Studio key.")
    model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    prompt = """Extract the required trade-document fields. Never infer missing
text. Every non-null value must have a short verbatim evidence snippet and page.
Use null and low confidence for absent or illegible fields."""
    media_type = "document" if content_type == "application/pdf" else "image"
    payload = json.dumps({
        "model": model,
        "input": [
            {"type": media_type, "data": base64.b64encode(content).decode(), "mime_type": content_type},
            {"type": "text", "text": prompt},
        ],
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": EXTRACTION_SCHEMA,
        },
    }).encode()
    req = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        data=payload,
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as res:
            body = json.load(res)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Gemini request failed ({exc.code}): {exc.read().decode()[:300]}") from exc
    text = body.get("output_text")
    if not text:
        for step in reversed(body.get("steps", [])):
            for part in step.get("content", []):
                if part.get("text"):
                    text = part["text"]
                    break
            if text:
                break
    if not text:
        raise RuntimeError("Gemini returned no structured extraction text.")
    result = json.loads(text)
    validate_extraction_shape(result)
    return result


def gemini_structured_agent(prompt: str, schema: dict) -> dict:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is required for real Gemini agents.")
    payload = json.dumps({
        "model": os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
        "input": [{"type": "text", "text": prompt}],
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": schema,
        },
    }).encode()
    req = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        data=payload,
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            body = json.load(res)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Gemini agent failed ({exc.code}): {exc.read().decode()[:300]}") from exc
    text = body.get("output_text")
    if not text:
        for step in reversed(body.get("steps", [])):
            for part in step.get("content", []):
                if part.get("text"):
                    text = part["text"]
                    break
            if text:
                break
    if not text:
        raise RuntimeError("Gemini agent returned no structured output.")
    return json.loads(text)


def groq_structured_agent(prompt: str, schema: dict) -> dict:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY is required for real Groq agents.")
    payload = json.dumps({
        "model": os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b"),
        "input": prompt + "\nReturn JSON only. Required JSON Schema:\n" + json.dumps(schema),
        "text": {"format": {"type": "json_object"}},
    }).encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/responses",
        data=payload,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            body = json.load(res)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Groq agent failed ({exc.code}): {exc.read().decode()[:300]}") from exc
    text = body.get("output_text")
    if not text:
        for item in body.get("output", []):
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    text = part.get("text")
    if not text:
        raise RuntimeError("Groq agent returned no structured output.")
    return json.loads(text)


def call_structured_agent(mode: str, prompt: str, schema: dict) -> dict:
    if mode == "gemini":
        return gemini_structured_agent(prompt, schema)
    if mode == "groq":
        return groq_structured_agent(prompt, schema)
    raise ValueError(f"Mode {mode} does not use a live LLM agent.")


def extract_document(filename: str, content: bytes, content_type: str, mode: str) -> dict:
    if mode == "demo":
        return demo_extract(filename)
    if mode == "gemini":
        return gemini_extract(filename, content, content_type)
    if mode == "groq":
        return groq_extract(filename, content, content_type)
    raise ValueError(f"Unsupported extraction mode: {mode}")


def validate_extraction_shape(result: dict) -> None:
    ExtractionResult.model_validate(result)
    fields = result.get("fields", {})
    for name in FIELDS:
        item = fields.get(name)
        if not isinstance(item, dict):
            raise ValueError(f"Extractor omitted structured field: {name}")
        score = item.get("confidence")
        if not isinstance(score, (int, float)) or not 0 <= score <= 1:
            raise ValueError(f"Invalid confidence for {name}")
        if item.get("value") and not item.get("evidence"):
            item["confidence"] = min(score, .49)
            result.setdefault("warnings", []).append(f"{name}: value lacked source evidence")


def normalize(value) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def validate(extracted: dict, rules: dict) -> dict:
    results, counts = [], {"match": 0, "mismatch": 0, "uncertain": 0}
    for name in FIELDS:
        item = extracted["fields"][name]
        value, confidence = item.get("value"), float(item.get("confidence", 0))
        rule = rules["fields"].get(name, {})
        expected = rule.get("expected")
        required = rule.get("required", False)
        threshold = rule.get("min_confidence", rules["default_min_confidence"])
        if not value or confidence < threshold:
            status = "uncertain"
            reason = "Missing value" if not value else f"Confidence {confidence:.0%} is below {threshold:.0%}"
        elif expected is not None and normalize(value) != normalize(expected):
            status, reason = "mismatch", "Extracted value does not equal the customer rule"
        elif required or expected is not None:
            status, reason = "match", "Value is present, evidence-backed, and satisfies the rule"
        else:
            status, reason = "match", "No restrictive customer rule; value is evidence-backed"
        counts[status] += 1
        results.append({
            "field": name, "status": status, "found": value, "expected": expected,
            "confidence": confidence, "evidence": item.get("evidence"),
            "page": item.get("page"), "reason": reason,
        })
    return {"customer": rules["customer"], "results": results, "summary": counts}


def route(validation: dict) -> dict:
    mismatches = [r for r in validation["results"] if r["status"] == "mismatch"]
    uncertain = [r for r in validation["results"] if r["status"] == "uncertain"]
    if mismatches:
        outcome = "amendment_request"
        reasoning = f"{len(mismatches)} confirmed mismatch(es) require supplier correction. No message was sent."
    elif uncertain:
        outcome = "human_review"
        reasoning = f"{len(uncertain)} field(s) are uncertain; silent approval is blocked."
    else:
        outcome = "auto_approve"
        reasoning = "All required fields match with sufficient confidence; the verified result can be stored."
    lines = []
    for r in mismatches + uncertain:
        lines.append(f"- {r['field'].replace('_', ' ').title()}: found {r['found'] or 'not readable'}; expected {r['expected'] or 'a clear, valid value'} ({r['reason']}).")
    draft = None
    if outcome != "auto_approve":
        draft = "Subject: Amendments required for shipment documents\n\nHello,\n\nPlease review the following items:\n" + "\n".join(lines) + "\n\nPlease amend and resend the documents.\n\nRegards,\nCG Validation Team"
    return {"outcome": outcome, "reasoning": reasoning, "draft_amendment": draft}


def validator_agent(extracted: dict, rules: dict, mode: str) -> dict:
    deterministic = validate(extracted, rules)
    if mode == "demo":
        return {
            **deterministic,
            "agent": {"provider": "demo", "guard_disagreements": 0},
        }
    # Exact matches, missing evidence, and low-confidence fields are already
    # decided safely by local rules. Spend tokens only where a textual mismatch
    # may actually be an alias, abbreviation, or equivalent description.
    semantic_fields = {
        "consignee_name", "port_of_loading", "port_of_discharge",
        "description_of_goods",
    }
    ambiguous = [
        item for item in deterministic["results"]
        if item["status"] == "mismatch" and item["field"] in semantic_fields
    ]
    if not ambiguous:
        return {
            **deterministic,
            "agent": {
                "provider": "deterministic",
                "llm_called": False,
                "guard_disagreements": 0,
                "reason": "No semantic ambiguity required an LLM judgment.",
            },
        }
    prompt = """You are the Validator Agent for trade documents. Compare every
extracted field with the customer rules. Consider harmless formatting,
abbreviations, ports, and unit equivalence, but never invent a value. Missing or
low-confidence evidence must be uncertain. Return exactly one result for each
required field using the supplied schema.

EXTRACTION:
""" + json.dumps(extracted) + "\nCUSTOMER RULES:\n" + json.dumps(rules)
    proposal = call_structured_agent(mode, prompt, VALIDATION_AGENT_SCHEMA)
    proposed_by_field = {item["field"]: item for item in proposal.get("results", [])}
    guarded_results, disagreements = [], 0
    for baseline in deterministic["results"]:
        proposed = proposed_by_field.get(baseline["field"])
        if not proposed:
            raise ValueError(f"Validator Agent omitted {baseline['field']}")
        proposed_status = proposed.get("status")
        guarded_status = baseline["status"]
        reason = proposed.get("reason", baseline["reason"])
        if baseline["status"] == "uncertain":
            guarded_status = "uncertain"
            if proposed_status != "uncertain":
                disagreements += 1
                reason = "Guard blocked the model from overriding missing or low-confidence evidence."
        elif proposed_status != baseline["status"]:
            disagreements += 1
            guarded_status = "uncertain"
            reason = (
                f"Rule engine returned {baseline['status']} while the Validator Agent "
                f"returned {proposed_status}; disagreement requires human review."
            )
        guarded_results.append({
            **baseline,
            "status": guarded_status,
            "validation_confidence": min(
                float(proposed.get("confidence", 0)),
                float(baseline["confidence"]),
            ),
            "reason": reason,
            "deterministic_status": baseline["status"],
            "agent_status": proposed_status,
        })
    summary = {"match": 0, "mismatch": 0, "uncertain": 0}
    for item in guarded_results:
        summary[item["status"]] += 1
    return {
        "customer": rules["customer"],
        "results": guarded_results,
        "summary": summary,
        "agent": {
            "provider": mode,
            "llm_called": True,
            "guard_disagreements": disagreements,
            "semantic_fields_reviewed": [item["field"] for item in ambiguous],
        },
    }


def router_agent(validation: dict, mode: str) -> dict:
    guarded_policy = route(validation)
    if mode == "demo":
        return {
            **guarded_policy,
            "agent": {"provider": "demo", "proposed_outcome": guarded_policy["outcome"], "guard_applied": False},
        }
    # A clean document has no prose to generate and the deterministic policy is
    # authoritative, so an LLM call would add cost without changing the result.
    if guarded_policy["outcome"] == "auto_approve":
        return {
            **guarded_policy,
            "agent": {
                "provider": "deterministic",
                "llm_called": False,
                "proposed_outcome": guarded_policy["outcome"],
                "guard_applied": False,
                "reason": "Clean auto-approval does not require generated text.",
            },
        }
    prompt = """You are the Router / Decision Agent. Read the complete guarded
validation result and propose exactly one outcome: auto_approve, human_review,
or amendment_request. Explain the operational reason. If amendments are needed,
write one concise editable supplier email listing every discrepancy. Never claim
that an email was sent. Return JSON matching the supplied schema.

VALIDATION:
""" + json.dumps(validation)
    proposal = call_structured_agent(mode, prompt, ROUTER_AGENT_SCHEMA)
    proposed_outcome = proposal.get("outcome")
    final_outcome = guarded_policy["outcome"]
    guard_applied = proposed_outcome != final_outcome
    if guard_applied:
        reasoning = (
            f"Decision guard overrode model proposal '{proposed_outcome}'. "
            + guarded_policy["reasoning"]
        )
        draft = guarded_policy["draft_amendment"]
    else:
        reasoning = proposal.get("reasoning") or guarded_policy["reasoning"]
        draft = proposal.get("draft_amendment") or guarded_policy["draft_amendment"]
    return {
        "outcome": final_outcome,
        "reasoning": reasoning,
        "draft_amendment": draft,
        "agent": {
            "provider": mode,
            "llm_called": True,
            "proposed_outcome": proposed_outcome,
            "guard_applied": guard_applied,
        },
    }


class PipelineState(TypedDict, total=False):
    run: dict
    document_path: str
    content_type: str
    extracted: dict
    validation: dict
    decision: dict


_pipeline_graph = None
_checkpoint_connection = None


def extractor_node(state: PipelineState) -> dict:
    run = dict(state["run"])
    attempts = 1 if run["mode"] == "demo" else 2
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            extracted = extract_document(
                run["filename"],
                Path(state["document_path"]).read_bytes(),
                state["content_type"],
                run["mode"],
            )
            break
        except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt == attempts:
                raise
    run["extraction_attempts"] = attempt
    validate_extraction_shape(extracted)
    run.update({"extracted": extracted, "stage": "extracted"})
    save_run(run)
    return {"run": run, "extracted": extracted}


def validator_node(state: PipelineState) -> dict:
    run = dict(state["run"])
    rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    validation = validator_agent(state["extracted"], rules, run["mode"])
    run.update({"validation": validation, "stage": "validated"})
    save_run(run)
    return {"run": run, "validation": validation}


def router_node(state: PipelineState) -> dict:
    run = dict(state["run"])
    decision = router_agent(state["validation"], run["mode"])
    run.update({
        "decision": decision,
        "stage": "routed",
        "status": "completed",
    })
    save_run(run)
    return {"run": run, "decision": decision}


def get_pipeline_graph():
    global _pipeline_graph, _checkpoint_connection
    if _pipeline_graph is not None:
        return _pipeline_graph
    try:
        from langgraph.graph import END, START, StateGraph
        from langgraph.checkpoint.sqlite import SqliteSaver
    except ImportError as exc:
        raise RuntimeError("LangGraph dependencies are missing. Run: pip install -r requirements.txt") from exc
    checkpoint_path = SETTINGS.checkpoint_path
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    _checkpoint_connection = sqlite3.connect(checkpoint_path, check_same_thread=False)
    builder = StateGraph(PipelineState)
    builder.add_node("extractor_agent", extractor_node)
    builder.add_node("validator_agent", validator_node)
    builder.add_node("router_agent", router_node)
    builder.add_edge(START, "extractor_agent")
    builder.add_edge("extractor_agent", "validator_agent")
    builder.add_edge("validator_agent", "router_agent")
    builder.add_edge("router_agent", END)
    _pipeline_graph = builder.compile(checkpointer=SqliteSaver(_checkpoint_connection))
    return _pipeline_graph


def process(filename: str, content: bytes, content_type: str, mode: str) -> dict:
    content_hash = hashlib.sha256(content).hexdigest()
    upload_dir = SETTINGS.upload_path
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix.lower() or mimetypes.guess_extension(content_type) or ".bin"
    document_path = upload_dir / f"{content_hash}{suffix}"
    if not document_path.exists():
        document_path.write_bytes(content)
    run = {
        "id": str(uuid.uuid4()), "created_at": utc_now(), "filename": filename,
        "status": "running", "mode": mode, "stage": "received", "error": None,
        "content_hash": content_hash,
    }
    save_run(run)
    try:
        graph = get_pipeline_graph()
        final_state = graph.invoke(
            {
                "run": run,
                "document_path": str(document_path),
                "content_type": content_type,
            },
            config={"configurable": {"thread_id": run["id"]}},
        )
        return final_state["run"]
    except Exception as exc:
        run["status"] = "failed"; run["stage"] = "failed"; run["error"] = str(exc)
        save_run(run)
        raise


def query(question: str) -> dict:
    q = question.lower().strip()
    with connect() as db:
        if "average" in q and "confidence" in q:
            rows = db.execute("SELECT extracted_json FROM runs WHERE status='completed'").fetchall()
            scores = [f["confidence"] for row in rows for f in json.loads(row["extracted_json"])["fields"].values()]
            answer = f"Average extraction confidence is {sum(scores)/len(scores):.1%} across {len(scores)} fields." if scores else "No completed runs yet."
        elif "pending" in q or "human review" in q:
            rows = db.execute("SELECT id, created_at, filename, decision_json FROM runs WHERE status='completed' ORDER BY created_at DESC").fetchall()
            items = [dict(r) for r in rows if json.loads(r["decision_json"])["outcome"] == "human_review"]
            answer = f"{len(items)} shipment(s) are pending human review: " + ", ".join(x["filename"] for x in items[:10])
        elif "flagged" in q:
            since = datetime.now(timezone.utc).timestamp() - 7 * 86400
            rows = db.execute("SELECT created_at, decision_json FROM runs WHERE status='completed'").fetchall()
            count = sum(1 for r in rows if datetime.fromisoformat(r["created_at"]).timestamp() >= since and json.loads(r["decision_json"])["outcome"] != "auto_approve")
            answer = f"{count} shipment(s) were flagged in the last 7 days."
        elif "auto" in q and "approve" in q:
            rows = db.execute("SELECT decision_json FROM runs WHERE status='completed'").fetchall()
            count = sum(json.loads(r["decision_json"])["outcome"] == "auto_approve" for r in rows)
            answer = f"{count} shipment(s) have been auto-approved."
        else:
            rows = db.execute("SELECT id, created_at, filename, status, stage, decision_json FROM runs ORDER BY created_at DESC LIMIT 10").fetchall()
            items = [{**dict(r), "decision": json.loads(r["decision_json"]) if r["decision_json"] else None, "decision_json": None} for r in rows]
            answer = f"Showing {len(items)} most recent run(s)."
    return {"question": question, "answer": answer, "grounding": "SQLite read-only query", "rows": items if "items" in locals() else []}


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        clean = path.split("?", 1)[0].lstrip("/") or "index.html"
        return str(WEB_DIR / clean)

    def send_json(self, status: int, data: dict):
        payload = json.dumps(data).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload)

    def do_GET(self):
        if self.path.startswith("/api/runs"):
            with connect() as db:
                rows = db.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT 25").fetchall()
            out = []
            for row in rows:
                item = dict(row)
                for key in ("extracted_json", "validation_json", "decision_json"):
                    item[key.removesuffix("_json")] = json.loads(item.pop(key)) if item[key] else None
                out.append(item)
            return self.send_json(200, {"runs": out})
        return super().do_GET()

    def do_POST(self):
        try:
            if self.path == "/api/process":
                length = int(self.headers.get("Content-Length", 0))
                if length <= 0 or length > SETTINGS.max_upload_bytes + 1024 * 1024:
                    raise ValueError("Document must be between 1 byte and 20 MB.")
                files, fields = parse_multipart_form(
                    self.rfile.read(length),
                    self.headers.get("Content-Type", ""),
                )
                upload = files.get("document")
                if upload is None:
                    raise ValueError("Missing document upload.")
                filename, declared_type, content = upload
                if not content or len(content) > SETTINGS.max_upload_bytes:
                    raise ValueError("Document must be between 1 byte and 20 MB.")
                content_type = declared_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
                if content_type not in SETTINGS.allowed_content_types:
                    raise ValueError("Use PDF, PNG, JPEG, or WebP.")
                return self.send_json(
                    200,
                    process(
                        Path(filename).name,
                        content,
                        content_type,
                        fields.get("mode", "demo"),
                    ),
                )
            if self.path == "/api/query":
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length))
                return self.send_json(200, query(body.get("question", "")))
            self.send_json(404, {"error": "Not found"})
        except Exception as exc:
            self.send_json(400, {"error": str(exc)})

    def log_message(self, fmt, *args):
        sys.stdout.write(f"[nova] {fmt % args}\n")


def main() -> None:
    """Start the local HTTP adapter after initializing durable storage."""
    connect()
    server = ThreadingHTTPServer((SETTINGS.host, SETTINGS.port), Handler)
    print(
        "Nova Trade Document Intelligence: "
        f"http://{SETTINGS.host}:{SETTINGS.port}"
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
