"""
Payments Models
===============
Mock payment system - simulates real payment without actual money.
"""
import uuid
from django.db import models
from django.conf import settings
from bookings.models import Booking


class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]
    
    payment_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='payment')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Mock payment method
    payment_method = models.CharField(max_length=50, default='card')
    
    # Mock card/UPI details (not real, just for simulation)
    mock_card_last4 = models.CharField(max_length=4, blank=True, null=True)
    
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Payment {str(self.payment_id)[:8]} - {self.status} - INR {self.amount}"
