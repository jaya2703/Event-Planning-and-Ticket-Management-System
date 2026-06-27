"""
Sample Data Script
==================
Run this AFTER migrations to create sample users, categories, and events.

Usage:
    python manage.py shell < create_sample_data.py
    OR
    python manage.py runscript create_sample_data  (if django-extensions installed)
"""
import os, sys, django

# Make sure Django knows which settings to use
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eventpro.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from accounts.models import CustomUser
from events.models import Category, Event
from django.utils import timezone
from datetime import date, time, timedelta

from accounts.models import CustomUser, Organization
from events.models import Category, Event, Venue, Speaker, Session, Sponsor, EventFAQ, TicketTier
from bookings.models import Booking, PromoCode, Refund
from volunteers.models import EventVolunteer, Shift, Task
from django.utils import timezone
from datetime import date, time, datetime, timedelta

print("Creating sample data...")

# ── CATEGORIES ──
cats_data = [
    ('Music', 'bi-music-note-beamed'),
    ('Sports', 'bi-trophy'),
    ('Technology', 'bi-laptop'),
    ('Food & Drink', 'bi-cup-hot'),
    ('Arts', 'bi-palette'),
    ('Business', 'bi-briefcase'),
    ('Health', 'bi-heart-pulse'),
    ('Education', 'bi-book'),
]

categories = {}
for name, icon in cats_data:
    cat, _ = Category.objects.get_or_create(name=name, defaults={'icon': icon})
    categories[name] = cat
print(f"  [OK] {len(cats_data)} categories created")

# ── USERS ──
def make_user(username, email, password, role, first, last, org=None):
    if not CustomUser.objects.filter(username=username).exists():
        u = CustomUser.objects.create_user(
            username=username, email=email, password=password,
            role=role, first_name=first, last_name=last, organization=org
        )
        print(f"  [OK] User created: {username} ({role})")
        return u
    else:
        u = CustomUser.objects.get(username=username)
        u.role = role
        if org:
            u.organization = org
        u.save()
        print(f"  [WARN] User already exists/updated: {username}")
        return u

# 1. Super Admin
admin_user = make_user('admin', 'admin@eventpro.com', 'admin123', 'admin', 'Super', 'Admin')
admin_user.is_staff = True
admin_user.is_superuser = True
admin_user.save()

# 2. Organizers
organizer1 = make_user('organizer1', 'org1@eventpro.com', 'org123', 'organizer', 'Priya', 'Sharma')
organizer1.interests = 'music,arts'
organizer1.save()

organizer2 = make_user('organizer2', 'org2@eventpro.com', 'org123', 'organizer', 'Rahul', 'Verma')
organizer2.interests = 'technology,business'
organizer2.save()

# ── ORGANIZATIONS ──
org1, _ = Organization.objects.get_or_create(
    slug='priya-events',
    defaults={'name': "Priya's Events Hub", 'owner': organizer1, 'subscription_tier': 'pro', 'subscription_status': 'active'}
)
organizer1.organization = org1
organizer1.save()

org2, _ = Organization.objects.get_or_create(
    slug='rahul-studio',
    defaults={'name': "Rahul's Tech & Business Studio", 'owner': organizer2, 'subscription_tier': 'enterprise', 'subscription_status': 'active'}
)
organizer2.organization = org2
organizer2.save()

# 3. Org Members / Roles
manager1 = make_user('manager1', 'manager1@eventpro.com', 'manager123', 'event_manager', 'Amit', 'Patel', org=org1)
finance1 = make_user('finance1', 'finance1@eventpro.com', 'finance123', 'finance', 'Sneha', 'Reddy', org=org1)
marketing1 = make_user('marketing1', 'marketing1@eventpro.com', 'marketing123', 'marketing', 'Karan', 'Joshi', org=org1)
staff1 = make_user('staff1', 'staff1@eventpro.com', 'staff123', 'staff', 'Pooja', 'Mehta', org=org1)
volunteer1 = make_user('volunteer1', 'volunteer1@eventpro.com', 'volunteer123', 'volunteer', 'Rohan', 'Das', org=org1)

user1 = make_user('user1', 'user1@eventpro.com', 'user123', 'user', 'Ananya', 'Patel')
user1.interests = 'music,sports'
user1.save()

user2 = make_user('user2', 'user2@eventpro.com', 'user123', 'user', 'Vikram', 'Singh')
user2.interests = 'technology,education'
user2.save()

# ── VENUES ──
v1, _ = Venue.objects.get_or_create(
    organization=org1,
    name='Bandra Fort Amphitheatre',
    defaults={'address': 'Bandra West, Land\'s End', 'city': 'Mumbai', 'capacity': 500}
)
v2, _ = Venue.objects.get_or_create(
    organization=org2,
    name='Bangalore International Exhibition Centre',
    defaults={'address': '10th Mile, Tumkur Road', 'city': 'Bangalore', 'capacity': 1000}
)

# ── SPEAKERS ──
sp1, _ = Speaker.objects.get_or_create(
    organization=org1,
    name='A.R. Rahman',
    defaults={'title': 'Music Composer & Director', 'bio': 'Oscar winning composer', 'email': 'rahman@example.com'}
)
sp2, _ = Speaker.objects.get_or_create(
    organization=org2,
    name='Nandan Nilekani',
    defaults={'title': 'Co-founder, Infosys', 'bio': 'Tech pioneer and entrepreneur', 'email': 'nandan@example.com'}
)

# ── EVENTS ──
today = date.today()
events_data = [
    {
        'title': 'Mumbai Music Fest 2024',
        'description': 'Experience an electrifying night of live music featuring top artists from across India. Join us for an unforgettable evening of Bollywood classics, indie music, and fusion beats under the stars.',
        'category': categories['Music'],
        'organizer': organizer1,
        'organization': org1,
        'date': today + timedelta(days=10),
        'time': time(18, 0),
        'end_date': today + timedelta(days=11),
        'end_time': time(23, 0),
        'venue': 'Bandra Fort Amphitheatre, Bandra West',
        'venue_ref': v1,
        'city': 'Mumbai',
        'total_capacity': 500,
        'ticket_price': 499.00,
        'rules': '1. No outside food allowed.\n2. Photography permitted for personal use only.\n3. No refunds after booking confirmed.',
        'status': 'published',
    },
    {
        'title': 'TechConf India 2024',
        'description': 'India\'s premier technology conference bringing together developers, designers, and innovators. Featuring keynotes on AI, Web3, and the future of software development.',
        'category': categories['Technology'],
        'organizer': organizer2,
        'organization': org2,
        'date': today + timedelta(days=20),
        'time': time(9, 0),
        'end_date': today + timedelta(days=22),
        'end_time': time(17, 0),
        'venue': 'Bangalore International Exhibition Centre',
        'venue_ref': v2,
        'city': 'Bangalore',
        'total_capacity': 300,
        'ticket_price': 999.00,
        'rules': 'Bring a valid ID. No recording of sessions without permission.',
        'status': 'published',
    },
]

for ev_data in events_data:
    ev, created = Event.objects.get_or_create(title=ev_data['title'], defaults=ev_data)
    if created:
        print(f"  [OK] Event created: {ev.title}")
        # Add a default general and VIP tier
        TicketTier.objects.create(event=ev, tier_type='general', name='General Admission', price=ev.ticket_price, capacity=int(ev.total_capacity * 0.8))
        TicketTier.objects.create(event=ev, tier_type='vip', name='VIP Pass', price=ev.ticket_price * 2, capacity=int(ev.total_capacity * 0.2))
        
        # Add standard Sessions
        Session.objects.create(event=ev, title="Keynote Speech", description="Opening remarks", start_time=datetime.combine(ev.date, ev.time), end_time=datetime.combine(ev.date, ev.time) + timedelta(hours=2), speaker=sp2 if ev.category.name=='Technology' else sp1)
        
        # Add Sponsors
        Sponsor.objects.create(event=ev, name="Titanium Corp", tier="gold", booth_number="A1", deliverables="Banner on Main Stage")
        
        # Add FAQs
        EventFAQ.objects.create(event=ev, question="Is parking available?", answer="Yes, free parking is available on site.", order=1)
    else:
        print(f"  [WARN] Event already exists: {ev_data['title']}")

# ── PROMO CODE ──
PromoCode.objects.get_or_create(
    code='WELCOME10',
    defaults={
        'organization': org1,
        'discount_type': 'percentage',
        'discount_value': 10.00,
        'valid_from': timezone.now() - timedelta(days=1),
        'valid_to': timezone.now() + timedelta(days=30),
        'active': True
    }
)

# ── STAFF ASSIGNMENT / SHIFTS & TASKS ──
music_fest = Event.objects.filter(title='Mumbai Music Fest 2024').first()
if music_fest:
    # Volunteers
    EventVolunteer.objects.get_or_create(
        event=music_fest, name='Meera Nair',
        defaults={'mobile': '9876543210', 'email': 'meera@example.com', 'duty': 'registration', 'shift_timing': '09:00 AM – 01:00 PM', 'status': 'assigned'}
    )
    
    # Shifts
    Shift.objects.get_or_create(
        event=music_fest, staff=staff1,
        defaults={'duty': 'Front Gate Scanner', 'start_time': timezone.now(), 'end_time': timezone.now() + timedelta(hours=6)}
    )
    
    # Tasks
    Task.objects.get_or_create(
        event=music_fest, assignee=staff1, title='Test QR Scanning Devices',
        defaults={'description': 'Ensure all camera scanners are logged in and tested', 'status': 'pending'}
    )
    print("  [OK] Staff shifts and tasks created for Mumbai Music Fest")

print("\n" + "="*50)
print("[OK] Sample data created successfully!")
print("="*50)
print("\nTest Login Credentials:")
print("  Admin:      admin / admin123")
print("  Organizer1: organizer1 / org123")
print("  Organizer2: organizer2 / org123")
print("  User1:      user1 / user123")
print("  User2:      user2 / user123")
print("\nEvent staff (volunteers) are managed per-event by organizers — no separate login.")
print("\nRun the server with: python manage.py runserver")
