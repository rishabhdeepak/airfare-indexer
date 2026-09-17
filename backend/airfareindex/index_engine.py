"""
Airfare Price Index calculation engine.

This module converts FareObservation records into:
    1. Route-level airfare indices
    2. National Airfare Price Index (APIx)

Current prototype methodology:
    - The earliest available observation date is used as the base date.
    - Base-period route average = index 100.
    - Later route index = (current average fare / base average fare) * 100.
    - National APIx = weighted average of available route indices.

Route weights are stored in the Route model rather than hard-coded here.
"""

from datetime import date

from django.db.models import Avg

from airfareindex.models import (
    FareObservation,
    Route,
    RouteIndexValue,
    NationalIndexValue,
)


def get_base_period_date() -> date | None:
    """
    Return the earliest date for which fare observations exist.
    """

    earliest = (
        FareObservation.objects
        .order_by("scraped_at")
        .first()
    )

    if earliest is None:
        return None

    return earliest.scraped_at.date()


def compute_route_average_fare(
    route: Route,
    on_date: date,
) -> float | None:
    """
    Calculate the average total fare for a route on a given
    collection date.
    """

    result = (
        FareObservation.objects
        .filter(
            origin=route.origin,
            destination=route.destination,
            scraped_at__date=on_date,
        )
        .aggregate(avg=Avg("total_fare"))
    )

    return result["avg"]


def compute_route_index(
    route: Route,
    target_date: date,
    base_date: date,
) -> dict | None:
    """
    Calculate the route index for target_date relative to base_date.
    """

    base_avg = compute_route_average_fare(
        route,
        base_date,
    )

    target_avg = compute_route_average_fare(
        route,
        target_date,
    )

    if base_avg is None or target_avg is None:
        return None

    if base_avg == 0:
        return None

    index_value = (
        float(target_avg) / float(base_avg)
    ) * 100

    return {
        "avg_fare": target_avg,
        "index_value": index_value,
    }


def compute_and_save_indices_for_date(
    target_date: date,
) -> dict:
    """
    Calculate route indices and the national APIx for a date.
    """

    base_date = get_base_period_date()

    if base_date is None:
        return {
            "error": (
                "No fare observations exist. "
                "Run the scraper first."
            )
        }

    routes = Route.objects.filter(active=True)

    route_results = {}

    weighted_sum = 0.0
    weight_total_used = 0.0

    for route in routes:

        result = compute_route_index(
            route,
            target_date,
            base_date,
        )

        if result is None:
            continue

        RouteIndexValue.objects.update_or_create(
            route=route,
            observation_date=target_date,
            defaults={
                "avg_fare": result["avg_fare"],
                "index_value": result["index_value"],
            },
        )

        route_name = f"{route.origin}-{route.destination}"

        route_results[route_name] = result["index_value"]

        weighted_sum += (
            result["index_value"] * route.weight
        )

        weight_total_used += route.weight

    if weight_total_used == 0:
        return {
            "error": (
                f"No route data found for {target_date}."
            )
        }

    # Renormalize weights when some routes have no data.
    national_index = (
        weighted_sum / weight_total_used
    )

    NationalIndexValue.objects.update_or_create(
        observation_date=target_date,
        defaults={
            "index_value": national_index,
            "routes_included": len(route_results),
        },
    )

    return {
        "base_date": base_date,
        "target_date": target_date,
        "route_indices": route_results,
        "national_index": national_index,
        "routes_included": len(route_results),
    }