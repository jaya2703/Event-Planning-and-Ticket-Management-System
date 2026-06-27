import os
import django
import sys
from datetime import timedelta

# Set up django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eventpro.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from accounts.models import CustomUser, Organization
from events.models import Event
from bookings.models import Booking, PromoCode, Refund
from django.utils import timezone
from accounts.services import check_subscription_limits

print("Running SaaS upgrades verification script...")

# 1. Verify multi-tenant properties
org = Organization.objects.first()
print(f"[VERIFY] Organization workspace: {org.name} ({org.subscription_tier} plan)")
assert org is not None, "Error: Organization not created."

# 2. Verify subscription feature flags and limits
assert check_subscription_limits(org, 'custom_branding') == True, "Error checking branding flag."
assert check_subscription_limits(org, 'custom_domain') == (org.subscription_tier == 'enterprise'), "Error checking custom domain flag."
print("[VERIFY] Subscription feature flags: SUCCESS")

# 3. Verify PromoCode pricing discount
user = CustomUser.objects.filter(role='user').first()
event = Event.objects.first()
promo = PromoCode.objects.first()

print(f"[VERIFY] Booking with Promo: code={promo.code}, discount={promo.discount_value}%")
b = Booking.objects.create(
    user=user,
    event=event,
    quantity=1,
    promo_code=promo,
    status='confirmed'
)
# Expected discount calculation: base price - 10%
expected_price = float(event.ticket_price) * 0.9
print(f"[VERIFY] Booking computed total price: {b.total_price} (expected: {expected_price})")
assert abs(float(b.total_price) - expected_price) < 0.01, f"Error: Promo discount calculation mismatch: {b.total_price} vs {expected_price}"
print("[VERIFY] Promo code price calculation: SUCCESS")

# Clean up verification booking
b.delete()

print("\n==============================================")
print("ALL SAAS BACKEND VERIFICATIONS COMPLETED SUCCESSFULLY!")
print("==============================================")
