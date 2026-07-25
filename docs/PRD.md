# Product Requirements Document

## Nova Trade Document Intelligence - Part 1

**Owner:** Full-Stack AI Engineer candidate  
**Pilot customer:** Acme Retail India  
**Scope:** One-document validation foundation; Part 2 email trigger and multi-document workflow are explicitly out of scope.

## 1. Nova, FDE, and the System of Outcomes

### What is Nova?

Nova is an agentic operations layer for global trade. Traditional SaaS records
shipments, exposes workflows, and waits for people to move work forward. Nova
instead reads unstructured inputs, applies customer-specific operating rules,
decides the next safe action, and completes the repetitive portion of the job.
The target is not another dashboard; it is a measurable operational result:
fewer manual checks, fewer document-error cycles, and faster clearance. Because
trade documents are messy and rules vary by customer, Nova must combine models,
deterministic controls, tools, durable state, and human review. The value comes
from owning the path from input to verified outcome while making uncertainty,
evidence, and accountability visible.

### What is the FDE model, and why use it?

A Forward Deployed Engineer works close to the customer's operation, combining
engineering with discovery and implementation. The FDE observes how CG operators
actually validate documents, turns informal rules into explicit controls, connects
Nova to the customer's systems, and measures whether the result improves. GoComet
uses this model because trade operations are not standardized enough for a generic
prompt or configuration screen. Each rollout has different documents, terminology,
exceptions, integrations, risk tolerance, and approval policy. Tight deployment
loops let the engineer ship a narrow outcome quickly, learn from real exceptions,
and convert customer-specific insight into reusable platform capability.

### What does “System of Outcomes” mean?

A System of Record stores authoritative facts; a System of Engagement helps
people communicate around those facts. A System of Outcomes is accountable for
moving work to a defined result. Here, the result is not “invoice uploaded” or
“comment added.” It is “document verified, exception explained, and the correct
next action prepared.” Nova consumes records and communication, but it also
interprets, validates, routes, persists, and measures work. Human operators retain
control over ambiguous or high-risk cases. The difference is completion with
guardrails: the product is judged by cycle time and safe straight-through
processing, not by seats, clicks, or records created.

## 2. Problem Statement

Today CG operators open emailed attachments, read every field, recall
customer-specific rules, compare values, type discrepancies, and repeat this
process after every amendment. The flow breaks through:

- illegible scans, inconsistent layouts, and missing fields;
- rules living in people's heads, spreadsheets, and email history;
- transcription errors and inconsistent normalization of names, ports, units,
  Incoterms, and HS codes;
- silent misses when an operator is rushed or inexperienced;
- two-to-four amendment cycles, each adding 4–24 hours;
- no shared view of pending, approved, and disputed documents;
- weak auditability: the source evidence and decision reason are not linked.

In the operator's first five minutes, success means they can upload a document,
see every required field with confidence and source evidence, understand which
rules passed or failed, and accept a safe next action without re-reading the whole
document. Uncertainty must be more obvious than approval.

## 3. Users and Jobs-to-be-Done

**CG operator:** validates high document volumes under time pressure. Cares about
finding exceptions quickly, avoiding costly misses, and producing a complete
amendment request.

**SU document coordinator:** creates and resubmits shipment documents. Cares about
receiving one precise correction list instead of vague or repeated feedback.

**Jobs-to-be-Done**

1. When a supplier document arrives, I want required fields extracted with source
   evidence, so that I do not re-read the entire file.
2. When a value violates a customer rule, I want found and expected values shown
   together, so that I can verify the discrepancy in seconds.
3. When the scan is ambiguous, I want the system to block silent approval and
   identify the uncertain field, so that I retain control of risk.
4. When several discrepancies exist, I want one editable amendment draft, so that
   the supplier receives complete feedback in one cycle.
5. When a shipment is cleared, I want the decision and evidence stored, so that I
   can answer audits without reconstructing email history.
6. When I manage the queue, I want grounded questions over verified runs, so that
   I can see backlog and exception trends without asking an engineer.

## 4. Agent Architecture

Three agents align with three different kinds of work and failure:

1. **Extractor (probabilistic perception):** input is a PDF/image; output is a
   typed document object containing value, confidence, source snippet, and page
   for each required field.
2. **Validator (policy verification):** input is the extraction plus a versioned
   customer rule set. An LLM handles semantic equivalence and returns a structured
   field result; a deterministic rule tool independently checks requiredness,
   confidence, and exact policy. Disagreement becomes `uncertain`.
3. **Router (bounded decision):** input is the complete validation. An LLM proposes
   the outcome, explanation, and editable draft; a deterministic guard constrains
   the final output to one
   of `auto_approve`, `human_review`, or `amendment_request`, with reasoning and
   an editable draft when relevant.

One giant prompt mixes perception, policy, and action, making errors hard to
localize and tests hard to reproduce. Five agents would split cohesive decisions
without adding a distinct trust boundary. Three lets the model do perception while
code owns policy and routing. Agents communicate through versionable JSON
contracts, not free-form conversation. SQLite holds the run after each stage;
after a crash the pipeline can resume from the last valid checkpoint by run ID
and content hash.

## 5. LLM and Tooling Choices

- **Extraction:** Gemini 3.6 Flash is the primary free-tier vision model because
  it accepts PDFs natively and supports JSON Schema output. Groq Qwen 3.6 27B is
  the fallback for images or rendered PDF pages. Both providers are configurable
  through environment variables rather than embedded in policy.
  A smaller model limits cost and latency; hard cases can escalate to a
  stronger model only after a low-confidence or schema failure.
- **Validation:** deterministic Python first enforces equality, requiredness, and
  confidence thresholds. The selected provider is called only when a mismatch in
  a textual field may be an alias, abbreviation, or semantically equivalent
  description. Any model/rule disagreement becomes uncertain.
- **Routing:** deterministic policy controls the three bounded outcomes. Clean
  auto-approval uses no model call; the text model is invoked only to explain an
  exception or draft an editable amendment request, and cannot override policy.
- **Orchestration:** LangGraph models Extractor, Validator, and Router as explicit
  nodes. A SQLite checkpointer saves typed state after every node using the run ID
  as the thread ID. This provides durable recovery, state inspection, and a clean
  path to Part 2 conditional routing and human-review interrupts.
- **Structured output:** required at the extractor boundary; validated again in
  code. Free-form model output is avoided for rules, decisions, database queries,
  and any approval control.
- **Bad documents:** use high-detail input, never infer absent text, retry at most
  once with a stronger model or rendered pages, then route low confidence to a
  human. The POC exposes this state rather than hiding it.

## 6. Trust, Failure Handling, and Evals

Every non-null extracted value must include a visible source snippet and page.
Missing evidence lowers confidence below the approval threshold. Required fields,
model/schema failures, and low confidence fail loud. A document cannot be
auto-approved if any field is `uncertain` or `mismatch`. Network/model retries are
bounded at two attempts, stages have timeouts, files are size/type checked, and
validation/routing never call themselves.

**Offline eval:** a versioned set of at least 100 documents with field-level ground
truth, including 30 degraded scans. Report exact match/F1 by field, evidence
coverage, calibration error, false-approval rate, and route accuracy. The release
gate is zero false approvals on the high-risk test set and at least 95% field
accuracy on clean documents.

**Online metrics:** sample completed and human-reviewed runs; compare operator
corrections against extracted values and recommended routes. Alert on false
approval, confidence drift, rising uncertainty by supplier/layout, model latency,
and cost.

## 7. Metrics and Success Criteria

**North star:** Percentage of submitted documents safely resolved without manual
field-by-field reading, with zero confirmed false approvals.

Supporting metrics:

- field exact-match rate, overall and by required field;
- high-risk false-approval rate;
- evidence coverage rate;
- confidence calibration error;
- percentage routed to human review;
- median upload-to-decision latency and p95 latency;
- average model cost per document;
- amendment cycles per shipment;
- operator handling minutes per document.

**Two-week pilot Go:** at least 100 documents processed; ≥60% safe straight-through
resolution; zero confirmed false approvals; ≥95% clean-document field accuracy;
median decision under 60 seconds; and ≥40% lower operator handling time.

**No-Go:** any confirmed false approval on a high-risk required field, evidence
coverage below 99%, availability below 95%, or operators report that reviewing
the output takes as long as the current process. A No-Go means retain human review,
analyze errors by layout/rule, and do not expand traffic.

## 8. What Comes Next

With two more weeks, build the trigger and multi-document shipment model: ingest a
simulated SU inbox, group BOL/invoice/packing-list attachments, cross-check shared
fields, and present an editable reply for CG approval. This is next because it
closes the gap between an upload demo and the real operational outcome while
reusing every Part 1 boundary. Autonomous sending, broad ERP integrations, and
fine-tuning wait until real exception data proves where they add value.

> Note: This PRD is grounded in the supplied DAW brief and cross-checked against
> GoComet's public Nova Full-Stack AI Engineer job description, including its
> governed-agent, LangGraph, evidence-delivery, and FDE outcome-ownership model.
