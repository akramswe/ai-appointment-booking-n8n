"""Small booking service intended for local demonstration and n8n practice."""
from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field

from app.parser import parse_request
from app.storage import connection, init_db

TZ = ZoneInfo("Europe/Vienna")
SERVICE_NAMES = ("Consultation", "Haircut", "Support Call")
TIMES = tuple(f"{hour:02d}:{minute:02d}" for hour in range(9, 17) for minute in (0, 30))


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="AI Appointment Booking | n8n Practice", version="1.0.0", lifespan=lifespan)


class CustomerMessage(BaseModel):
    message: str = Field(min_length=3, max_length=2000)


class Booking(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    email: EmailStr
    day: date
    time: str = Field(pattern=r"^\d{2}:\d{2}$")
    service: str = "Consultation"


def _valid_day_and_time(day: date, slot: str) -> None:
    if slot not in TIMES:
        raise HTTPException(422, "Choose a half-hour slot between 09:00 and 16:30")
    if day.weekday() >= 5:
        raise HTTPException(422, "Bookings are available Monday to Friday")
    start = datetime.combine(day, time.fromisoformat(slot), tzinfo=TZ)
    if start <= datetime.now(TZ):
        raise HTTPException(422, "Choose a future date and time")


@app.get("/")
def homepage():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/parse")
def parse(payload: CustomerMessage):
    return parse_request(payload.message)


@app.get("/api/slots")
def slots(day: date = Query(...)):
    if day.weekday() >= 5 or day < datetime.now(TZ).date():
        return {"day": day.isoformat(), "available": []}
    with connection() as conn:
        taken = {row["time"] for row in conn.execute("SELECT time FROM appointments WHERE day = ?", (day.isoformat(),))}
    available = [slot for slot in TIMES if slot not in taken and datetime.combine(day, time.fromisoformat(slot), tzinfo=TZ) > datetime.now(TZ)]
    return {"day": day.isoformat(), "available": available}


@app.post("/api/book")
def book(booking: Booking):
    _valid_day_and_time(booking.day, booking.time)
    if booking.service not in SERVICE_NAMES:
        raise HTTPException(422, f"service must be one of: {', '.join(SERVICE_NAMES)}")
    day = booking.day.isoformat()
    email = str(booking.email).lower()
    with connection() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO appointments (customer_name, customer_email, service, day, time) VALUES (?, ?, ?, ?, ?)",
                (booking.name.strip(), email, booking.service, day, booking.time),
            )
        except sqlite3.IntegrityError:
            return {"status": "slot_unavailable", "reply": f"Sorry, {day} at {booking.time} is already booked. Please choose another slot."}
        booking_id = cursor.lastrowid
        message = (
            f"Hello {booking.name.strip()},\n\nYour {booking.service.lower()} is booked for "
            f"{day} at {booking.time} (Europe/Vienna).\n\nThank you!"
        )
        conn.execute(
            "INSERT INTO outbox (appointment_id, recipient, subject, message) VALUES (?, ?, ?, ?)",
            (booking_id, email, "Your appointment confirmation (DRAFT)", message),
        )
    return {
        "status": "booked", "appointment_id": booking_id,
        "day": day, "time": booking.time, "service": booking.service,
        "reply": f"Booked {booking.service.lower()} for {booking.name.strip()} on {day} at {booking.time}. A confirmation draft was saved (not sent).",
    }


@app.get("/api/bookings")
def bookings():
    with connection() as conn:
        rows = conn.execute(
            "SELECT id, customer_name, service, day, time, created_at FROM appointments ORDER BY day, time"
        ).fetchall()
    return {"bookings": [dict(row) for row in rows]}


@app.get("/api/outbox")
def outbox():
    with connection() as conn:
        rows = conn.execute(
            "SELECT id, appointment_id, recipient, subject, message, status FROM outbox ORDER BY id DESC"
        ).fetchall()
    return {"outbox": [dict(row) for row in rows]}
