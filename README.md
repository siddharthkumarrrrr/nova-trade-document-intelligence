# Nova Trade Document Intelligence - Part 1

A presentation-ready proof of concept for GoComet's Full-Stack AI Engineer DAW.
It turns a trade document into evidence-backed structured fields, validates those
fields against customer rules, routes the shipment, stores the result in SQLite,
and answers grounded natural-language questions over stored runs.

## What is included

- Extractor Agent: PDF/image to typed fields, confidence, and source evidence
- Validator Agent: deterministic customer-rule comparison
- Router Agent: deterministic bounded decision policy and amendment template
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
```

Start the app:

```powershell
python app.py
```

Open `http://127.0.0.1:8000`. Demo mode works without any API key; select
Gemini in the UI for real extraction. Never commit `.env`.

Gemini is used for extraction because it accepts PDFs and images natively and
supports JSON Schema output. The default is `gemini-3.6-flash`; override it with
`GEMINI_MODEL`.

LangGraph orchestrates three responsibility boundaries - Extractor, Validator,
and Router - with a SQLite
checkpointer. Each run uses its run ID as the LangGraph thread ID, so completed
nodes survive a process restart and can be inspected or replayed.

Every real document makes one LLM call: Gemini vision extraction. The Validator
compares the typed extraction with customer rules in deterministic Python. The
Router deterministically selects one of the three allowed outcomes and generates
its explanation/amendment template from the field-level result.

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
and routing policy. An uncertain or mismatched required field can never be
auto-approved.

## Submission checklist

- [x] Runnable POC with all five required behaviours
- [x] PRD source
- [x] Technical write-up source
- [x] Two sample documents (clean and messy)
- [x] Sample queries
- [ ] Record the 2-3 minute demo video
- [ ] Add the supplied Nova job description to the PRD references if available
