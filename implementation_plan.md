# Implementation Plan - Phase 2: Waitlist, Custom Staff, QR Verification & Audit Logs

This implementation plan details the architectural and code changes to satisfy the new product requirements.

## Proposed Changes

### 1. Model Updates & Migrations

#### [MODIFY] [accounts/models.py](file:///d:/Event-Planning-and-Ticket-Management-System/accounts/models.py)
- Add `verification_code` (CharField, unique=True, null=True, blank=True) to `CustomUser`.
- Override `save` to generate `USR-XXXXXXXX` unique codes if not present.

#### [MODIFY] [events/models.py](file:///d:/Event-Planning-and-Ticket-Management-System/events/models.py)
- Add `waitlist_enabled` (BooleanField, default=True) to `Event`.
- Add `reservation_timeout` (PositiveIntegerField, default=15, minutes) to `Event`.
- Add `auto_approve_waitlist` (BooleanField, default=True) to `Event`.
- Add `max_waitlist_size` (PositiveIntegerField, default=50) to `Event`.

#### [MODIFY] [bookings/models.py](file:///d:/Event-Planning-and-Ticket-Management-System/bookings/models.py)
- Add `pending_approval` to `Booking.STATUS_CHOICES`.
- Add `ticket_code` (CharField, unique=True, null=True, blank=True) to `Booking`.
- Add `payment_deadline` (DateTimeField, null=True, blank=True) to `Booking`.
- Add `reminder_sent` (BooleanField, default=False) to `Booking`.
- Override `save` to generate `EVT-YYYY-XXXXXX` unique codes if not present.
- Create `TicketScanLog` model with fields: `booking`, `user`, `verification_code`, `event`, `scanner`, `gate`, `device`, `scanned_at`, `result`, `rejection_reason`.

#### [MODIFY] [volunteers/models.py](file:///d:/Event-Planning-and-Ticket-Management-System/volunteers/models.py)
- Create `DutyArea` model with fields `event` (null=True for global), `name`, `is_global`.
- Update `EventVolunteer` model:
  - Add `duty_area` (ForeignKey to `DutyArea`, null=True, blank=True).
  - Add `role` (CharField, default='Volunteer').
  - Add `notes` (TextField, blank=True, default='').

---

### 2. Waiting List & Automatic Ticket Allocation

#### [MODIFY] [bookings/views.py](file:///d:/Event-Planning-and-Ticket-Management-System/bookings/views.py)
- Create `cleanup_expired_reservations()` helper function:
  - Release expired `pending_payment` bookings (set status to `cancelled`).
  - Send expiry notifications.
  - Automatically promote the next waitlisted user.
  - Call this function at the start of booking/dashboard view requests.
- Update `promote_from_waitlist(event, freed_quantity)`:
  - Check if waitlisting is enabled and respect max size.
  - If `auto_approve_waitlist` is True:
    - Set status to `pending_payment` (or `confirmed` if price is 0).
    - Set `payment_deadline` based on `event.reservation_timeout`.
    - Notify user of open spot and start of payment window.
  - If `auto_approve_waitlist` is False:
    - Set status to `pending_approval`.
    - Notify user and organizer.
- Update `cancel_booking` view:
  - Send cancellation notification.
  - Call `promote_from_waitlist`.
- Update `book_ticket` / payments view:
  - On payment success, set status to `confirmed`, generate QR code, and send confirmation/QR notifications.

#### [NEW] [Organizer Waitlist Management Views]
- Add a view in `events` or `bookings` to manually approve a waitlist promotion (sets status to `pending_payment` and starts reservation window).

---

### 3. Custom Staff & Dynamic Duty Areas

#### [MODIFY] [volunteers/forms.py](file:///d:/Event-Planning-and-Ticket-Management-System/volunteers/forms.py)
- Redefine `EventVolunteerForm` to exclude hardcoded choices.
- Add fields: `name`, `mobile`, `email`, `role`, `duty_area`, `shift_timing`, `notes`, `status`.
- Filter `duty_area` queryset based on the active event (show global duty areas + event-specific ones).

#### [MODIFY] [volunteers/views.py](file:///d:/Event-Planning-and-Ticket-Management-System/volunteers/views.py)
- Create views to list, add, edit, and delete custom `DutyArea` objects for an event.
- Update `manage_event_volunteers` and `edit_volunteer` views:
  - Support the new custom roles (`role`), duty areas (`duty_area`), and notes (`notes`).
  - Trigger notification on staff assignment change.

#### [MODIFY] [volunteers/manage_event.html](file:///d:/Event-Planning-and-Ticket-Management-System/templates/volunteers/manage_event.html)
- Add a panel to manage (create/delete) dynamic duty areas.
- Update the volunteer forms and tables to reflect dynamic duty areas, custom roles, and notes.

---

### 4. QR Verification & Enhanced Validation with Audit Logs

#### [MODIFY] [bookings/views.py](file:///d:/Event-Planning-and-Ticket-Management-System/bookings/views.py)
- Refactor `parse_and_verify_qr` and `scan_qr` endpoint:
  - Support looking up both ticket codes (`EVT-YYYY-XXXXXX`) and user verification codes (`USR-XXXXXXXX`).
  - Implement comprehensive validations (check event association, status checks, expired/duplicate checks).
  - Create a `TicketScanLog` audit record for every check-in attempt (Success or Rejected with detailed reasons).
  - Return attendee info (name, photo, codes, payment/check-in status, gate, previous scan count) on AJAX validation.
  - Trigger notification on successful event entry check-in.

---

### 5. UI Visibility for Verification Codes
- Display user verification codes and ticket codes on:
  - Profile page (`templates/accounts/profile.html`)
  - Ticket details page (`templates/bookings/booking_detail.html`)
  - QR Scanner page (`templates/bookings/scan_qr.html`)
  - Dashboard tables (`templates/dashboard/organizer_dashboard.html`, etc.)

## Verification Plan

### Automated Tests
- Run `python manage.py makemigrations` and `python manage.py migrate`.
- Run `python manage.py check` to ensure syntax validation.

### Manual Verification
- Verify waitlist timeout release.
- Add dynamic duty areas and check the staff dropdown filter.
- Scan QR code or enter manual code, verifying the audit log database entry.
