"""Analytics helpers for admin Events Management page."""
import json
from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone

from accounts.admin_analytics import pct_change
from accounts.models import CustomUser
from events.models import Event, Category
from bookings.models import Booking
from payments.models import Payment

BOOKING_ACTIVE = Q(bookings__status__in=['confirmed', 'attended', 'pending_payment'])


def _month_bounds(offset=0):
    now = timezone.now()
    first = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if offset == 0:
        return first, now
    end = first - timedelta(seconds=1)
    return end.replace(day=1, hour=0, minute=0, second=0, microsecond=0), end


def build_events_admin_context(request):
    search = request.GET.get('q', '').strip()
    category_filter = request.GET.get('category', '')
    organizer_filter = request.GET.get('organizer', '')
    status_filter = request.GET.get('status', '')
    city_filter = request.GET.get('city', '').strip()
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    base_qs = Event.objects.select_related('organizer', 'category')
    filtered = base_qs

    if search:
        filtered = filtered.filter(
            Q(title__icontains=search)
            | Q(venue__icontains=search)
            | Q(city__icontains=search)
            | Q(description__icontains=search)
        )
    if category_filter:
        filtered = filtered.filter(category_id=category_filter)
    if organizer_filter:
        filtered = filtered.filter(organizer_id=organizer_filter)
    if status_filter:
        filtered = filtered.filter(status=status_filter)
    if city_filter:
        filtered = filtered.filter(city__icontains=city_filter)
    if date_from:
        filtered = filtered.filter(date__gte=date_from)
    if date_to:
        filtered = filtered.filter(date__lte=date_to)

    events_qs = filtered.annotate(
        tickets_sold=Sum('bookings__quantity', filter=BOOKING_ACTIVE),
        revenue=Sum(
            'bookings__payment__amount',
            filter=Q(bookings__payment__status='success'),
        ),
        checkins=Count('bookings', filter=Q(bookings__is_checked_in=True)),
    ).order_by('-created_at')

    paginator = Paginator(events_qs, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    status_counts = {
        'total': Event.objects.count(),
        'upcoming': Event.objects.filter(status='upcoming').count(),
        'ongoing': Event.objects.filter(status='ongoing').count(),
        'completed': Event.objects.filter(status='completed').count(),
        'cancelled': Event.objects.filter(status='cancelled').count(),
    }

    tickets_total = Booking.objects.filter(
        status__in=['confirmed', 'attended', 'pending_payment']
    ).aggregate(t=Sum('quantity'))['t'] or 0
    revenue_total = Payment.objects.filter(status='success').aggregate(
        t=Sum('amount')
    )['t'] or 0

    fill_rates = []
    for ev in Event.objects.filter(total_capacity__gt=0)[:200]:
        fill_rates.append(min(100, (ev.tickets_booked / ev.total_capacity) * 100))
    avg_attendance = round(sum(fill_rates) / len(fill_rates), 1) if fill_rates else 0

    cur_start, cur_end = _month_bounds(0)
    prev_start, prev_end = _month_bounds(1)
    events_cur = Event.objects.filter(created_at__gte=cur_start, created_at__lte=cur_end).count()
    events_prev = Event.objects.filter(created_at__gte=prev_start, created_at__lte=prev_end).count()
    tickets_cur = Booking.objects.filter(booked_at__gte=cur_start, booked_at__lte=cur_end).aggregate(
        t=Sum('quantity')
    )['t'] or 0
    tickets_prev = Booking.objects.filter(booked_at__gte=prev_start, booked_at__lte=prev_end).aggregate(
        t=Sum('quantity')
    )['t'] or 0
    rev_cur = Payment.objects.filter(
        status='success', paid_at__gte=cur_start, paid_at__lte=cur_end
    ).aggregate(t=Sum('amount'))['t'] or 0
    rev_prev = Payment.objects.filter(
        status='success', paid_at__gte=prev_start, paid_at__lte=prev_end
    ).aggregate(t=Sum('amount'))['t'] or 0

    analytics = {
        'total_events': {'value': status_counts['total'], 'growth': pct_change(events_cur, events_prev), 'up': events_cur >= events_prev},
        'tickets_sold': {'value': tickets_total, 'growth': pct_change(tickets_cur, tickets_prev), 'up': tickets_cur >= tickets_prev},
        'revenue': {'value': revenue_total, 'growth': pct_change(rev_cur, rev_prev), 'up': rev_cur >= rev_prev},
        'avg_attendance': {'value': avg_attendance, 'growth': 0, 'up': True},
    }

    top_event = (
        Event.objects.annotate(bc=Count('bookings'))
        .order_by('-bc')
        .select_related('organizer')
        .first()
    )
    top_revenue_event = (
        Event.objects.annotate(
            rev=Sum('bookings__payment__amount', filter=Q(bookings__payment__status='success'))
        )
        .order_by('-rev')
        .first()
    )
    cat_top = (
        Category.objects.annotate(bc=Count('event'))
        .order_by('-bc')
        .first()
    )
    week_end = timezone.now().date() + timedelta(days=7)
    upcoming_week = Event.objects.filter(
        status='upcoming', date__gte=timezone.now().date(), date__lte=week_end
    ).count()
    low_attendance = Event.objects.filter(total_capacity__gt=0).annotate(
        sold=Sum('bookings__quantity', filter=BOOKING_ACTIVE)
    )
    low_attendance_count = sum(
        1 for e in low_attendance
        if (e.sold or 0) / e.total_capacity < 0.2
    )

    insights = {
        'top_event': top_event,
        'top_revenue_event': top_revenue_event,
        'top_category': cat_top.name if cat_top else '—',
        'upcoming_week': upcoming_week,
        'low_attendance': low_attendance_count,
    }

    today = timezone.now().date()
    start_chart = today - timedelta(days=180)
    creation_qs = (
        Event.objects.filter(created_at__date__gte=start_chart)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    creation_labels = [r['month'].strftime('%b') for r in creation_qs if r['month']]
    creation_values = [r['count'] for r in creation_qs if r['month']]

    top5 = (
        Event.objects.annotate(
            sold=Sum('bookings__quantity', filter=BOOKING_ACTIVE),
            rev=Sum('bookings__payment__amount', filter=Q(bookings__payment__status='success')),
        )
        .order_by('-sold')[:5]
    )
    top5_labels = [e.title[:22] for e in top5]
    top5_bookings = [e.sold or 0 for e in top5]
    top5_revenue = [float(e.rev or 0) for e in top5]

    cat_labels, cat_values = [], []
    for row in (
        Category.objects.annotate(
            rev=Sum(
                'event__bookings__payment__amount',
                filter=Q(event__bookings__payment__status='success'),
            )
        )
        .order_by('-rev')[:6]
    ):
        cat_labels.append(row.name)
        cat_values.append(float(row.rev or 0))

    organizers = CustomUser.objects.filter(role='organizer').order_by('username')
    categories = Category.objects.order_by('name')

    query_params = request.GET.copy()
    if 'page' in query_params:
        query_params.pop('page')

    return {
        'page_obj': page_obj,
        'events': page_obj.object_list,
        'status_counts': status_counts,
        'analytics': analytics,
        'insights': insights,
        'search': search,
        'category_filter': category_filter,
        'organizer_filter': organizer_filter,
        'status_filter': status_filter,
        'city_filter': city_filter,
        'date_from': date_from,
        'date_to': date_to,
        'organizers': organizers,
        'categories': categories,
        'query_string': query_params.urlencode(),
        'chart_creation_labels': json.dumps(creation_labels),
        'chart_creation_values': json.dumps(creation_values),
        'chart_top5_labels': json.dumps(top5_labels),
        'chart_top5_bookings': json.dumps(top5_bookings),
        'chart_top5_revenue': json.dumps(top5_revenue),
        'chart_cat_labels': json.dumps(cat_labels),
        'chart_cat_values': json.dumps(cat_values),
    }
