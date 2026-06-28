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
from datetime import timedelta
from .models import Booking, Waitlist
from events.models import Event
from accounts.models import Notification


import hmac
import hashlib
from django.db.models import Sum

def generate_secure_token(booking_id, event_id, user_id):
    key = django_settings.SECRET_KEY.encode('utf-8')
    msg = f"{booking_id}-{event_id}-{user_id}".encode('utf-8')
    return hmac.new(key, msg, hashlib.sha256).hexdigest()[:16]

def parse_and_verify_qr(qr_data):
    """
    Parses the QR string and verifies the token.
    Returns (is_valid, booking, reason)
    reason can be: 'invalid', 'already_used', 'approved'
    """
    if not qr_data or not qr_data.startswith("EVENTPRO|"):
        # Support fallback to EVENTPRO-BOOKING-<uuid> format for backward compatibility
        if qr_data.startswith('EVENTPRO-BOOKING-'):
            uuid_str = qr_data.replace('EVENTPRO-BOOKING-', '')
            try:
                booking = Booking.objects.get(booking_id=uuid_str)
                if booking.is_checked_in:
                    return True, booking, 'already_used'
                if booking.status not in ['confirmed', 'attended']:
                    return False, None, 'invalid'
                return True, booking, 'approved'
            except Exception:
                return False, None, 'invalid'
        return False, None, 'invalid'
    
    try:
        parts = dict(p.split(':', 1) for p in qr_data.split('|')[1:] if ':' in p)
        ticket_id = parts.get('T')
        booking_id = parts.get('B')
        event_id = parts.get('E')
        user_id = parts.get('U')
        token = parts.get('K')
        
        if not all([ticket_id, booking_id, event_id, user_id, token]):
            return False, None, 'invalid'
            
        # Verify token
        expected_token = generate_secure_token(booking_id, event_id, user_id)
        if not hmac.compare_digest(token, expected_token):
            return False, None, 'invalid'
            
        # Fetch booking
        booking = Booking.objects.get(booking_id=booking_id)
        
        # Verify matching IDs
        if str(booking.id) != str(ticket_id) or str(booking.event_id) != str(event_id) or str(booking.user_id) != str(user_id):
            return False, None, 'invalid'
            
        # Check if already checked in
        if booking.is_checked_in:
            return True, booking, 'already_used'
            
        # Check booking status (must not be cancelled)
        if booking.status not in ['confirmed', 'attended']:
            return False, None, 'invalid'
            
        return True, booking, 'approved'
        
    except Exception:
        return False, None, 'invalid'

def generate_qr_code(booking):
    """
    Generate a QR code image for a booking.
    The QR code contains ticketId, bookingId, eventId, userId, and secure token.
    """
    token = generate_secure_token(booking.booking_id, booking.event_id, booking.user_id)
    # Format: EVENTPRO|T:{ticketId}|B:{bookingId}|E:{eventId}|U:{userId}|K:{token}
    qr_data = f"EVENTPRO|T:{booking.id}|B:{booking.booking_id}|E:{booking.event_id}|U:{booking.user_id}|K:{token}"
    
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
    cleanup_expired_reservations()
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
                if not ticket_tier:
                    messages.error(request, "Invalid ticket tier.")
                    return redirect('events:detail', event_id=event.id)
                if ticket_tier.available < quantity:
                    messages.error(request, "Not enough tickets available for this tier.")
                    return redirect('events:detail', event_id=event.id)
                
                # SaaS tier limits & validation
                if quantity > ticket_tier.ticket_limit_per_user:
                    messages.error(request, f"This tier has a limit of {ticket_tier.ticket_limit_per_user} tickets per booking.")
                    return redirect('events:detail', event_id=event.id)
                if ticket_tier.tier_type == 'group' and quantity < ticket_tier.group_size:
                    messages.error(request, f"Group tickets require a minimum purchase of {ticket_tier.group_size} tickets.")
                    return redirect('events:detail', event_id=event.id)
                if ticket_tier.early_bird_deadline and ticket_tier.early_bird_deadline < timezone.now():
                    messages.error(request, "Early Bird sales have ended for this event.")
                    return redirect('events:detail', event_id=event.id)
                if ticket_tier.availability_timer and ticket_tier.availability_timer < timezone.now():
                    messages.error(request, "This ticket tier is no longer available.")
                    return redirect('events:detail', event_id=event.id)

            # Promo Code validation
            promo_code = None
            promo_code_str = request.POST.get('promo_code', '').strip().upper()
            if promo_code_str:
                from .models import PromoCode
                promo = PromoCode.objects.filter(code=promo_code_str, active=True, valid_from__lte=timezone.now(), valid_to__gte=timezone.now()).first()
                if promo:
                    if promo.used_count < promo.max_uses:
                        promo_code = promo
                    else:
                        messages.warning(request, "Promo code usage limit reached.")
                else:
                    messages.warning(request, "Invalid or expired promo code.")

            booking = Booking.objects.create(
                user=request.user,
                event=event,
                quantity=quantity,
                ticket_tier=ticket_tier,
                promo_code=promo_code,
                status='confirmed'
            )
            
            # Recalculate based on price (after promo discount)
            if booking.total_price > 0:
                booking.status = 'pending_payment'
                booking.save()
            else:
                booking.status = 'confirmed'
                booking.save()

            if promo_code:
                promo_code.used_count += 1
                promo_code.save()

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
    cleanup_expired_reservations()
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


def cleanup_expired_reservations():
    """
    Checks all bookings with status='pending_payment' where payment_deadline has passed.
    Releases their reservation (sets status='cancelled'), notifies the user, and promotes the next.
    Also handles payment reminders before expiry (e.g. 5 minutes before deadline).
    """
    from .models import Booking
    from django.utils import timezone
    from datetime import timedelta
    from accounts.services import notify

    now = timezone.now()

    # 1. Handle Expirations
    expired = Booking.objects.filter(status='pending_payment', payment_deadline__lt=now)
    for b in expired:
        b.status = 'cancelled'
        b.save()
        notify(
            b.user,
            f"Your ticket reservation for '{b.event.title}' has expired because payment was not completed within the time limit.",
            'payment_failed'
        )
        # Notify waitlist
        promote_from_waitlist(b.event, b.quantity)

    # 2. Handle Reminders (if deadline is less than 5 minutes away and reminder not sent)
    reminders = Booking.objects.filter(
        status='pending_payment',
        payment_deadline__gte=now,
        payment_deadline__lt=now + timedelta(minutes=5),
        reminder_sent=False
    )
    for b in reminders:
        b.reminder_sent = True
        b.save()
        notify(
            b.user,
            f"Reminder: You have less than 5 minutes to complete payment for your reservation at '{b.event.title}'!",
            'event_reminder',
            link=f'/payments/process/{b.id}/'
        )


def promote_from_waitlist(event, freed_quantity):
    """
    Waitlist Promotion:
    When a booking is cancelled, automatically select the first person on the waitlist.
    Handles enabled check, auto vs manual approval, reservation deadline.
    """
    if not event.waitlist_enabled:
        return

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
            from accounts.services import notify
            first_in_line.delete()
            
            # Re-number remaining waitlist positions
            remaining = Waitlist.objects.filter(event=event).order_by('position')
            for i, entry in enumerate(remaining, start=1):
                entry.position = i
                entry.save()

            if event.auto_approve_waitlist:
                # Automatic approval
                waitlisted_booking.status = 'pending_payment' if event.ticket_price > 0 else 'confirmed'
                waitlisted_booking.waitlist_position = None
                
                if waitlisted_booking.status == 'pending_payment':
                    waitlisted_booking.payment_deadline = timezone.now() + timedelta(minutes=event.reservation_timeout)
                    waitlisted_booking.reminder_sent = False
                    waitlisted_booking.save()
                    
                    msg = f"Great news! A spot opened for '{event.title}'. Complete payment within {event.reservation_timeout} minutes to confirm your booking."
                    notify(user_to_promote, msg, 'waitlist_upgraded', link=f'/payments/process/{waitlisted_booking.id}/')
                else:
                    # Free event
                    qr_path = generate_qr_code(waitlisted_booking)
                    waitlisted_booking.qr_code = qr_path
                    waitlisted_booking.save()
                    
                    msg = f"Great news! Your booking for '{event.title}' is confirmed!"
                    notify(user_to_promote, msg, 'booking_success', link=f'/bookings/{waitlisted_booking.id}/')
            else:
                # Manual approval required
                waitlisted_booking.status = 'pending_approval'
                waitlisted_booking.waitlist_position = None
                waitlisted_booking.save()
                
                # Notify User
                msg_user = f"You have been selected from the waitlist for '{event.title}'. Pending organizer approval."
                notify(user_to_promote, msg_user, 'waitlist_upgraded')
                
                # Notify Organizer
                msg_org = f"Attendee {user_to_promote.username} is promoted from waitlist for '{event.title}' and requires approval."
                notify(event.organizer, msg_org, 'waitlist_upgraded', link=f'/bookings/approve-waitlist/{waitlisted_booking.id}/')


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
    p.drawString(40, height - 185, f"Ticket Code: {booking.ticket_code or 'N/A'}")
    
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
        ("Ticket Code", booking.ticket_code or "N/A"),
        ("User Code", booking.user.verification_code or "N/A"),
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


def verify_ticket_or_user(scan_data, event, scanner, gate="Main Gate", device="Web Scanner"):
    """
    Validates a ticket scan (QR string, UUID, EVT code, or USR code).
    Returns (result_status, message, booking_obj, user_obj, warnings, scan_log_obj, prev_scans)
    """
    from bookings.models import Booking, TicketScanLog
    from accounts.models import CustomUser
    from volunteers.models import EventVolunteer
    from django.utils import timezone
    
    scan_data = scan_data.strip()
    booking = None
    user = None
    result = "rejected"
    reason = ""
    warnings = []
    
    # 1. Try parsing QR string
    if scan_data.startswith("EVENTPRO|"):
        try:
            parts = dict(p.split(':', 1) for p in scan_data.split('|')[1:] if ':' in p)
            booking_uuid = parts.get('B')
            booking = Booking.objects.select_related('user', 'event', 'ticket_tier').filter(booking_id=booking_uuid).first()
        except Exception:
            pass
            
    # 2. Try lookup by booking UUID
    if not booking:
        try:
            booking = Booking.objects.select_related('user', 'event', 'ticket_tier').filter(booking_id=scan_data).first()
        except Exception:
            pass
            
    # 3. Try lookup by ticket_code (EVT-...)
    if not booking and scan_data.startswith("EVT-"):
        booking = Booking.objects.select_related('user', 'event', 'ticket_tier').filter(ticket_code=scan_data).first()
        
    # 4. Try lookup by user_verification_code (USR-...)
    if not booking:
        user_code = scan_data
        user = CustomUser.objects.filter(verification_code=user_code).first()
        if user:
            # Check if this user has a booking for the event
            booking = Booking.objects.select_related('user', 'event', 'ticket_tier').filter(user=user, event=event).first()

    # Now we evaluate the booking or user
    if booking:
        user = booking.user
        # Verify event match
        if booking.event != event:
            reason = f"Ticket belongs to different event: '{booking.event.title}'"
            warnings.append("WRONG_EVENT")
        elif booking.status == 'cancelled':
            reason = "Ticket has been cancelled."
            warnings.append("CANCELLED")
        elif booking.status == 'waitlisted':
            reason = "User is still on the waitlist."
            warnings.append("WAITLISTED")
        elif booking.status in ['pending_payment', 'pending_approval']:
            reason = f"Booking status is {booking.status}."
            warnings.append("PENDING_PAYMENT" if booking.status == 'pending_payment' else "PENDING_APPROVAL")
        elif booking.is_checked_in:
            reason = "Ticket already scanned / Checked-in."
            warnings.append("ALREADY_SCANNED")
            result = "rejected"
        else:
            # Success check-in!
            result = "success"
            booking.is_checked_in = True
            booking.checked_in_at = timezone.now()
            booking.status = 'attended'
            booking.save()
            
    elif user:
        # Check if the user is staff/speaker/VIP/organizer
        is_staff_or_speaker = False
        role_display = "VIP/Attendee"
        
        if event.organizer == user:
            is_staff_or_speaker = True
            role_display = "Event Organizer"
        elif user.role in ['admin', 'organizer', 'event_manager', 'staff', 'volunteer']:
            is_staff_or_speaker = True
            role_display = f"Staff ({user.role.title()})"
        else:
            # Check volunteer/staff assignment
            vol = EventVolunteer.objects.filter(event=event, email=user.email).first()
            if not vol and user.phone:
                vol = EventVolunteer.objects.filter(event=event, mobile=user.phone).first()
            if vol:
                is_staff_or_speaker = True
                role_display = f"Staff ({vol.role})"
                
                if not vol.is_present:
                    vol.is_present = True
                    vol.checked_in_at = timezone.now()
                    vol.status = 'active'
                    vol.save()
                    
        if is_staff_or_speaker:
            result = "success"
            reason = f"Staff Pass - {role_display}"
        else:
            reason = "No ticket booking found for this user for this event."
            warnings.append("NO_BOOKING")
    else:
        # Direct lookup by name or mobile for EventVolunteer
        vol = EventVolunteer.objects.filter(event=event, mobile=scan_data).first()
        if not vol:
            vol = EventVolunteer.objects.filter(event=event, name__iexact=scan_data).first()
        if vol:
            result = "success"
            reason = f"Staff Pass - {vol.role} (Direct lookup)"
            if not vol.is_present:
                vol.is_present = True
                vol.checked_in_at = timezone.now()
                vol.status = 'active'
                vol.save()
        else:
            reason = "Invalid Code: No booking, user, or staff member found."
            warnings.append("INVALID_CODE")

    # Record Scan Log
    log = TicketScanLog.objects.create(
        booking=booking,
        user=user,
        verification_code=scan_data,
        event=event,
        scanner=scanner,
        gate=gate,
        device=device,
        result=result,
        rejection_reason=reason if result == "rejected" else ""
    )
    
    # Calculate previous successful scans for user
    prev_scans = TicketScanLog.objects.filter(
        event=event,
        user=user,
        result='success'
    ).exclude(id=log.id).count() if user else 0

    # User notification triggers on successful check-in
    if result == "success" and user:
        from accounts.services import notify
        notify(
            user,
            f"Welcome! Your check-in at '{event.title}' was successful.",
            'event_reminder',
            link=f'/bookings/{booking.id}/' if booking else f'/events/{event.id}/'
        )

    return result, reason or "Access Granted", booking, user, warnings, log, prev_scans


@login_required
def scan_qr(request):
    """Page where organizer can scan QR codes and verify tickets"""
    staff_roles = ['organizer', 'event_manager', 'finance', 'marketing', 'staff', 'volunteer', 'admin']
    if request.user.role not in staff_roles:
        messages.error(request, "Access denied.")
        return redirect('accounts:dashboard')
    
    is_admin = request.user.role == 'admin'
    if is_admin:
        my_events = Event.objects.all()
    else:
        my_events = Event.objects.filter(organizer=request.user)

    # Get event context
    selected_event_id = request.POST.get('event_id') or request.GET.get('event_id')
    selected_event = None
    if selected_event_id:
        try:
            selected_event = Event.objects.get(id=selected_event_id)
            if not is_admin and selected_event.organizer != request.user:
                selected_event = None
        except Event.DoesNotExist:
            pass
    if not selected_event:
        selected_event = my_events.first()

    my_bookings = Booking.objects.filter(event=selected_event) if selected_event else Booking.objects.none()

    # Re-calculate metrics
    total_capacity = selected_event.total_capacity or 0 if selected_event else 0
    total_checked_in = my_bookings.filter(is_checked_in=True).count()
    from django.db.models import Sum
    total_tickets_sold = my_bookings.filter(status__in=['confirmed', 'attended']).aggregate(t=Sum('quantity'))['t'] or 0
    remaining_capacity = max(0, total_capacity - total_tickets_sold)
    attendance_rate = int((total_checked_in / total_capacity * 100)) if total_capacity > 0 else 0

    if request.method == 'POST':
        qr_data = request.POST.get('qr_data', '')
        gate = request.POST.get('gate', 'Main Gate')
        device = request.POST.get('device', 'Web Scanner')
        
        if not selected_event:
            return JsonResponse({'success': False, 'message': 'No event selected'}, status=400)
            
        result_status, message, booking, user, warnings, log, prev_scans = verify_ticket_or_user(
            qr_data, selected_event, request.user, gate=gate, device=device
        )
        
        success = (result_status == "success")
        
        # Recalculate metrics after check-in
        total_checked_in = my_bookings.filter(is_checked_in=True).count()
        attendance_rate = int((total_checked_in / total_capacity * 100)) if total_capacity > 0 else 0
        
        profile = {}
        if user:
            profile = {
                'username': user.username,
                'full_name': user.get_full_name() or user.username,
                'email': user.email,
                'role': user.role,
                'photo_url': user.profile_picture.url if user.profile_picture else None,
                'ticket_code': booking.ticket_code if booking else "N/A",
                'tier': booking.ticket_tier.name if (booking and booking.ticket_tier) else "Staff/VIP Pass",
                'price': str(booking.total_price) if booking else "0.00",
                'status': booking.status if booking else "Staff",
            }
        elif booking:
            profile = {
                'username': 'Guest',
                'full_name': 'Guest Attendee',
                'email': booking.user.email,
                'role': 'guest',
                'photo_url': None,
                'ticket_code': booking.ticket_code,
                'tier': booking.ticket_tier.name if booking.ticket_tier else "Standard",
                'price': str(booking.total_price),
                'status': booking.status,
            }

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json' or request.POST.get('ajax') == 'true':
            return JsonResponse({
                'success': success,
                'result': result_status,
                'message': message,
                'warnings': warnings,
                'prev_scans': prev_scans,
                'profile': profile,
                'metrics': {
                    'checked_in': total_checked_in,
                    'remaining': remaining_capacity,
                    'attendance_rate': attendance_rate
                }
            })
        
        # Standard fallback POST
        if success:
            messages.success(request, f"✅ Check-in successful for {profile.get('full_name')}!")
        else:
            messages.error(request, f"❌ Rejection: {message}")
        return redirect(f'/bookings/scan/?event_id={selected_event.id}')

    # Fetch recent bookings for simulation
    recent_bookings = my_bookings.select_related('user', 'event').order_by('-booked_at')[:10]
    for b in recent_bookings:
        b.secure_token = generate_secure_token(b.booking_id, b.event_id, b.user_id)
        b.qr_string = f"EVENTPRO|T:{b.id}|B:{b.booking_id}|E:{b.event_id}|U:{b.user_id}|K:{b.secure_token}"

    context = {
        'my_events': my_events,
        'selected_event': selected_event,
        'recent_bookings': recent_bookings,
        'total_capacity': total_capacity,
        'total_checked_in': total_checked_in,
        'remaining_capacity': remaining_capacity,
        'attendance_rate': attendance_rate,
        'my_bookings_count': total_tickets_sold
    }
    return render(request, 'bookings/scan_qr.html', context)


@login_required
def event_scan_logs(request, event_id):
    """View scan log audits for a specific event"""
    event = get_object_or_404(Event, id=event_id)
    if request.user.role != 'admin' and event.organizer != request.user:
        messages.error(request, "Permission denied.")
        return redirect('accounts:organizer_dashboard')
        
    from bookings.models import TicketScanLog
    logs = TicketScanLog.objects.filter(event=event).select_related('user', 'booking', 'scanner').order_by('-scanned_at')
    
    return render(request, 'bookings/scan_logs.html', {
        'event': event,
        'logs': logs
    })


import csv
from django.http import JsonResponse
import json

@login_required
def export_attendees_csv(request, event_id):
    """Export event attendee bookings to CSV."""
    if request.user.role not in ['organizer', 'admin', 'event_manager']:
        return HttpResponse("Unauthorized", status=401)
    event = get_object_or_404(Event, id=event_id)
    if event.organizer != request.user and request.user.role != 'admin' and not (request.user.organization and request.user.organization == event.organization):
        return HttpResponse("Unauthorized", status=401)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="attendees_event_{event_id}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Booking ID', 'Username', 'Email', 'First Name', 'Last Name', 'Ticket Tier', 'Quantity', 'Total Price', 'Status', 'Checked In', 'Checked In At', 'Notes'])
    
    for b in event.bookings.all().select_related('user', 'ticket_tier'):
        writer.writerow([
            str(b.booking_id),
            b.user.username,
            b.user.email,
            b.user.first_name,
            b.user.last_name,
            b.ticket_tier.name if b.ticket_tier else 'General',
            b.quantity,
            b.total_price,
            b.status,
            'Yes' if b.is_checked_in else 'No',
            b.checked_in_at.strftime('%Y-%m-%d %H:%M:%S') if b.checked_in_at else '',
            b.attendee_notes
        ])
    return response


@login_required
def import_attendees_csv(request, event_id):
    """Import and register attendees from a CSV upload."""
    if request.user.role not in ['organizer', 'admin', 'event_manager']:
        messages.error(request, "Permission denied.")
        return redirect('accounts:dashboard')
    event = get_object_or_404(Event, id=event_id)
    
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        decoded_file = csv_file.read().decode('utf-8').splitlines()
        reader = csv.DictReader(decoded_file)
        
        from accounts.models import CustomUser
        from events.models import TicketTier
        
        success_count = 0
        error_count = 0
        
        for row in reader:
            try:
                username = row.get('username', '').strip()
                email = row.get('email', '').strip()
                first_name = row.get('first_name', '').strip()
                last_name = row.get('last_name', '').strip()
                quantity = int(row.get('quantity', 1))
                tier_type = row.get('tier_type', 'general').strip().lower()
                
                if not email or not username:
                    error_count += 1
                    continue
                
                # Get or create user
                user, created = CustomUser.objects.get_or_create(
                    email=email,
                    defaults={
                        'username': username,
                        'first_name': first_name,
                        'last_name': last_name,
                        'role': 'user'
                    }
                )
                if created:
                    user.set_password(CustomUser.objects.make_random_password())
                    user.save()
                
                # Get tier
                ticket_tier = TicketTier.objects.filter(event=event, tier_type=tier_type, is_active=True).first()
                
                # Check capacity
                if event.tickets_available >= quantity:
                    booking = Booking.objects.create(
                        user=user,
                        event=event,
                        quantity=quantity,
                        ticket_tier=ticket_tier,
                        status='confirmed'
                    )
                    booking.qr_code = generate_qr_code(booking)
                    booking.save()
                    success_count += 1
                else:
                    error_count += 1
            except Exception:
                error_count += 1
                
        messages.success(request, f"Import complete: {success_count} successful registrations, {error_count} errors.")
        return redirect('events:detail', event_id=event.id)
        
    messages.error(request, "Please upload a valid CSV file.")
    return redirect('events:detail', event_id=event.id)


@login_required
def manual_registration(request, event_id):
    """Manually register a single attendee (organizer desk)."""
    if request.user.role not in ['organizer', 'admin', 'event_manager', 'staff']:
        messages.error(request, "Permission denied.")
        return redirect('accounts:dashboard')
    event = get_object_or_404(Event, id=event_id)
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        quantity = int(request.POST.get('quantity', 1))
        tier_id = request.POST.get('ticket_tier', '')
        attendee_notes = request.POST.get('attendee_notes', '').strip()
        
        from accounts.models import CustomUser
        from events.models import TicketTier
        
        user, created = CustomUser.objects.get_or_create(
            email=email,
            defaults={
                'username': username or email.split('@')[0],
                'first_name': first_name,
                'last_name': last_name,
                'role': 'user'
            }
        )
        if created:
            user.set_password('welcome123')
            user.save()
            
        ticket_tier = None
        if tier_id:
            ticket_tier = TicketTier.objects.filter(id=tier_id, event=event).first()
            
        if event.tickets_available >= quantity:
            booking = Booking.objects.create(
                user=user,
                event=event,
                quantity=quantity,
                ticket_tier=ticket_tier,
                attendee_notes=attendee_notes,
                status='confirmed'
            )
            booking.qr_code = generate_qr_code(booking)
            booking.save()
            messages.success(request, f"Successfully registered {user.get_full_name()}!")
        else:
            messages.error(request, "Event is at full capacity. Cannot register.")
            
    return redirect('events:detail', event_id=event.id)


@login_required
def badge_generation(request, booking_id):
    """HTML preview of printable badge for event check-in desk."""
    booking = get_object_or_404(Booking, id=booking_id)
    if booking.event.organizer != request.user and request.user.role != 'admin' and booking.user != request.user:
        messages.error(request, "Unauthorized")
        return redirect('accounts:dashboard')
        
    booking.badge_printed = True
    booking.save()
    
    return render(request, 'bookings/badge_print.html', {'booking': booking})


from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def api_offline_sync(request):
    """API endpoint to sync scanned tickets from local storage (offline mode)."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            scans = data.get('scans', [])
            
            success = 0
            duplicates = 0
            errors = 0
            
            for scan_id in scans:
                try:
                    booking = Booking.objects.get(booking_id=scan_id)
                    if booking.is_checked_in:
                        duplicates += 1
                    else:
                        booking.is_checked_in = True
                        booking.checked_in_at = timezone.now()
                        booking.status = 'attended'
                        booking.save()
                        success += 1
                except Booking.DoesNotExist:
                    errors += 1
            return JsonResponse({'status': 'success', 'success_count': success, 'duplicate_count': duplicates, 'error_count': errors})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)


@login_required
def approve_waitlist_booking(request, booking_id):
    """Organizer manual approval of waitlist booking"""
    booking = get_object_or_404(Booking, id=booking_id)
    event = booking.event
    
    # Check permissions
    if request.user.role != 'admin' and event.organizer != request.user:
        messages.error(request, "Permission denied.")
        return redirect('accounts:organizer_dashboard')
        
    if booking.status != 'pending_approval':
        messages.error(request, "This booking is not pending approval.")
        return redirect('accounts:organizer_dashboard')
        
    # Promote to pending_payment (or confirmed if free)
    booking.status = 'pending_payment' if event.ticket_price > 0 else 'confirmed'
    if booking.status == 'pending_payment':
        booking.payment_deadline = timezone.now() + timedelta(minutes=event.reservation_timeout)
        booking.reminder_sent = False
        booking.save()
        
        # Notify user
        from accounts.services import notify
        msg = f"Your waitlist request for '{event.title}' has been approved! Complete payment within {event.reservation_timeout} minutes."
        notify(booking.user, msg, 'waitlist_upgraded', link=f'/payments/process/{booking.id}/')
        
        messages.success(request, f"Approved waitlist promotion for {booking.user.username}. Payment link sent.")
    else:
        # Free event
        qr_path = generate_qr_code(booking)
        booking.qr_code = qr_path
        booking.save()
        
        from accounts.services import notify
        msg = f"Your booking for '{event.title}' has been approved and confirmed!"
        notify(booking.user, msg, 'booking_success', link=f'/bookings/{booking.id}/')
        
        messages.success(request, f"Approved and confirmed booking for {booking.user.username}.")
        
    return redirect('accounts:organizer_dashboard')

