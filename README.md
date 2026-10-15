# BookingPilot — AI Appointment Booking with n8n + FastAPI

> **A compact portfolio practice project:** webhook → extract customer details → validate → book an available slot → create an **unsent** confirmation draft.

![Python](https://img.shields.io/badge/Python-3.12+-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-API-009688) ![n8n](https://img.shields.io/badge/n8n-workflow-orange) ![SQLite](https://img.shields.io/badge/SQLite-local_database-003B57)

**Why this project?** Business automation companies build appointment scheduling, AI reception, and integrations. This mini project demonstrates a complete, inspectable workflow without requiring a CRM subscription, real customer data, or a paid LLM account. It is an independent portfolio demo, **not affiliated with Sparkspot**.

## What it does

1. Receives a customer appointment request (web dashboard or n8n webhook).
2. Extracts `name`, `email`, `day`, `time`, `service`.
3. Returns a clarification response when fields are missing.
4. Checks opening hours, future dates and uniqueness; prevents booking the same 30-minute slot twice.
5. When a slot is occupied, suggests up to three real available times from SQLite, closest first.
6. Saves confirmed appointments to SQLite and creates an **email confirmation draft** for inspection (never sends it).
7. Lets you see bookings and outbox drafts in a local web dashboard.

**AI note:** Works without credentials using a simple, transparent rule-based parser. With a valid `OPENAI_API_KEY`, it attempts LLM extraction, then falls back to rules if needed. The response includes `parser: "openai"` or `parser: "rules"` so you can tell which mode was actually used. This is **not** a live phone assistant, WhatsApp integration, or real Google Calendar integration.

## Tech stack

- **n8n:** importable 8-node workflow (`workflows/appointment-booking.json`)
- **Python / FastAPI:** parsing and booking endpoints, input validation
- **SQLite:** appointments and unsent confirmation drafts
- **Docker Compose:** local n8n and API service
- **pytest:** backend tests
- **Optional OpenAI API:** extract fields from less structured customer messages

## Quick start (Docker — recommended)

Prerequisites: Docker Desktop or Docker Engine with Compose. Run these commands from the repository root:

```bash
cp .env.example .env
# Optional: add OPENAI_API_KEY to .env to try real LLM extraction.
docker compose up --build -d
```

Open:

- Demo dashboard: **http://localhost:8000**
- OpenAPI documentation: **http://localhost:8000/docs**
- n8n editor: **http://localhost:5678** (create a local n8n account on first launch)

The web dashboard works **before** you import the n8n workflow. Choose a future weekday and a 30-minute time slot from 09:00 to 16:30, Vienna local time.

### Import and run the n8n workflow

1. Visit `http://localhost:5678` and complete the n8n setup.
2. Create/open a workflow, choose **Import from File**, and select `workflows/appointment-booking.json`.
3. The workflow has 8 nodes: Webhook → Parse → IF required fields → GET slots → IF available → Book / Suggest alternatives → One shared reply. Missing details also go to the shared reply.
4. Click **Listen for test event** on its Webhook node (or execute workflow in test mode, depending on your n8n version).
5. In a separate terminal run `python scripts/demo.py --target n8n-test` to send a booking for an automatically calculated future weekday. Alternatively, use this curl example (change the date if needed):

```bash
curl -X POST 'http://localhost:5678/webhook-test/appointment-assistant' \
  -H 'Content-Type: application/json' \
  -d '{"message":"Hi, my name is Alex; email alex@example.com; I need a consultation on 2026-11-03 at 14:00."}'
```

**Expected:** JSON `status: "booked"` if the slot is available. If the slot is occupied or invalid, expect `slot_unavailable` and up to three real `suggested_slots` (e.g. `14:30`, `13:30`, `15:00`). If you omit a required detail, expect `status: "needs_details"` and a list of missing fields.

After test mode, **activate / publish** the workflow in n8n to use the normal endpoint `http://localhost:5678/webhook/appointment-assistant` (version-specific n8n UI wording may differ).

> The workflow uses `http://api:8000` because n8n and FastAPI share a Compose network. When running n8n outside Docker, update both HTTP Request nodes to `http://localhost:8000` (if FastAPI is on the same machine). Do not expose the workflow to the public internet without authentication, abuse controls, and a privacy review.

### Try it without Docker (backend only)

```bash
python -m venv .venv
source .venv/bin/activate                 # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Open `http://localhost:8000` to test the dashboard. Run `python scripts/demo.py` for a complete backend example. Run n8n separately if desired.

## Local API examples

Send an inquiry:

```bash
curl -X POST 'http://localhost:8000/api/parse' \
  -H 'Content-Type: application/json' \
  -d '{"message":"My name is Alex; email alex@example.com; haircut on 2026-11-03 at 11:30"}'
```

Book directly (if the date is still in the future and available):

```bash
curl -X POST 'http://localhost:8000/api/book' \
  -H 'Content-Type: application/json' \
  -d '{"name":"Alex","email":"alex@example.com","day":"2026-11-03","time":"11:30","service":"Haircut"}'
```

Additional routes: `GET /health`, `GET /api/slots?day=YYYY-MM-DD`, `GET /api/alternatives?day=YYYY-MM-DD&time=HH:MM`, `GET /api/bookings`, `GET /api/outbox`.

## Run tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

The tests use isolated temporary SQLite files and never use a real OpenAI key.

## Project structure

```text
app/
  main.py                # FastAPI endpoints + booking validation
  parser.py              # optional LLM / deterministic fallback
  storage.py             # SQLite schema and persistence
  static/index.html      # local demo dashboard
workflows/
  appointment-booking.json  # upgraded 8-node n8n import
scripts/demo.py          # send a test request automatically
tests/test_api.py        # backend tests
docs/interview-notes.md # talking points and extensions
Dockerfile
docker-compose.yml
.env.example
pytest.ini
```

## Security and limitations

This is a **local learning prototype**, not production-ready software.

- No authentication, API rate limits, or access restrictions beyond localhost Docker port bindings.
- No actual email or SMS is sent: `outbox` contains unsent drafts only.
- Appointments are stored in local SQLite; there is no Google Calendar syncing or real phone service.
- Working hours are fixed (Monday–Friday, 09:00–17:00, Europe/Vienna), all appointments are 30 minutes.
- Natural-language parsing works best with a configured LLM; free rules mode expects ISO dates and 24-hour time.
- The LLM provider receives customer messages **only when configured**. Do not send real customer data without proper agreements, consent/legal basis, and data security controls.
- Docker Compose uses the latest n8n image for ease of demonstration; pin and audit dependencies before any deployment.

## What to demonstrate to a recruiter

- Run an inquiry through the n8n webhook.
- Show n8n routing on missing fields vs. a complete request.
- Book the same slot twice to demonstrate conflict prevention and real alternative suggestions.
- Show the locally saved appointment and **draft** confirmation.
- Explain why local development differs from secure production deployment.

See `docs/interview-notes.md` for a 60-second demo script and ideas to improve the code yourself.

**Upgrading from the previous version?** See [`docs/UPGRADE-GUIDE.md`](docs/UPGRADE-GUIDE.md) for the exact files and n8n nodes to modify. This upgrade has been unit-tested but live import/execution in n8n needs verification on your machine.

## License

MIT License. See `LICENSE`.
