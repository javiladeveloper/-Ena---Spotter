from django.db import models
from django.db.models import Index


class FuelStation(models.Model):
    """Model representing a fuel station with pricing information."""

    opis_id = models.IntegerField(db_index=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100, db_index=True)
    state = models.CharField(max_length=2, db_index=True)
    rack_id = models.IntegerField()
    retail_price = models.DecimalField(max_digits=10, decimal_places=8)

    # Coordinates for distance calculations
    latitude = models.FloatField(null=True, blank=True, db_index=True)
    longitude = models.FloatField(null=True, blank=True, db_index=True)

    class Meta:
        indexes = [
            Index(fields=['state', 'retail_price']),
            Index(fields=['latitude', 'longitude']),
        ]
        ordering = ['retail_price']

    def __str__(self):
        return f"{self.name} - {self.city}, {self.state} (${self.retail_price}/gal)"

    @property
    def full_address(self):
        return f"{self.address}, {self.city}, {self.state}"
