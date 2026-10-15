# BookingPilot Upgrade Guide: Availability Branch + Suggestions

This is an update to the original six-node BookingPilot practice project. It adds a true availability decision in n8n and real alternative slots from SQLite. **No customer emails are sent.**

## Exactly which files changed?

| File | Purpose | What you can customize |
| --- | --- | --- |
| `workflows/appointment-booking.json` | Importable eight-node workflow | Node positions/names, webhook path, logic branches |
| `app/main.py` | Shared availability calculation and `GET /api/alternatives` endpoint | Opening hours, number of suggestions, ranking strategy |
| `tests/test_api.py` | Coverage of alternatives, occupied dates, and workflow graph | Additional dates, race-condition tests |
| `README.md` | Import, endpoints, and demo guide | Your own screenshots and findings |

You do **not** need to change `app/parser.py`, `app/storage.py` or `docker-compose.yml` to try the upgrade.

## In n8n: where to modify

1. Open **http://localhost:5678** in your browser.
2. **Create a new workflow** and choose **Import from File**. Select `workflows/appointment-booking.json` from the extracted upgraded ZIP. If you already imported the previous version, keep it for comparison or replace it and deactivate the old one (same webhook path cannot be active twice).
3. In the node **Extract booking details**, check the HTTP URL: `http://api:8000/api/parse` (n8n launched via the included Docker Compose).
4. In **Required fields present?**, the true output goes to **Check available slots**; false goes to **Return customer response**.
5. In **Check available slots**, the HTTP GET URL is `http://api:8000/api/slots`; query field **day** comes from **Extract booking details**.
6. In **Requested slot available?**, the expression checks whether the requested time is in the `available` array. True: **Book appointment + create draft**; false: **Suggest alternative slots**.
7. In **Suggest alternative slots**, GET `http://api:8000/api/alternatives` with query parameters **day** and **time** from **Extract booking details**. Backend responds with `suggested_slots`.
8. The node **Return customer response** replies with the JSON returned by the active branch. It also returns the parsing response when required fields are missing.

**If n8n is running outside Docker:** Change the four API HTTP URLs in `Extract booking details`, `Check available slots`, `Book appointment + create draft`, and `Suggest alternative slots` (four nodes) from `http://api:8000` to `http://localhost:8000` if n8n and the backend both run on the same machine. If n8n runs in Docker while the API runs on the host, `host.docker.internal` may be needed instead.

## In Python: where to modify

Open `app/main.py` in VS Code:

- `TIMES = ...` near the top: change the allowed appointment hours.
- `_available_slots(...)`: finds open times, excluding occupied times, weekends, and past times.
- `_alternative_payload(...)`: sorts actual free slots by distance from the requested time. Modify `[:3]` to suggest a different number of slots.
- `@app.get("/api/alternatives")`: new endpoint used by n8n's occupied-slot branch.
- `@app.post("/api/book")`: catches simultaneous booking conflicts and responds with suggestions as a fallback.

## Run

From the extracted project root:

```bash
cp .env.example .env
# On Windows PowerShell instead: Copy-Item .env.example .env
docker compose up --build -d
```

- FastAPI dashboard: http://localhost:8000
- OpenAPI documentation: http://localhost:8000/docs
- n8n workflow editor: http://localhost:5678

Import the workflow in n8n. Select the webhook node and click **Listen for test event**. To test a date, use a *future weekday* and your local timezone (Europe/Vienna).

```bash
python scripts/demo.py --target n8n-test
```

Send the same request again (listen for another event in test mode): the second request should return `status: "slot_unavailable"` with `suggested_slots`. A request without name/email should return `status: "needs_details"`. Check the dashboard for saved appointments and **unsent** email drafts.

## Test the backend without n8n

```bash
pip install -r requirements-dev.txt
pytest -q
```

## Questions you should be able to answer in an interview

- Why do you check availability *before* booking and still enforce `UNIQUE(day, time)` in SQLite? (There can be races between checking and inserting.)
- Why is the confirmation stored as a draft rather than sent automatically?
- What changes are needed before production? (Authentication, rate limits, privacy, retention, retries, observability, time zones, calendar synchronization.)
- How would you handle rescheduling or a fully booked day?

**Testing note:** The Python API tests and workflow JSON structure are verified by the project test suite. The exported workflow still needs a live import and end-to-end test in your own n8n installation. This is a local demonstration, not a production service.
