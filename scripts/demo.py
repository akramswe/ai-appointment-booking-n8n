"""Send a complete test booking to the API or n8n; standard library only."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


def post(url: str, payload: dict) -> dict:
    request = Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def main():
    cli = argparse.ArgumentParser(description="Test one customer appointment request")
    cli.add_argument("--target", choices=("api", "n8n-test", "n8n-live"), default="api")
    args = cli.parse_args()
    day = (datetime.now(ZoneInfo("Europe/Vienna")) + timedelta(days=3)).date()
    while day.weekday() >= 5:
        day += timedelta(days=1)
    message = f"Hello, my name is Alex; email alex@example.com; book a consultation on {day} at 14:00."
    print("Customer request:", message)
    try:
        if args.target == "api":
            result = post("http://localhost:8000/api/parse", {"message": message})
            print("Parsed:", json.dumps(result, indent=2))
            if result["ready"]:
                result = post("http://localhost:8000/api/book", result)
        else:
            segment = "webhook-test" if args.target == "n8n-test" else "webhook"
            result = post(f"http://localhost:5678/{segment}/appointment-assistant", {"message": message})
        print("Result:", json.dumps(result, indent=2))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise SystemExit(f"Request failed: {exc}. Check services and activate/listen to the n8n webhook first.")


if __name__ == "__main__":
    main()
