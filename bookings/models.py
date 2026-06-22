"""
Bookings Models
===============
Handles ticket bookings, waitlists, and check-ins.
"""
import uuid
from django.db import models
from django.conf import settings
from events.models import Event


class Booking(models.Model):
    """
    Represents a ticket booking by a user for an event.
    """
    STATUS_CHOICES = [
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('waitlisted', 'Waitlisted'),
        ('attended', 'Attended'),
    ]
    
    # Unique booking ID (like a ticket number)
    booking_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    
    # Who booked and which event
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookings')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='bookings')
    
    # How many tickets
    quantity = models.PositiveIntegerField(default=1)
    
    # Total price = ticket_price * quantity
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Booking status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='confirmed')
    
    # QR Code image (generated when booking is created)
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True)
    
    # Check-in tracking (for crowd density feature)
    is_checked_in = models.BooleanField(default=False)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    
    # When the booking was made
    booked_at = models.DateTimeField(auto_now_add=True)
    
    # Waitlist position (if waitlisted)
    waitlist_position = models.PositiveIntegerField(null=True, blank=True)
    
    def __str__(self):
        return f"Booking #{str(self.booking_id)[:8]} - {self.user.username} -> {self.event.title}"
    
    def save(self, *args, **kwargs):
        """Override save to calculate total price automatically"""
        self.total_price = self.event.ticket_price * self.quantity
        super().save(*args, **kwargs)

    @property
    def is_refund_eligible(self):
        if self.status != 'cancelled' or self.total_price <= 0:
            return False
        from payments.models import Payment
        return Payment.objects.filter(
            booking=self, status='success', is_refunded=False
        ).exists()

    @property
    def is_refunded_booking(self):
        from payments.models import Payment
        return Payment.objects.filter(booking=self, is_refunded=True).exists()


class Waitlist(models.Model):
    """
    Waitlist Auto Upgrade Feature:
    When event is full, users join waitlist.
    When a booking is cancelled, the first person on waitlist gets promoted.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='waitlist')
    quantity = models.PositiveIntegerField(default=1)
    position = models.PositiveIntegerField()  # Position in the queue
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['position']  # First in, first out
        unique_together = ['user', 'event']
    
    def __str__(self):
        return f"Waitlist #{self.position} - {self.user.username} for {self.event.title}"
