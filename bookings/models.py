"""
Bookings Models
===============
Handles ticket bookings, waitlists, and check-ins.
"""
import uuid
from django.db import models
from django.conf import settings
from events.models import Event


class PromoCode(models.Model):
    """
    Promo codes for ticket discount logic.
    """
    organization = models.ForeignKey('accounts.Organization', on_delete=models.CASCADE, related_name='promo_codes', null=True, blank=True)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='promo_codes', null=True, blank=True)
    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=20, choices=[('percentage', 'Percentage'), ('flat', 'Flat')], default='percentage')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    active = models.BooleanField(default=True)
    max_uses = models.PositiveIntegerField(default=100)
    used_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.code


class Booking(models.Model):
    """
    Represents a ticket booking by a user for an event.
    """
    STATUS_CHOICES = [
        ('pending_payment', 'Pending Payment'),
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
    ticket_tier = models.ForeignKey(
        'events.TicketTier', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='bookings'
    )
    
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
    
    # Attendee SaaS extensions
    attendee_notes = models.TextField(blank=True, default='')
    promo_code = models.ForeignKey(PromoCode, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings')
    badge_printed = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Booking #{str(self.booking_id)[:8]} - {self.user.username} -> {self.event.title}"
    
    def save(self, *args, **kwargs):
        if self.ticket_tier:
            price = self.ticket_tier.price
        else:
            price = self.event.ticket_price
        
        base_total = price * self.quantity
        if self.promo_code:
            if self.promo_code.discount_type == 'percentage':
                discount = base_total * (self.promo_code.discount_value / 100)
            else:
                discount = self.promo_code.discount_value
            self.total_price = max(0, base_total - discount)
        else:
            self.total_price = base_total
        super().save(*args, **kwargs)

    @property
    def is_refund_eligible(self):
        if self.status != 'cancelled' or self.total_price <= 0:
            return False
        from payments.models import Payment
        return Payment.objects.filter(
            booking=self, status='success', is_refunded=False
        ).exists() and not hasattr(self, 'refund')

    @property
    def is_refunded_booking(self):
        from payments.models import Payment
        return Payment.objects.filter(booking=self, is_refunded=True).exists() or (hasattr(self, 'refund') and self.refund.status == 'approved')


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


class Refund(models.Model):
    """SaaS refund request processing"""
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='refund')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')],
        default='pending'
    )
    reason = models.TextField(blank=True, null=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Refund for Booking #{str(self.booking.booking_id)[:8]} - {self.status}"

