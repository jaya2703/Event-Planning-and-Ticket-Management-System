"""
Bookings Views
==============
Handles ticket booking, cancellation, QR generation, PDF download, and check-in.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
import qrcode
import io
import os
from django.conf import settings as django_settings
from .models import Booking, Waitlist
from events.models import Event
from accounts.models import Notification


def generate_qr_code(booking):
    """
    Generate a QR code image for a booking.
    The QR code contains the booking ID which can be scanned to verify the ticket.
    """
    # The data inside the QR code
    qr_data = f"EVENTPRO|B:{booking.booking_id}|E:{booking.event_id}|U:{booking.user_id}"
    
    # Create QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    # Create image from QR code
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save it to a file
    qr_filename = f"qr_{booking.booking_id}.png"
    qr_path = os.path.join(django_settings.MEDIA_ROOT, 'qr_codes', qr_filename)
    
    os.makedirs(os.path.dirname(qr_path), exist_ok=True)
    img.save(qr_path)
    
    # Return just the filename (relative path for storing in model)
    return f"qr_codes/{qr_filename}"


@login_required
def book_ticket(request, event_id):
    """
    Book a ticket for an event.
    If event is full, automatically join waitlist.
    """
    if request.user.role != 'user':
        messages.error(request, "Only attendees can book events.")
        return redirect('accounts:dashboard')

    event = get_object_or_404(Event, id=event_id)
    
    # Check if user already has a confirmed booking
    existing_booking = Booking.objects.filter(
        user=request.user, event=event, status__in=['confirmed', 'pending_payment']
    ).first()
    
    if existing_booking:
        messages.warning(request, "You already have a booking for this event.")
        return redirect('bookings:detail', booking_id=existing_booking.id)
    
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        
        # Validate quantity
        if quantity < 1 or quantity > 5:
            messages.error(request, "You can book between 1 and 5 tickets.")
            return redirect('events:detail', event_id=event.id)
        
        # Check availability
        if event.tickets_available >= quantity:
            tier_id = request.POST.get('ticket_tier')
            ticket_tier = None
            if tier_id:
                from events.models import TicketTier
                ticket_tier = TicketTier.objects.filter(id=tier_id, event=event, is_active=True).first()
                if ticket_tier and ticket_tier.available < quantity:
                    messages.error(request, "Not enough tickets available for this tier.")
                    return redirect('events:detail', event_id=event.id)

            booking = Booking.objects.create(
                user=request.user,
                event=event,
                quantity=quantity,
                ticket_tier=ticket_tier,
                status='pending_payment' if (ticket_tier and ticket_tier.price > 0) or event.ticket_price > 0 else 'confirmed'
            )

            if booking.status == 'confirmed':
                qr_path = generate_qr_code(booking)
                booking.qr_code = qr_path
                booking.save()
                from accounts.services import notify
                notify(request.user, f"Your booking for '{event.title}' is confirmed!", 'booking_success',
                       link=f'/bookings/{booking.id}/')
                messages.success(request, "Booking confirmed!")
                return redirect('bookings:detail', booking_id=booking.id)

            from accounts.services import notify
            notify(request.user, f"Complete payment for '{event.title}' to confirm your booking.", 'payment_success',
                   link=f'/payments/process/{booking.id}/')
            return redirect('payments:process', booking_id=booking.id)
        
        else:
            # Event is full - add to waitlist
            # Check if already on waitlist
            if Waitlist.objects.filter(user=request.user, event=event).exists():
                messages.warning(request, "You're already on the waitlist for this event.")
            else:
                # Get current waitlist count to determine position
                position = Waitlist.objects.filter(event=event).count() + 1
                waitlist_entry = Waitlist.objects.create(
                    user=request.user,
                    event=event,
                    quantity=quantity,
                    position=position
                )
                
                # Create booking with waitlisted status
                booking = Booking.objects.create(
                    user=request.user,
                    event=event,
                    quantity=quantity,
                    status='waitlisted',
                    waitlist_position=position
                )
                
                Notification.objects.create(
                    user=request.user,
                    message=f"📋 You've been added to the waitlist for '{event.title}'. Position: #{position}"
                )
                
                messages.info(request, f"Event is full! You've been added to the waitlist at position #{position}. We'll notify you if a spot opens up.")
            
            return redirect('events:detail', event_id=event.id)
    
    context = {
        'event': event,
        'available_tickets': event.tickets_available,
    }
    return render(request, 'bookings/book_ticket.html', context)


@login_required
def booking_detail(request, booking_id):
    """View details of a single booking"""
    booking = get_object_or_404(Booking, id=booking_id)
    if booking.user != request.user and request.user.role != 'admin':
        messages.error(request, "You do not have permission to view this booking.")
        return redirect('accounts:dashboard')
    return render(request, 'bookings/booking_detail.html', {
        'booking': booking,
        'is_admin_view': request.user.role == 'admin',
    })


@login_required
def booking_history(request):
    """List all bookings for the current user"""
    if request.user.role == 'admin':
        return redirect('accounts:manage_bookings')
    if request.user.role != 'user':
        messages.error(request, "Booking history is only available for attendees.")
        return redirect('accounts:dashboard')
    bookings = Booking.objects.filter(user=request.user).order_by('-booked_at')
    return render(request, 'bookings/booking_history.html', {'bookings': bookings})


@login_required
def cancel_booking(request, booking_id):
    """
    Cancel a booking.
    After cancellation, check if anyone is on the waitlist and promote them.
    """
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    if booking.status != 'confirmed':
        messages.error(request, "Only confirmed bookings can be cancelled.")
        return redirect('bookings:detail', booking_id=booking.id)
    
    if request.method == 'POST':
        booking.status = 'cancelled'
        booking.save()
        
        # Notify user of cancellation
        refund_note = ''
        from payments.models import Payment
        if booking.total_price > 0 and Payment.objects.filter(booking=booking, status='success').exists():
            refund_note = ' You can request a refund from My Bookings.'
        Notification.objects.create(
            user=request.user,
            message=f"❌ Your booking for '{booking.event.title}' has been cancelled.{refund_note}"
        )
        
        # --- WAITLIST AUTO UPGRADE ---
        # Check if anyone is waiting for this event
        promote_from_waitlist(booking.event, booking.quantity)
        
        messages.success(request, "Booking cancelled successfully.")
        return redirect('accounts:user_dashboard')
    
    return render(request, 'bookings/cancel_confirm.html', {'booking': booking})


def promote_from_waitlist(event, freed_quantity):
    """
    Waitlist Auto Upgrade Feature:
    When a booking is cancelled, automatically promote the first person on the waitlist.
    """
    # Find the first person on the waitlist (lowest position number)
    first_in_line = Waitlist.objects.filter(event=event).order_by('position').first()
    
    if first_in_line and freed_quantity >= first_in_line.quantity:
        user_to_promote = first_in_line.user
        
        # Find their waitlisted booking
        waitlisted_booking = Booking.objects.filter(
            user=user_to_promote,
            event=event,
            status='waitlisted'
        ).first()
        
        if waitlisted_booking:
            waitlisted_booking.status = 'pending_payment' if event.ticket_price > 0 else 'confirmed'
            waitlisted_booking.waitlist_position = None

            if waitlisted_booking.status == 'confirmed':
                qr_path = generate_qr_code(waitlisted_booking)
                waitlisted_booking.qr_code = qr_path
            waitlisted_booking.save()

            first_in_line.delete()

            from accounts.services import notify
            msg = (
                f"Great news! A spot opened for '{event.title}'. "
                + ("Complete payment to confirm your booking." if waitlisted_booking.status == 'pending_payment'
                   else "Your booking is now confirmed!")
            )
            notify(user_to_promote, msg, 'waitlist_upgraded',
                   link=f'/payments/process/{waitlisted_booking.id}/' if waitlisted_booking.status == 'pending_payment'
                   else f'/bookings/{waitlisted_booking.id}/')
            
            # Re-number remaining waitlist positions
            remaining = Waitlist.objects.filter(event=event).order_by('position')
            for i, entry in enumerate(remaining, start=1):
                entry.position = i
                entry.save()


@login_required
def download_ticket_pdf(request, booking_id):
    """
    Generate and download a PDF ticket.
    The PDF includes: event info, user info, booking ID, QR code.
    """
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import cm
    
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    if booking.status != 'confirmed':
        messages.error(request, "Ticket PDF is only available for confirmed bookings.")
        return redirect('bookings:detail', booking_id=booking.id)
    
    # Create a PDF in memory (we don't save it, just send it to browser)
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # --- PDF DESIGN ---
    # Header background
    p.setFillColor(HexColor('#6c5ce7'))
    p.rect(0, height - 120, width, 120, fill=True, stroke=False)
    
    # Title
    p.setFillColor(HexColor('#ffffff'))
    p.setFont("Helvetica-Bold", 28)
    p.drawString(40, height - 60, "EventPro")
    p.setFont("Helvetica", 14)
    p.drawString(40, height - 85, "E-TICKET / BOARDING PASS")
    
    # Booking ID
    p.setFillColor(HexColor('#2d3436'))
    p.setFont("Helvetica-Bold", 18)
    p.drawString(40, height - 160, booking.event.title)
    
    p.setFont("Helvetica", 12)
    p.setFillColor(HexColor('#636e72'))
    p.drawString(40, height - 185, f"Booking ID: {str(booking.booking_id).upper()[:16]}")
    
    # Divider
    p.setStrokeColor(HexColor('#dfe6e9'))
    p.line(40, height - 200, width - 40, height - 200)
    
    # Event details
    p.setFillColor(HexColor('#2d3436'))
    p.setFont("Helvetica-Bold", 11)
    details = [
        ("Event", booking.event.title),
        ("Date", str(booking.event.date)),
        ("Time", str(booking.event.time)),
        ("Venue", booking.event.venue),
        ("Ticket Holder", f"{booking.user.first_name} {booking.user.last_name}"),
        ("Email", booking.user.email),
        ("Quantity", str(booking.quantity)),
        ("Total Paid", f"INR {booking.total_price}"),
        ("Status", booking.status.upper()),
    ]
    
    y_pos = height - 230
    for label, value in details:
        p.setFont("Helvetica-Bold", 10)
        p.setFillColor(HexColor('#636e72'))
        p.drawString(40, y_pos, f"{label}:")
        p.setFont("Helvetica", 10)
        p.setFillColor(HexColor('#2d3436'))
        p.drawString(160, y_pos, str(value))
        y_pos -= 22
    
    # QR Code (if available)
    if booking.qr_code:
        qr_full_path = os.path.join(django_settings.MEDIA_ROOT, str(booking.qr_code))
        if os.path.exists(qr_full_path):
            p.drawImage(qr_full_path, width - 170, height - 380, width=130, height=130)
            p.setFont("Helvetica", 8)
            p.setFillColor(HexColor('#636e72'))
            p.drawString(width - 170, height - 395, "Scan for verification")
    
    # Footer
    p.setFillColor(HexColor('#f8f9fa'))
    p.rect(0, 0, width, 60, fill=True, stroke=False)
    p.setFillColor(HexColor('#636e72'))
    p.setFont("Helvetica", 9)
    p.drawString(40, 35, "This is an official e-ticket generated by EventPro. Please carry a printout or show on your mobile.")
    p.drawString(40, 20, f"Generated on: {timezone.now().strftime('%d %B %Y %H:%M')}")
    
    p.save()
    
    # Send PDF as download
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="ticket_{str(booking.booking_id)[:8]}.pdf"'
    return response


@login_required
def verify_checkin(request, booking_uuid):
    """
    QR Code Verification & Check-in.
    When organizer scans QR code, this view marks the user as checked in.
    """
    if request.user.role not in ['organizer', 'admin']:
        messages.error(request, "Only organizers and admins can verify tickets.")
        return redirect('home')
    
    try:
        booking = Booking.objects.get(booking_id=booking_uuid)
    except Booking.DoesNotExist:
        messages.error(request, "Invalid QR code. Booking not found.")
        return redirect('accounts:dashboard')
    
    if booking.status != 'confirmed':
        messages.error(request, f"This ticket is {booking.status}. Cannot check in.")
        return render(request, 'bookings/checkin_result.html', {'booking': booking, 'success': False})
    
    if booking.is_checked_in:
        messages.warning(request, "⚠️ This ticket has already been used! Possible duplicate entry attempt.")
        return render(request, 'bookings/checkin_result.html', {'booking': booking, 'success': False, 'duplicate': True})
    
    # Mark as checked in
    booking.is_checked_in = True
    booking.checked_in_at = timezone.now()
    booking.status = 'attended'
    booking.save()
    
    messages.success(request, f"✅ Check-in successful for {booking.user.get_full_name()}!")
    return render(request, 'bookings/checkin_result.html', {'booking': booking, 'success': True})


@login_required
def scan_qr(request):
    """Page where organizer can scan QR codes"""
    if request.user.role != 'organizer':
        messages.error(request, "Access denied.")
        return redirect('accounts:dashboard')
    
    if request.method == 'POST':
        qr_data = request.POST.get('qr_data', '')
        # QR data format: "EVENTPRO-BOOKING-<uuid>"
        if qr_data.startswith('EVENTPRO-BOOKING-'):
            booking_uuid = qr_data.replace('EVENTPRO-BOOKING-', '')
            return redirect('bookings:verify_checkin', booking_uuid=booking_uuid)
        if qr_data.startswith('EVENTPRO|'):
            parts = dict(p.split(':', 1) for p in qr_data.split('|')[1:] if ':' in p)
            booking_uuid = parts.get('B', '')
            if booking_uuid:
                return redirect('bookings:verify_checkin', booking_uuid=booking_uuid)
        else:
            messages.error(request, "Invalid QR code format.")
    
    return render(request, 'bookings/scan_qr.html')
