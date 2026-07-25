# Nova Trade Document Intelligence - Part 1

A presentation-ready proof of concept for GoComet's Full-Stack AI Engineer DAW.
It turns a trade document into evidence-backed structured fields, validates those
fields against customer rules, routes the shipment, stores the result in SQLite,
and answers grounded natural-language questions over stored runs.

## What is included

- Extractor Agent: PDF/image to typed fields, confidence, and source evidence
- Validator Agent: deterministic rules first; LLM semantic review only for ambiguous text
- Router Agent: deterministic decision policy; LLM drafting only for exceptions
- SQLite audit trail and safe natural-language query templates
- Browser UI showing real pipeline state and agent reasoning
- Clean and messy sample trade documents
- PRD and technical write-up in `docs/`

## Run locally

Requires Python 3.10+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Add your provider key to `.env`:

```dotenv
GEMINI_API_KEY=your-google-ai-studio-key
GEMINI_MODEL=gemini-3.6-flash

# Optional fallback provider
GROQ_API_KEY=
GROQ_MODEL=qwen/qwen3.6-27b
```

Start the app:

```powershell
python app.py
```

Open `http://127.0.0.1:8000`. Demo mode works without any API key; select
Gemini or Groq in the UI for real model calls. Never commit `.env`.

Gemini is the preferred free-tier path because it accepts PDFs natively and
supports JSON Schema output. The default is `gemini-3.6-flash`; override it with
`GEMINI_MODEL`. Groq remains available as a fallback using
`qwen/qwen3.6-27b` and `GROQ_MODEL`; PDFs are rendered to at most five images
for that provider.

LangGraph orchestrates three responsibility boundaries - Extractor, Validator,
and Router - with a SQLite
checkpointer. Each run uses its run ID as the LangGraph thread ID, so completed
nodes survive a process restart and can be inspected or replayed.

The cost-optimized path makes one model call for a clean document: vision
extraction. The Validator uses an LLM only when a textual mismatch may be an
alias or equivalent description. The Router uses an LLM only when it must explain
an exception or draft an amendment; deterministic policy always owns the outcome.

## Suggested 2-3 minute demo

1. Upload `samples/clean-commercial-invoice.pdf`; run Demo mode.
2. Point out evidence and confidence beside every extracted field.
3. Show the validator's field-by-field results and auto-approval.
4. Upload `samples/messy-commercial-invoice.pdf`; run it.
5. Open the mismatches/uncertain fields and show the amendment draft.
6. Ask: `How many shipments were flagged this week?`
7. Close with the persisted audit trail and explicit no-silent-approval policy.

## Sample grounded queries

- `How many shipments were flagged this week?`
- `How many shipments were auto-approved?`
- `Show shipments pending review`
- `Show recent shipments`
- `What is the average extraction confidence?`

## Architecture

`Upload -> Extractor -> durable checkpoint -> Validator -> durable checkpoint -> Router -> SQLite -> UI/query`

The code follows a small layered design:

```text
app.py                  composition entrypoint
nova/settings.py        immutable configuration and filesystem paths
nova/domain.py          field contracts, Pydantic models, JSON Schemas
nova/http_transport.py  bounded multipart HTTP adapter
nova/application.py     providers, agents, policies, LangGraph and persistence
web/                    operator-facing UI
tests/                  agent-policy and transport regression tests
```

The domain contracts do not depend on HTTP or provider code. Settings are
centralized, upload parsing is isolated from workflow logic, and `app.py` contains
no business behavior.

## Run tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Each handoff is typed JSON. LangGraph writes a SQLite checkpoint after every
node, so a run can resume from its last successful step. Real extraction is
bounded to two attempts. Python independently enforces confidence, validation,
and routing policy; model disagreement becomes `uncertain`, never approval.

## Submission checklist

- [x] Runnable POC with all five required behaviours
- [x] PRD source
- [x] Technical write-up source
- [x] Two sample documents (clean and messy)
- [x] Sample queries
- [ ] Record the 2-3 minute demo video
- [ ] Add the supplied Nova job description to the PRD references if available
