# 60-second portfolio explanation

"I built a local appointment-booking automation as a practice system for small business workflows. n8n accepts a booking inquiry through a webhook, calls my FastAPI extraction endpoint, and either asks for missing details or creates a booking. My backend validates future weekday slots, prevents duplicate bookings with a database unique constraint, and generates a confirmation draft. A local dashboard shows the results. The app works in rules mode and optionally integrates an LLM. No real email is sent."

## Interview demo checklist

1. Show `workflows/appointment-booking.json` inside n8n.
2. POST a **complete** sample request; point out the true IF branch and booked response.
3. POST the **same request** again; explain why the SQLite unique constraint prevents double booking.
4. POST `{"message":"Can I get an appointment?"}`; show the false IF branch with missing details.
5. Open `http://localhost:8000`, refresh activity, and display bookings and drafts.
6. Explain LLM/rules selection by showing the returned `parser` field.

## Make the project yours

- Add an n8n error-handling workflow with a dedicated alert channel.
- Implement cancellation/rescheduling and tests.
- Build a real Google Calendar adapter with OAuth (and rollback on API failure).
- Add authenticated admin access, secret management, rate limiting and retention rules.
- Configure an approved email provider with explicit permission before sending any confirmations.

**Do not claim to have built these extensions until you have implemented and tested them.**
