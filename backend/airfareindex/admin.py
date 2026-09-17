from django.contrib import admin

from .models import (
    FareObservation,
    Route,
    RouteIndexValue,
    NationalIndexValue,
)


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = (
        "origin",
        "destination",
        "weight",
    )


@admin.register(FareObservation)
class FareObservationAdmin(admin.ModelAdmin):
    list_display = (
        "origin",
        "destination",
        "flight_date",
        "airline",
        "flight_number",
        "advance_days",
        "base_fare",
        "taxes",
        "fees",
        "total_fare",
        "source",
        "scraped_at",
    )

    list_filter = (
        "airline",
        "source",
        "advance_days",
        "flight_date",
    )

    search_fields = (
        "origin",
        "destination",
        "airline",
        "flight_number",
    )


@admin.register(RouteIndexValue)
class RouteIndexValueAdmin(admin.ModelAdmin):
    list_display = (
        "route",
        "observation_date",
        "avg_fare",
        "index_value",
    )

    list_filter = (
        "observation_date",
        "route",
    )


@admin.register(NationalIndexValue)
class NationalIndexValueAdmin(admin.ModelAdmin):
    list_display = (
        "observation_date",
        "index_value",
        "routes_included",
    )

    list_filter = (
        "observation_date",
    )