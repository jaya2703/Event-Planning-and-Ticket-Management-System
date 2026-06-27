"""
Payments Views
==============
Mock payment flow: Process -> Success/Failed
No real money, just simulation for learning purposes.
"""
import base64
import io
import random
import qrcode
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import Payment
from bookings.models import Booking
from bookings.views import generate_qr_code, promote_from_waitlist
from accounts.services import notify


def _confirm_booking_after_payment(booking):
    """Mark booking confirmed and generate QR ticket."""
    if booking.status in ('pending_payment', 'waitlisted'):
        booking.status = 'confirmed'
        if not booking.qr_code:
            booking.qr_code = generate_qr_code(booking)
        booking.save()

MOCK_UPI_ID = 'eventpro@paytm'


def build_upi_payment_qr(booking):
    """Build a scannable UPI payment QR (mock merchant)."""
    amount = f"{booking.total_price:.2f}"
    note = f"EventPro {booking.event.title}"[:40]
    upi_payload = (
        f"upi://pay?pa={MOCK_UPI_ID}&pn=EventPro"
        f"&am={amount}&cu=INR&tn={note}"
    )

    qr = qrcode.QRCode(version=None, box_size=8, border=2)
    qr.add_data(upi_payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    data_uri = 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii')
    return data_uri, upi_payload


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
        _confirm_booking_after_payment(booking)
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
            card_number = request.POST.get('card_number', '').replace(' ', '')
            if payment_method == 'card' and len(card_number) >= 4:
                payment.mock_card_last4 = card_number[-4:]
            else:
                payment.mock_card_last4 = '4242'
            payment.save()
            _confirm_booking_after_payment(booking)
            notify(request.user, f"Payment of ₹{booking.total_price} successful for '{booking.event.title}'",
                   'payment_success', link=f'/bookings/{booking.id}/')
            notify(request.user, f"Your ticket for '{booking.event.title}' is confirmed!", 'booking_success',
                   link=f'/bookings/{booking.id}/')
            return redirect('payments:success', booking_id=booking.id)
        else:
            payment.status = 'failed'
            payment.save()
            qty = booking.quantity
            event = booking.event
            booking.status = 'cancelled'
            booking.save()
            promote_from_waitlist(event, qty)
            notify(request.user, f"Payment failed for '{booking.event.title}'. Booking cancelled.", 'payment_failed')
            return redirect('payments:failed', booking_id=booking.id)
    
    upi_qr_image, upi_payload = build_upi_payment_qr(booking)
    context = {
        'booking': booking,
        'event': booking.event,
        'upi_qr_image': upi_qr_image,
        'mock_upi_id': MOCK_UPI_ID,
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


@login_required
def request_refund(request, booking_id):
    """Mock refund request for cancelled paid bookings."""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    if not booking.is_refund_eligible:
        messages.error(request, "This booking is not eligible for a refund.")
        return redirect('bookings:detail', booking_id=booking.id)

    payment = booking.payment

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        from bookings.models import Refund
        Refund.objects.create(
            booking=booking,
            amount=payment.amount,
            reason=reason,
            status='pending'
        )
        notify(request.user, f"Refund request submitted for '{booking.event.title}'", 'refund', link=f'/bookings/{booking.id}/')
        messages.success(request, f"Refund request of ₹{payment.amount} has been submitted for approval.")
        return redirect('bookings:detail', booking_id=booking.id)

    context = {
        'booking': booking,
        'event': booking.event,
        'payment': payment,
    }
    return render(request, 'payments/refund.html', context)


@login_required
def refund_success(request, booking_id):
    """Refund success confirmation page."""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    payment = getattr(booking, 'payment', None)
    if not payment or not payment.is_refunded:
        return redirect('bookings:detail', booking_id=booking.id)
    return render(request, 'payments/refund_success.html', {
        'booking': booking,
        'payment': payment,
    })


@login_required
def approve_refund(request, refund_id):
    """Approve or reject a pending refund request (finance/organizer/admin role)."""
    if request.user.role not in ['organizer', 'admin', 'finance']:
        messages.error(request, "Permission denied.")
        return redirect('accounts:dashboard')
    
    from bookings.models import Refund
    refund = get_object_or_404(Refund, id=refund_id)
    payment = refund.booking.payment
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve':
            refund.status = 'approved'
            refund.processed_at = timezone.now()
            refund.save()
            
            payment.is_refunded = True
            payment.refunded_at = timezone.now()
            payment.save()
            
            notify(refund.booking.user, f"Your refund request for '{refund.booking.event.title}' has been approved.", 'refund')
            messages.success(request, f"Refund request approved and processed successfully.")
        else:
            refund.status = 'rejected'
            refund.processed_at = timezone.now()
            refund.save()
            notify(refund.booking.user, f"Your refund request for '{refund.booking.event.title}' was rejected.", 'refund')
            messages.warning(request, f"Refund request was rejected.")
            
    return redirect('accounts:dashboard')


@login_required
def request_payout(request):
    """Request a payout for organization revenue (organizer/finance)."""
    if request.user.role not in ['organizer', 'finance']:
        messages.error(request, "Permission denied.")
        return redirect('accounts:dashboard')
        
    org = request.user.organization
    if not org:
        messages.error(request, "No organization profile associated.")
        return redirect('accounts:dashboard')
        
    if request.method == 'POST':
        amount = float(request.POST.get('amount', 0))
        bank_details = request.POST.get('bank_details', '').strip()
        
        if amount <= 0 or not bank_details:
            messages.error(request, "Invalid payout amount or bank details.")
        else:
            from .models import Payout
            Payout.objects.create(
                organization=org,
                amount=amount,
                bank_details=bank_details,
                status='pending'
            )
            messages.success(request, f"Payout request of ₹{amount} submitted successfully.")
            
    return redirect('accounts:dashboard')


@login_required
def download_invoice(request, booking_id):
    """Generate a printable HTML invoice for the booking."""
    booking = get_object_or_404(Booking, id=booking_id)
    if booking.user != request.user and request.user.role != 'admin':
        messages.error(request, "Access denied.")
        return redirect('accounts:dashboard')
        
    payment = getattr(booking, 'payment', None)
    return render(request, 'payments/invoice.html', {
        'booking': booking,
        'payment': payment,
        'invoice_number': f"INV-{booking.booking_id.hex[:8].upper()}"
    })

