# EventPro - Event Planning & Ticket Management System

> An intern-level full-stack Django project for your portfolio, interviews, and college submissions.

---

## Tech Stack

| Layer      | Technology              |
|------------|-------------------------|
| Backend    | Python 3, Django 4+     |
| Frontend   | HTML5, CSS3, Bootstrap 5, JavaScript |
| Database   | SQLite (dev), MySQL-ready |
| PDF        | ReportLab               |
| QR Code    | qrcode library          |
| Images     | Pillow                  |

---

## Features

### Authentication
- Register / Login / Logout
- Forgot Password (email-based)
- 4 Roles: Admin, Organizer, User, Volunteer

### Event Management
- Create / Edit / Delete Events
- Event Banner Upload
- Category-based browsing
- Search & Filter (by name, city, category, price)

### Ticket Booking
- Book 1–5 tickets per booking
- Automatic capacity tracking
- QR code generation per booking
- PDF ticket download
- Booking cancellation

### Waitlist Auto-Upgrade ⭐
- When event is full → join waitlist
- When booking cancelled → first on waitlist gets promoted automatically
- Notification sent to promoted user

### Mock Payment System
- Simulates card / UPI / net banking
- 90% success rate simulation
- Payment success / failed / pending states

### QR Verification & Check-in ⭐
- Unique QR per booking
- Scan to verify at venue
- Prevents duplicate entry detection
- Live crowd density monitoring (Low / Medium / High)

### AI Smart Recommendations ⭐
- Based on user interests and booking history
- Simple category-matching logic (no ML needed)
- Shows on user dashboard

### Live Polls & Feedback ⭐
- Organizers create polls for their events
- Users vote in real time
- Star ratings + written reviews

### 3 Dashboards
- **Admin Dashboard**: System-wide stats, revenue, user breakdown
- **Organizer Dashboard**: Event management, ticket sales, volunteer assignment
- **User Dashboard**: Bookings, notifications, AI recommendations

### Volunteer Management
- Organizers assign volunteers to events
- Volunteers get limited access (QR scanning only)

---

## Project Structure

```
eventpro/
├── eventpro/           ← Django project settings
│   ├── settings.py
│   └── urls.py
├── accounts/           ← Users, roles, authentication
│   ├── models.py       ← CustomUser with role field
│   ├── views.py        ← Login, register, dashboards
│   ├── forms.py
│   └── urls.py
├── events/             ← Event CRUD, polls, feedback
│   ├── models.py       ← Event, Category, Poll, Feedback
│   ├── views.py
│   └── urls.py
├── bookings/           ← Ticket booking, QR, PDF, check-in
│   ├── models.py       ← Booking, Waitlist
│   ├── views.py
│   └── urls.py
├── payments/           ← Mock payment flow
│   ├── models.py
│   └── views.py
├── volunteers/         ← Volunteer assignment
│   ├── models.py
│   └── views.py
├── notifications/      ← Notification list view
├── templates/          ← All HTML files
│   ├── base.html       ← Master template (navbar, footer)
│   ├── home.html
│   ├── accounts/
│   ├── events/
│   ├── bookings/
│   ├── payments/
│   └── dashboard/
├── static/
│   ├── css/style.css   ← All custom CSS
│   └── js/main.js      ← Custom JavaScript
├── media/              ← Uploaded files (auto-created)
├── create_sample_data.py  ← Creates test users & events
├── setup.sh            ← One-click setup
└── manage.py
```

---

## Quick Setup

### 1. Install dependencies
```bash
pip install django pillow qrcode reportlab
```

### 2. Run migrations
```bash
    python manage.py makemigrations
python manage.py migrate
```

### 3. Create sample data
```bash
python create_sample_data.py
```

### 4. Start server
```bash
python manage.py runserver
```

### 5. Open browser
```
http://127.0.0.1:8000
```

**OR** use the one-click setup:
```bash
bash setup.sh
```

---

## Test Login Credentials

| Role       | Username    | Password |
|------------|-------------|----------|
| Admin      | admin       | admin123 |
| Organizer  | organizer1  | org123   |
| Organizer  | organizer2  | org123   |
| User       | user1       | user123  |
| User       | user2       | user123  |
| Volunteer  | volunteer1  | vol123   |

---

## Testing Multiple Users Simultaneously

To test different roles at the same time:

1. **Normal browser** → Login as `admin`
2. **Incognito window** → Login as `organizer1`
3. **Different browser** (Firefox/Edge) → Login as `user1`

Django stores sessions independently per browser, so each window acts as a different user. No extra setup needed!

---

## URL Reference

| URL | Description |
|-----|-------------|
| `/` | Homepage |
| `/events/` | Browse all events |
| `/events/<id>/` | Event detail |
| `/events/create/` | Create event (organizer) |
| `/accounts/login/` | Login |
| `/accounts/register/` | Register |
| `/accounts/dashboard/` | Auto-redirects by role |
| `/bookings/book/<id>/` | Book a ticket |
| `/bookings/history/` | My bookings |
| `/bookings/scan/` | QR scanner (organizer/volunteer) |
| `/payments/process/<id>/` | Payment page |
| `/admin/` | Django admin panel |

---

## Built With ❤️ for Learning

This project is intentionally beginner-friendly:
- Simple, readable code with comments
- No complex architecture
- Feature-by-feature structure
- Easy to extend and modify

Perfect for: internship interviews, college projects, portfolio
