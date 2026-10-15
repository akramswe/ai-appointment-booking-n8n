"""Tests intentionally use a temporary database and never contact external AI services."""
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.main import app


def future_weekday(offset=3):
    candidate = (datetime.now(ZoneInfo('Europe/Vienna')) + timedelta(days=offset)).date()
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate.isoformat()


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'test.sqlite3'))
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    with TestClient(app) as instance:
        yield instance


def payload(day=None, time='14:00', email='alex@example.com', service='Consultation'):
    return {"name":"Alex Example", "email":email, "day":day or future_weekday(), "time":time, "service":service}


def test_health_and_ui(client):
    assert client.get('/health').json() == {'status':'ok'}
    result = client.get('/')
    assert result.status_code == 200
    assert 'BookingPilot' in result.text


def test_rule_parser_extracts_details(client):
    text = f"Hi, my name is Alex Example; email alex@example.com; book a haircut on {future_weekday()} at 14:00."
    result = client.post('/api/parse', json={'message':text})
    assert result.status_code == 200
    body = result.json()
    assert body['ready'] is True
    assert body['name'] == 'Alex Example'
    assert body['service'] == 'Haircut'
    assert body['parser'] == 'rules'


def test_missing_details_returns_clarification(client):
    body = client.post('/api/parse',json={'message':'Please book an appointment'}).json()
    assert body['ready'] is False
    assert body['missing'] == ['name', 'email', 'day', 'time']
    assert 'Please provide' in body['reply']


def test_rejects_short_input(client):
    assert client.post('/api/parse',json={'message':'hi'}).status_code == 422


def test_booking_creates_confirmation_draft(client):
    answer = client.post('/api/book',json=payload())
    assert answer.status_code == 200
    assert answer.json()['status'] == 'booked'
    bookings = client.get('/api/bookings').json()['bookings']
    drafts = client.get('/api/outbox').json()['outbox']
    assert len(bookings) == len(drafts) == 1
    assert drafts[0]['status'] == 'draft'
    assert drafts[0]['recipient'] == 'alex@example.com'
    assert 'not sent' in answer.json()['reply']


def test_prevents_double_booking_and_duplicate_drafts(client):
    first = client.post('/api/book',json=payload()).json()
    second = client.post('/api/book',json=payload(email='second@example.com')).json()
    assert first['status'] == 'booked'
    assert second['status'] == 'slot_unavailable'
    assert len(client.get('/api/bookings').json()['bookings']) == 1
    assert len(client.get('/api/outbox').json()['outbox']) == 1


def test_free_slots_update(client):
    day = future_weekday()
    before = client.get('/api/slots',params={'day':day}).json()['available']
    assert '14:00' in before
    client.post('/api/book',json=payload(day=day))
    after = client.get('/api/slots',params={'day':day}).json()['available']
    assert '14:00' not in after
    assert len(after) == len(before)-1


def test_rejects_weekends(client):
    candidate = (datetime.now(ZoneInfo('Europe/Vienna')) + timedelta(days=2)).date()
    while candidate.weekday() != 5:
        candidate += timedelta(days=1)
    assert client.post('/api/book',json=payload(day=candidate.isoformat())).status_code == 422
    assert client.get('/api/slots',params={'day':candidate.isoformat()}).json()['available'] == []


def test_rejects_past_days(client):
    assert client.post('/api/book',json=payload(day='2020-01-01')).status_code == 422


def test_rejects_non_business_hour(client):
    assert client.post('/api/book',json=payload(time='21:00')).status_code == 422


def test_rejects_bad_email_and_unknown_service(client):
    assert client.post('/api/book',json=payload(email='not-an-email')).status_code == 422
    assert client.post('/api/book',json=payload(service='Deep cleaning')).status_code == 422


def test_workflow_export_valid_json_and_connections():
    path = Path(__file__).resolve().parents[1] / 'workflows' / 'appointment-booking.json'
    workflow = json.loads(path.read_text())
    names = {node['name'] for node in workflow['nodes']}
    assert len(names) == 8
    assert 'Incoming appointment request' in names
    assert 'Check available slots' in names
    assert 'Requested slot available?' in names
    assert 'Suggest alternative slots' in names
    assert 'Return customer response' in names
    assert set(workflow['connections']).issubset(names)
    assert all(tgt['node'] in names for edges in workflow['connections'].values() for path in edges['main'] for tgt in path)
    assert not workflow['active']


def test_alternatives_are_actual_available_slots(client):
    day = future_weekday()
    first = client.post('/api/book', json=payload(day=day)).json()
    assert first['status'] == 'booked'
    result = client.get('/api/alternatives', params={'day': day, 'time': '14:00'})
    assert result.status_code == 200
    body = result.json()
    assert body['status'] == 'slot_unavailable'
    assert body['requested_time'] == '14:00'
    assert body['suggested_slots'] == ['14:30', '13:30', '15:00']
    available = client.get('/api/slots', params={'day': day}).json()['available']
    assert all(item in available for item in body['suggested_slots'])


def test_alternatives_ignore_other_booked_slots(client):
    day = future_weekday()
    client.post('/api/book', json=payload(day=day, time='14:00'))
    client.post('/api/book', json=payload(day=day, time='14:30', email='different@example.com'))
    body = client.get('/api/alternatives', params={'day': day, 'time': '14:00'}).json()
    assert '14:00' not in body['suggested_slots']
    assert '14:30' not in body['suggested_slots']
    assert body['suggested_slots'][0] == '13:30'


def test_alternatives_do_not_offer_weekends(client):
    candidate = (datetime.now(ZoneInfo('Europe/Vienna')) + timedelta(days=2)).date()
    while candidate.weekday() != 5:
        candidate += timedelta(days=1)
    body = client.get('/api/alternatives',params={'day':candidate.isoformat(),'time':'10:00'}).json()
    assert body['suggested_slots'] == []


def test_alternatives_validate_time(client):
    day = future_weekday()
    assert client.get('/api/alternatives', params={'day': day, 'time':'not-a-time'}).status_code == 422
    assert client.get('/api/alternatives', params={'day': day, 'time':'25:00'}).status_code == 422


def test_competing_bookings_also_provide_suggestions(client):
    day = future_weekday()
    client.post('/api/book', json=payload(day=day))
    collision = client.post('/api/book', json=payload(day=day,email='second@example.com'))
    assert collision.status_code == 200
    body = collision.json()
    assert body['status'] == 'slot_unavailable'
    assert '14:30' in body['suggested_slots']
    assert len(client.get('/api/outbox').json()['outbox']) == 1


def test_workflow_true_and_false_branches():
    workflow = json.loads((Path(__file__).resolve().parents[1] / 'workflows' / 'appointment-booking.json').read_text())
    edges = workflow['connections']
    assert edges['Required fields present?']['main'][1][0]['node'] == 'Return customer response'
    assert edges['Requested slot available?']['main'][0][0]['node'] == 'Book appointment + create draft'
    assert edges['Requested slot available?']['main'][1][0]['node'] == 'Suggest alternative slots'
    assert edges['Suggest alternative slots']['main'][0][0]['node'] == 'Return customer response'
