"""
Payments Views
==============
Mock payment flow: Process -> Success/Failed
No real money, just simulation for learning purposes.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
import random
from .models import Payment
from bookings.models import Booking
from accounts.models import Notification


@login_required
def process_payment(request, booking_id):
    """
    Mock payment processing page.
    Shows a payment form and simulates payment.
    """
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    # If already paid, go to success
    if hasattr(booking, 'payment') and booking.payment.status == 'success':
        return redirect('payments:success', booking_id=booking.id)
    
    # If ticket is free (price = 0), skip payment
    if booking.total_price == 0:
        Payment.objects.create(
            booking=booking,
            amount=0,
            status='success',
            paid_at=timezone.now()
        )
        return redirect('payments:success', booking_id=booking.id)
    
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', 'card')
        
        # Create payment record
        payment = Payment.objects.create(
            booking=booking,
            amount=booking.total_price,
            payment_method=payment_method,
            status='pending'
        )
        
        # --- MOCK PAYMENT SIMULATION ---
        # In a real system, this is where you'd call Razorpay/Stripe API
        # For now, we simulate: 90% success rate
        roll = random.randint(1, 10)
        
        if roll <= 9:  # 90% success
            payment.status = 'success'
            payment.paid_at = timezone.now()
            payment.mock_card_last4 = '4242'
            payment.save()
            
            Notification.objects.create(
                user=request.user,
                message=f"💳 Payment of INR {booking.total_price} successful for '{booking.event.title}'"
            )
            
            return redirect('payments:success', booking_id=booking.id)
        else:
            payment.status = 'failed'
            payment.save()
            
            # Cancel the booking if payment failed
            booking.status = 'cancelled'
            booking.save()
            
            return redirect('payments:failed', booking_id=booking.id)
    
    context = {
        'booking': booking,
        'event': booking.event,
    }
    return render(request, 'payments/process.html', context)


@login_required
def payment_success(request, booking_id):
    """Payment success page"""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    payment = getattr(booking, 'payment', None)
    return render(request, 'payments/success.html', {'booking': booking, 'payment': payment})


@login_required
def payment_failed(request, booking_id):
    """Payment failed page"""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    return render(request, 'payments/failed.html', {'booking': booking})
