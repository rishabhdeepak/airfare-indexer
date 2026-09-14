"""
airfare_scraper.py — SIH26056 Web Scraping module
Milestone 1: DEL -> BOM, T+7, SpiceJet.

Approach: navigate to SpiceJet's search page like a normal browser visitor,
and capture the JSON response from their availability API call that the
page itself triggers to render results. We do NOT call the API directly
with raw HTTP requests — we let Playwright drive a real page load and
listen for the response, same as any browser would receive.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from playwright.async_api import async_playwright

SOURCE_NAME = "SpiceJet"
ORIGIN = "DEL"
DESTINATION = "BOM"
ADVANCE_DAYS = 7
HEADLESS = False  # set to False so you can WATCH what the browser actually does

CARRIER_NAMES = {
    "SG": "SpiceJet",
}


def get_flight_date(advance_days: int) -> str:
    return (datetime.now() + timedelta(days=advance_days)).strftime("%Y-%m-%d")


def build_search_url(origin: str, destination: str, flight_date: str) -> str:
    return (
        "https://www.spicejet.com/search"
        f"?from={origin}&to={destination}"
        "&tripType=1"
        f"&departure={flight_date}"
        "&adult=1&child=0&srCitizen=0&infant=0"
        "&currency=INR&redirectTo=/"
    )


def parse_availability_response(data: dict, origin: str, destination: str, advance_days: int) -> list[dict]:
    """Turn SpiceJet's raw availability JSON into our team's standard schema."""
    records = []
    trips = data.get("data", {}).get("trips", [])
    fares_available = data.get("data", {}).get("faresAvailable", {})

    for trip in trips:
        for journey in trip.get("journeysAvailable", []):
            designator = journey.get("designator", {})
            flight_date = designator.get("departure", "")[:10]  # 'YYYY-MM-DD'

            segments = journey.get("segments", [])
            carrier_code = None
            flight_number = None
            if segments:
                identifier = segments[0].get("identifier", {})
                carrier_code = identifier.get("carrierCode")
                flight_number = identifier.get("identifier")

            airline = CARRIER_NAMES.get(carrier_code, carrier_code or "Unknown")

            # Each flight offers several fare classes (Saver, Flexi, etc.) —
            # pick the cheapest bookable one, standard for a price index.
            best = None
            for fare_key in journey.get("fares", {}).keys():
                fare_detail = fares_available.get(fare_key)
                if not fare_detail:
                    continue
                passenger_fares = fare_detail.get("passengerFares", [])
                if not passenger_fares:
                    continue
                pf = passenger_fares[0]  # adult passenger fare

                base_fare = pf.get("discountedFare", 0)
                total_fare = pf.get("fareAmount", 0)
                charges = pf.get("serviceCharges", [])
                fees = sum(c["amount"] for c in charges if c.get("type") == 4)
                taxes = sum(c["amount"] for c in charges if c.get("type") == 5)

                candidate = {
                    "base_fare": base_fare,
                    "taxes": taxes,
                    "fees": fees,
                    "total_fare": total_fare,
                }
                if best is None or candidate["total_fare"] < best["total_fare"]:
                    best = candidate

            if best is None:
                continue  # sold out / no fares for this flight

            records.append({
                "origin": origin,
                "destination": destination,
                "flight_date": flight_date,
                "airline": airline,
                "flight_number": f"{carrier_code} {flight_number}" if carrier_code else None,
                "advance_days": advance_days,
                "base_fare": best["base_fare"],
                "taxes": best["taxes"],
                "fees": best["fees"],
                "total_fare": best["total_fare"],
                "source": SOURCE_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    return records


async def scrape_one_route(origin: str, destination: str, advance_days: int) -> list[dict] | None:
    """Returns a list of records (possibly empty if genuinely no flights),
    or None if the scrape itself failed (network issue, timeout, etc.) —
    callers should retry on None, but treat [] as a valid, final result."""
    flight_date = get_flight_date(advance_days)
    search_url = build_search_url(origin, destination, flight_date)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        page = await browser.new_page()

        availability_responses = []

        def log_api_call(response):
            if "/api/" in response.url:
                print(f"  [API] {response.status}  {response.url[:120]}")
            if "api/v3/search/availability" in response.url and response.request.method == "POST":
                availability_responses.append(response)

        page.on("response", log_api_call)

        try:
            print(f"Navigating to: {search_url}")

            async with page.expect_response(
                lambda r: "api/v3/search/availability" in r.url and r.request.method == "POST",
                timeout=45000,
            ) as response_info:
                await page.goto(search_url, timeout=45000)

            response = await response_info.value
            data = await response.json()

            if len(availability_responses) > 1:
                print(f"  NOTE: {len(availability_responses)} separate 'availability' calls fired in this page load "
                      f"(using the first one). This may explain run-to-run count differences.")

            records = parse_availability_response(data, origin, destination, advance_days)

            if not records:
                debug_name = f"debug_empty_{origin}_{destination}_T{advance_days}.json"
                with open(debug_name, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                print(f"  0 records (genuinely no flights) — raw response saved to {debug_name}")

            return records  # [] here is a confirmed, real result

        except Exception as e:
            print(f"  FAILED (will retry): {e}")
            await page.screenshot(path=f"debug_screenshot_{origin}_{destination}_T{advance_days}.png", full_page=True)
            html = await page.content()
            with open(f"debug_page_{origin}_{destination}_T{advance_days}.html", "w", encoding="utf-8") as f:
                f.write(html)
            return None  # signal: this needs a retry, don't treat as "no flights"
        finally:
            await browser.close()


async def scrape_one_route_with_retry(origin: str, destination: str, advance_days: int, max_attempts: int = 2) -> list[dict]:
    for attempt in range(1, max_attempts + 1):
        result = await scrape_one_route(origin, destination, advance_days)
        if result is not None:
            return result
        if attempt < max_attempts:
            print(f"  Retrying ({attempt}/{max_attempts})...")
            await asyncio.sleep(3)
    print(f"  Gave up after {max_attempts} attempts — treating as 0 records, but this is UNCONFIRMED, not a real empty result.")
    return []


async def scrape_multiple(routes: list[tuple[str, str]], booking_windows: list[int]) -> list[dict]:
    """Loop scrape_one_route() across every route x booking-window combination."""
    all_records = []
    for origin, destination in routes:
        for advance_days in booking_windows:
            print(f"\n=== {origin} -> {destination}, T+{advance_days} ===")
            records = await scrape_one_route_with_retry(origin, destination, advance_days)
            print(f"  Got {len(records)} records")
            all_records.extend(records)
            await asyncio.sleep(2)  # be a polite, low-rate visitor
    return all_records


def save_to_json(records: list[dict], filename: str = "airfares.json"):
    with open(filename, "w") as f:
        json.dump(records, f, indent=2)


if __name__ == "__main__":
    # Single-route mode (Milestone 1) — kept for quick testing:
    # data = asyncio.run(scrape_one_route(ORIGIN, DESTINATION, ADVANCE_DAYS))

    # Multi-route, multi-booking-window mode (Day 3 expansion):
    ROUTES = [
        ("DEL", "BOM"),
        ("DEL", "BLR"),
        ("BOM", "BLR"),
    ]
    BOOKING_WINDOWS = [1, 7, 15, 30, 45]

    data = asyncio.run(scrape_multiple(ROUTES, BOOKING_WINDOWS))
    print(f"\nCollected {len(data)} total fare records")
    save_to_json(data)