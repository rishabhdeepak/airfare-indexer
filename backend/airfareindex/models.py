from django.db import models

class Route(models.Model):
    """
    A city-pair included in the Airfare Price Index basket.
    """

    origin = models.CharField(max_length=3)
    destination = models.CharField(max_length=3)

    weight = models.FloatField()

    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["origin", "destination"],
                name="unique_route"
            )
        ]

    def __str__(self):
        return f"{self.origin}->{self.destination}"

class FareObservation(models.Model):
    """
    One actual airfare quote collected from an airline or OTA.
    """

    origin = models.CharField(max_length=3)
    destination = models.CharField(max_length=3)

    flight_date = models.DateField()

    airline = models.CharField(max_length=50)
    flight_number = models.CharField(
        max_length=20,
        null=True,
        blank=True
    )

    # How many days before the flight the fare was collected
    advance_days = models.PositiveIntegerField()

    # Fare components
    base_fare = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    taxes = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    fees = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    total_fare = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    # Where this observation came from
    source = models.CharField(max_length=50)

    # When we collected it
    scraped_at = models.DateTimeField()

    class Meta:
        indexes = [
            models.Index(
                fields=["origin", "destination", "flight_date"]
            ),
            models.Index(
                fields=["advance_days"]
            ),
        ]

    def __str__(self):
        return (
            f"{self.origin}->{self.destination} "
            f"{self.flight_date} "
            f"({self.airline}) ₹{self.total_fare}"
        )


class RouteIndexValue(models.Model):
    """
    Daily price index for one route.
    """

    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        related_name="index_values"
    )

    observation_date = models.DateField()

    avg_fare = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    index_value = models.FloatField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["route", "observation_date"],
                name="unique_route_index_date"
            )
        ]

        indexes = [
            models.Index(
                fields=["observation_date"]
            ),
        ]

    def __str__(self):
        return (
            f"{self.route} @ {self.observation_date}: "
            f"{self.index_value:.1f}"
        )


class NationalIndexValue(models.Model):
    """
    Daily headline Airfare Price Index (APIx).
    """

    observation_date = models.DateField(unique=True)

    index_value = models.FloatField()

    routes_included = models.PositiveIntegerField()

    class Meta:
        indexes = [
            models.Index(
                fields=["observation_date"]
            ),
        ]

    def __str__(self):
        return (
            f"APIx @ {self.observation_date}: "
            f"{self.index_value:.1f}"
        )