# EventPro Enterprise Edition — Implementation Report

## 1. Project Overview

EventPro has been upgraded from a student CRUD project into an **enterprise-grade Event Management Platform** suitable for MCA/BCA final year projects, portfolio showcase, internship demos, and placement interviews.

**Stack:** Django 6, SQLite, Bootstrap 5, Chart.js, SweetAlert2, DataTables, ReportLab, qrcode

**Roles (3 dashboards only):**
| Role | Dashboard | Purpose |
|------|-----------|---------|
| Admin | Admin Command Center | Platform analytics & management |
| Organizer | Organizer Workspace | Event, ticket, volunteer, crowd ops |
| User (Attendee) | User Dashboard | Browse, book, wishlist, tickets |

Volunteers have **no separate dashboard** — they are managed inside the Organizer Workspace.

---

## 2. Architecture

```
eventpro/
├── accounts/          # Auth, users, notifications, wishlist, audit, admin panel
│   ├── services.py    # notify(), analytics, audit helpers
│   ├── manage_views.py # Custom admin (no Django admin UI)
│   └── middleware.py  # Per-window session (multi-user browser)
├── events/            # Events, categories, polls, feedback, ticket tiers
├── bookings/          # Bookings, waitlist, QR, PDF, check-in
├── payments/          # Mock gateway, refunds, UPI QR
├── notifications/     # Notification center views
└── volunteers/        # Volunteer assignment (organizer-managed)
```

**Design principles:**
- Reuse existing models and views where possible
- Extend via new fields/models (backward-compatible migrations)
- Service layer (`accounts/services.py`) for cross-cutting concerns
- Role-based sidebar navigation
- `select_related` / `prefetch_related` on dashboard queries

---

## 3. Database Design (Key Models)

### Users & Security
- **CustomUser** — role, profile, interests, `email_verified`, `email_verification_token`
- **WindowSession** — maps browser window ID → isolated Django session
- **LoginHistory** — IP, user agent, timestamp
- **AuditLog** — admin activity trail

### Events & Tickets
- **Event** — full event metadata, capacity, pricing
- **TicketTier** — General, VIP, Student, Early Bird (per event)
- **Category** — event categorization

### Bookings & Payments
- **Booking** — statuses: `pending_payment`, `confirmed`, `cancelled`, `waitlisted`, `attended`
- **Payment** — mock gateway with success/failed/pending, refunds
- **Waitlist** — FIFO queue with auto-upgrade

### Engagement
- **Notification** — typed (booking, payment, waitlist, poll, etc.) with icons & links
- **Wishlist** — saved events per user
- **Poll / PollVote / EventFeedback** — live polling & ratings

### Operations
- **VolunteerAssignment** — organizer assigns volunteers to events with duty roles

---

## 4. Dashboard Structure

### Admin Command Center (`/accounts/dashboard/admin/`)
- **9 KPI stat cards:** users, organizers, events, active/completed/cancelled, revenue, tickets, pending payments
- **Charts:** monthly revenue (line), users by role (doughnut), user growth (bar), category distribution (polar)
- **Management:** Users, Events, Payments, Categories, Audit Logs
- **Export:** CSV reports (bookings, payments, users)
- **No Django Admin UI** in sidebar — custom panel only

### Organizer Workspace (`/accounts/dashboard/organizer/`)
- Revenue, tickets sold, volunteer count
- **Live Crowd Density** per event (low/medium/high + occupancy bar)
- Events table with Edit, View, **Volunteers** assign
- Volunteer roster
- Booking trend chart (Chart.js)

### User Dashboard (`/accounts/dashboard/user/`)
- Bookings, upcoming events, recommendations
- Notification bell, Browse Events
- **Wishlist** in sidebar

---

## 5. Core Feature Logic

### Payment-Before-Confirmation (Bug Fix)
1. Booking created as `pending_payment` (holds capacity)
2. User completes mock payment (card/UPI/net banking)
3. On success → `confirmed` + QR generated
4. On failure → `cancelled` + waitlist promoted

### Waitlist Auto Upgrade
1. Event full → user joins waitlist (`waitlisted` booking + Waitlist row)
2. On cancellation → first waitlisted user promoted
3. Paid events → `pending_payment` + notification to complete payment
4. Free events → `confirmed` + QR immediately

### AI Smart Recommendation
Uses:
- User **interests** (comma-separated profile field)
- **Past booking categories**
- **Trending** events by booking count

Displayed in User Dashboard → "Recommended For You"

### Live Crowd Density
```
occupancy = checked_in / total_capacity
< 30%  → low (green)
< 70%  → medium (amber)
≥ 70%  → high (red)
```
Shown in Organizer Workspace with progress bars.

### QR Ticket System
QR payload: `EVENTPRO|B:{booking_id}|E:{event_id}|U:{user_id}`

Organizer scans via Scan QR page → duplicate check-in prevented.

### Mock Payment Gateway
- Card, UPI (real scannable QR), Net Banking forms
- 90% simulated success rate
- Transaction ID (UUID), refund flow, payment history in admin

---

## 6. Authentication Module

| Feature | Status |
|---------|--------|
| Registration | ✅ Role: Attendee / Organizer |
| Login / Logout | ✅ Role-based + login history |
| Forgot / Reset Password | ✅ Django built-in + console email |
| Email Verification | ✅ Fields ready (`email_verified`, token) |
| Session Management | ✅ Per-window `wsid` sessions |
| Account Security | ✅ Audit log, login history, user activate/deactivate |

---

## 7. Notification System

**Types:** booking_success, payment_success, payment_failed, waitlist_upgraded, refund, poll, general

**Delivery:** In-app notification center with typed icons, unread badges, mark-as-read on visit.

---

## 8. UI / UX Enterprise Layer

**Libraries:** Bootstrap 5, Chart.js, SweetAlert2, DataTables, Poppins font

**Design:** `enterprise.css` — glass cards, gradient accents, SaaS stat grids, crowd density bars, animated sections

**Avoided:** Plain Bootstrap tables, generic CRUD appearance

---

## 9. Bug Fixes Applied

| Bug | Fix |
|-----|-----|
| Unpaid bookings held capacity as confirmed | `pending_payment` status |
| Payment failure didn't promote waitlist | `promote_from_waitlist()` on failure |
| Waitlist promote skipped payment | Routes to payment page |
| Organizer revenue column wrong | Uses Payment aggregate |
| AI ignored interests | Recommendation uses interests + categories |
| Organizer saw Browse Events | Role-restricted sidebar |
| Login session lost (multi-window) | WindowSession middleware sync |

---

## 10. How to Run

```bash
cd eventpro
.venv\Scripts\activate
pip install django pillow qrcode reportlab
python manage.py migrate
python create_sample_data.py   # optional sample data
python manage.py runserver
```

**Test accounts:**
- Admin: `admin` / `admin123`
- Organizer: `organizer1` / `org123`
- User: `user1` / `user123`

---

## 11. Future Enhancements (Roadmap)

- Email verification flow (token generation on register)
- Ticket tier UI on book page & event form
- Poll create UI on organizer event detail
- PDF/Excel export via ReportLab (CSV done)
- PostgreSQL + Redis for production
- Real payment gateway (Razorpay/Stripe)

---

*EventPro Enterprise Edition — Built for academic excellence and professional demonstration.*
