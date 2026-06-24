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
print(f"  ✅ {len(cats_data)} categories created")

# ── USERS ──
def make_user(username, email, password, role, first, last):
    if not CustomUser.objects.filter(username=username).exists():
        u = CustomUser.objects.create_user(
            username=username, email=email, password=password,
            role=role, first_name=first, last_name=last
        )
        print(f"  ✅ User created: {username} ({role})")
        return u
    else:
        print(f"  ⚠️  User already exists: {username}")
        return CustomUser.objects.get(username=username)

admin_user = make_user('admin', 'admin@eventpro.com', 'admin123', 'admin', 'Super', 'Admin')
admin_user.is_staff = True
admin_user.is_superuser = True
admin_user.save()

organizer1 = make_user('organizer1', 'org1@eventpro.com', 'org123', 'organizer', 'Priya', 'Sharma')
organizer1.interests = 'music,arts'
organizer1.save()

organizer2 = make_user('organizer2', 'org2@eventpro.com', 'org123', 'organizer', 'Rahul', 'Verma')
organizer2.interests = 'technology,business'
organizer2.save()

user1 = make_user('user1', 'user1@eventpro.com', 'user123', 'user', 'Ananya', 'Patel')
user1.interests = 'music,sports'
user1.save()

user2 = make_user('user2', 'user2@eventpro.com', 'user123', 'user', 'Vikram', 'Singh')
user2.interests = 'technology,education'
user2.save()

# ── EVENTS ──
today = date.today()
events_data = [
    {
        'title': 'Mumbai Music Fest 2024',
        'description': 'Experience an electrifying night of live music featuring top artists from across India. Join us for an unforgettable evening of Bollywood classics, indie music, and fusion beats under the stars.',
        'category': categories['Music'],
        'organizer': organizer1,
        'date': today + timedelta(days=10),
        'time': time(18, 0),
        'venue': 'Bandra Fort Amphitheatre, Bandra West',
        'city': 'Mumbai',
        'total_capacity': 500,
        'ticket_price': 499,
        'rules': '1. No outside food allowed.\n2. Photography permitted for personal use only.\n3. No refunds after booking confirmed.',
        'status': 'upcoming',
    },
    {
        'title': 'TechConf India 2024',
        'description': 'India\'s premier technology conference bringing together developers, designers, and innovators. Featuring keynotes on AI, Web3, and the future of software development.',
        'category': categories['Technology'],
        'organizer': organizer2,
        'date': today + timedelta(days=20),
        'time': time(9, 0),
        'venue': 'Bangalore International Exhibition Centre',
        'city': 'Bangalore',
        'total_capacity': 300,
        'ticket_price': 999,
        'rules': 'Bring a valid ID. No recording of sessions without permission.',
        'status': 'upcoming',
    },
    {
        'title': 'Street Food Festival Delhi',
        'description': 'A celebration of Delhi\'s most iconic street foods. Over 50 vendors, live cooking demonstrations, and competitions for the best chaat, kebabs, and desserts.',
        'category': categories['Food & Drink'],
        'organizer': organizer1,
        'date': today + timedelta(days=5),
        'time': time(11, 0),
        'venue': 'Dilli Haat, INA',
        'city': 'Delhi',
        'total_capacity': 200,
        'ticket_price': 0,
        'rules': 'Free event. Come hungry!',
        'status': 'upcoming',
    },
    {
        'title': 'IPL Viewing Night',
        'description': 'Watch the IPL final on a giant 30-foot screen with fellow cricket fans. Includes unlimited snacks and drinks. Live commentary, prizes for predictions!',
        'category': categories['Sports'],
        'organizer': organizer2,
        'date': today + timedelta(days=3),
        'time': time(19, 30),
        'venue': 'Sports Zone Arena, Powai',
        'city': 'Mumbai',
        'total_capacity': 100,
        'ticket_price': 299,
        'status': 'upcoming',
    },
    {
        'title': 'Startup Weekend Hyderabad',
        'description': 'A 54-hour event where aspiring entrepreneurs pitch ideas, form teams, and build startups. Mentors from leading VC firms and successful founders.',
        'category': categories['Business'],
        'organizer': organizer2,
        'date': today + timedelta(days=30),
        'time': time(9, 0),
        'venue': 'T-Hub, IIIT Hyderabad Campus',
        'city': 'Hyderabad',
        'total_capacity': 150,
        'ticket_price': 599,
        'status': 'upcoming',
    },
    {
        'title': 'Art Exhibition: Colors of India',
        'description': 'A stunning showcase of contemporary Indian art featuring 40+ artists. Paintings, sculptures, digital art, and photography exploring the diversity of India.',
        'category': categories['Arts'],
        'organizer': organizer1,
        'date': today + timedelta(days=15),
        'time': time(10, 0),
        'venue': 'National Gallery of Modern Art',
        'city': 'Delhi',
        'total_capacity': 250,
        'ticket_price': 150,
        'status': 'upcoming',
    },
]

for ev_data in events_data:
    if not Event.objects.filter(title=ev_data['title']).exists():
        Event.objects.create(**ev_data)
        print(f"  ✅ Event created: {ev_data['title']}")
    else:
        print(f"  ⚠️  Event already exists: {ev_data['title']}")

from volunteers.models import EventVolunteer
music_fest = Event.objects.filter(title='Mumbai Music Fest 2024').first()
if music_fest and not EventVolunteer.objects.filter(event=music_fest).exists():
    EventVolunteer.objects.create(
        event=music_fest, name='Meera Nair', mobile='9876543210',
        email='meera@example.com', duty='registration',
        shift_timing='09:00 AM – 01:00 PM', status='assigned',
    )
    EventVolunteer.objects.create(
        event=music_fest, name='Rahul Shah', mobile='9876543211',
        email='rahul@example.com', duty='entry_gate',
        shift_timing='01:00 PM – 06:00 PM', status='assigned',
    )
    print("  ✅ Event staff volunteers created for Mumbai Music Fest")

print("\n" + "="*50)
print("✅ Sample data created successfully!")
print("="*50)
print("\nTest Login Credentials:")
print("  Admin:      admin / admin123")
print("  Organizer1: organizer1 / org123")
print("  Organizer2: organizer2 / org123")
print("  User1:      user1 / user123")
print("  User2:      user2 / user123")
print("\nEvent staff (volunteers) are managed per-event by organizers — no separate login.")
print("\nRun the server with: python manage.py runserver")
