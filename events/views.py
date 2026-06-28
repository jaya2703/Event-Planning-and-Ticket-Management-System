"""
Events Views
============
Handles all event-related pages: listing, detail, create, edit, delete.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Event, Category, Poll, PollOption, PollVote, EventFeedback
from .forms import EventForm, FeedbackForm, PollForm


def _format_stat(count, fallback):
    """Format counts like 500+ or 50K+ for hero stats."""
    if count >= 10000:
        return f'{count // 1000}K+'
    if count >= 1000:
        k = count / 1000
        return f'{int(k)}K+' if k == int(k) else f'{count}+'
    if count > 0:
        return f'{count}+'
    return fallback


def home(request):
    """Homepage - shows featured events"""
    featured_events = list(
        Event.objects.filter(status='upcoming')
        .select_related('category', 'organizer')
        .order_by('date')[:7]
    )
    categories = Category.objects.all()
    total_events = Event.objects.filter(status='upcoming').count()
    total_users = 0
    try:
        from accounts.models import CustomUser
        total_users = CustomUser.objects.count()
    except Exception:
        pass

    spotlight_event = featured_events[0] if featured_events else None
    trending_events = featured_events[1:6] if spotlight_event else featured_events[:5]
    more_events = featured_events[6:] if len(featured_events) > 6 else []

    total_bookings = 0
    try:
        from bookings.models import Booking
        total_bookings = Booking.objects.filter(
            status__in=['confirmed', 'attended']
        ).count()
    except Exception:
        pass

    context = {
        'featured_events': featured_events,
        'spotlight_event': spotlight_event,
        'trending_events': trending_events,
        'more_events': more_events,
        'categories': categories,
        'total_events': total_events,
        'total_users': total_users,
        'total_bookings': total_bookings,
        'stat_events': _format_stat(total_events, '500+'),
        'stat_tickets': _format_stat(total_bookings, '50K+'),
        'stat_users': _format_stat(total_users, '10K+'),
    }
    return render(request, 'home.html', context)


def event_list(request):
    """
    Event listing page with search and filters.
    Users can search events and filter by category, date, city, price.
    """
    if request.user.is_authenticated:
        if request.user.role == 'organizer':
            messages.info(request, 'Organizers manage events from the dashboard.')
            return redirect('accounts:organizer_dashboard')
        if request.user.role == 'volunteer':
            messages.info(request, 'Please sign in as an attendee or organizer.')
            return redirect('accounts:login')

    events = Event.objects.filter(status='upcoming').order_by('date')
    categories = Category.objects.all()
    
    # --- SEARCH ---
    search_query = request.GET.get('search', '')
    if search_query:
        # Q objects allow us to search multiple fields at once
        events = events.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(venue__icontains=search_query) |
            Q(city__icontains=search_query)
        )
    
    # --- FILTERS ---
    category_filter = request.GET.get('category', '')
    if category_filter:
        events = events.filter(category__id=category_filter)
    
    city_filter = request.GET.get('city', '')
    if city_filter:
        events = events.filter(city__icontains=city_filter)
    
    date_filter = request.GET.get('date', '')
    if date_filter:
        events = events.filter(date=date_filter)
    
    price_filter = request.GET.get('price', '')
    if price_filter == 'free':
        events = events.filter(ticket_price=0)
    elif price_filter == 'paid':
        events = events.filter(ticket_price__gt=0)

    wishlist_ids = set()
    if request.user.is_authenticated and request.user.role == 'user':
        from accounts.models import Wishlist
        wishlist_ids = set(
            Wishlist.objects.filter(user=request.user).values_list('event_id', flat=True)
        )

    context = {
        'events': events,
        'categories': categories,
        'search_query': search_query,
        'selected_category': category_filter,
        'selected_city': city_filter,
        'wishlist_ids': wishlist_ids,
    }
    return render(request, 'events/event_list.html', context)


def event_detail(request, event_id):
    """Single event detail page"""
    event = get_object_or_404(Event, id=event_id)
    
    # Private password check
    if event.visibility == 'private' and event.password:
        pwd_session_key = f'event_pwd_{event.id}'
        is_pwd_verified = request.session.get(pwd_session_key) == event.password
        if not is_pwd_verified:
            if request.method == 'POST' and 'event_private_password' in request.POST:
                submitted_pwd = request.POST.get('event_private_password', '').strip()
                if submitted_pwd == event.password:
                    request.session[pwd_session_key] = event.password
                    messages.success(request, "Access granted!")
                    return redirect('events:detail', event_id=event.id)
                else:
                    messages.error(request, "Incorrect password. Access denied.")
            return render(request, 'events/private_password.html', {'event': event})

    feedbacks = EventFeedback.objects.filter(event=event).order_by('-created_at')
    polls = Poll.objects.filter(event=event, is_active=True)
    
    # Check if user already booked this event
    already_booked = False
    user_feedback = None
    if request.user.is_authenticated:
        from bookings.models import Booking
        already_booked = Booking.objects.filter(
            user=request.user, event=event, status='confirmed'
        ).exists()
        try:
            user_feedback = EventFeedback.objects.get(event=event, user=request.user)
        except EventFeedback.DoesNotExist:
            pass
    
    # Handle feedback submission
    feedback_form = FeedbackForm()
    if request.method == 'POST' and request.user.is_authenticated:
        if 'feedback' in request.POST:
            if user_feedback:
                messages.warning(request, "You already submitted feedback for this event.")
            else:
                feedback_form = FeedbackForm(request.POST)
                if feedback_form.is_valid():
                    fb = feedback_form.save(commit=False)
                    fb.event = event
                    fb.user = request.user
                    fb.save()
                    messages.success(request, "Thank you for your feedback!")
                    return redirect('events:detail', event_id=event.id)
        
        # Handle poll voting
        elif 'poll_option' in request.POST:
            option_id = request.POST.get('poll_option')
            poll_id = request.POST.get('poll_id')
            try:
                poll = Poll.objects.get(id=poll_id)
                option = PollOption.objects.get(id=option_id, poll=poll)
                PollVote.objects.create(poll=poll, option=option, user=request.user)
                messages.success(request, "Vote submitted!")
            except Exception as e:
                messages.error(request, "Could not submit vote. You may have already voted.")
            return redirect('events:detail', event_id=event.id)

    wishlist_ids = set()
    if request.user.is_authenticated and request.user.role == 'user':
        from accounts.models import Wishlist
        wishlist_ids = set(
            Wishlist.objects.filter(user=request.user).values_list('event_id', flat=True)
        )

    context = {
        'event': event,
        'feedbacks': feedbacks,
        'polls': polls,
        'already_booked': already_booked,
        'user_feedback': user_feedback,
        'feedback_form': feedback_form,
        'wishlist_ids': wishlist_ids,
    }
    return render(request, 'events/event_detail.html', context)


@login_required
def create_event(request):
    """Create a new event — organizers only."""
    if request.user.role not in ['organizer', 'admin', 'event_manager']:
        messages.error(request, "Only organizers can create events.")
        return redirect('accounts:dashboard')
    
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save(commit=False)
            event.organizer = request.user  # Set the organizer to current user
            if request.user.organization:
                event.organization = request.user.organization
            event.save()
            messages.success(request, f"Event '{event.title}' created successfully!")
            return redirect('accounts:organizer_dashboard')
    else:
        form = EventForm()
    
    return render(request, 'events/event_form.html', {'form': form, 'action': 'Create'})


@login_required
def edit_event(request, event_id):
    """Edit an existing event"""
    event = get_object_or_404(Event, id=event_id)
    
    can_edit = (request.user.role == 'admin') or (event.organizer == request.user)

    if not can_edit:
        messages.error(request, "You do not have permission to edit this event.")
        return redirect('accounts:organizer_dashboard')
    
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, "Event updated successfully!")
            return redirect('accounts:organizer_dashboard')
    else:
        form = EventForm(instance=event)
    
    return render(request, 'events/event_form.html', {
        'form': form, 'action': 'Edit', 'event': event
    })


@login_required
def delete_event(request, event_id):
    """Delete an event"""
    event = get_object_or_404(Event, id=event_id)
    
    can_delete = (request.user.role == 'admin') or (event.organizer == request.user)

    if not can_delete:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json':
            return JsonResponse({'error': 'Permission denied'}, status=403)
        messages.error(request, "You do not have permission to delete this event.")
        return redirect('accounts:organizer_dashboard')
    
    if request.method == 'POST' or request.GET.get('ajax') == 'true':
        event_title = event.title
        event.delete()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json' or request.GET.get('ajax') == 'true':
            return JsonResponse({'success': True, 'message': f"Event '{event_title}' deleted."})
        messages.success(request, f"Event '{event_title}' deleted.")
        return redirect('accounts:organizer_dashboard')
    
    return render(request, 'events/event_confirm_delete.html', {'event': event})


@login_required
def add_poll(request, event_id):
    """Add a poll to an event (organizer only)"""
    event = get_object_or_404(Event, id=event_id)
    # Only the organizer who created it, someone in the same organization, or admin can add polls
    can_add_poll = False
    if request.user.role == 'admin':
        can_add_poll = True
    elif event.organizer == request.user:
        can_add_poll = True
    elif event.organization and request.user.organization == event.organization and request.user.role in ['organizer', 'event_manager']:
        can_add_poll = True

    if not can_add_poll:
        messages.error(request, "Permission denied.")
        return redirect('events:detail', event_id=event.id)
    
    if request.method == 'POST':
        question = request.POST.get('question')
        options = request.POST.getlist('options')  # List of option texts
        
        if question and options:
            poll = Poll.objects.create(event=event, question=question)
            for opt_text in options:
                if opt_text.strip():
                    PollOption.objects.create(poll=poll, option_text=opt_text.strip())
            messages.success(request, "Poll created!")
        else:
            messages.error(request, "Please provide a question and at least one option.")
    
    return redirect('events:detail', event_id=event.id)


@login_required
def duplicate_event(request, event_id):
    """Clone an event and its settings (sessions, ticket tiers, FAQ, sponsors) as a draft."""
    from datetime import timedelta
    from events.models import TicketTier, Session, Sponsor, EventFAQ
    if request.user.role not in ['organizer', 'admin']:
        messages.error(request, "Permission denied.")
        return redirect('accounts:dashboard')
    
    orig = get_object_or_404(Event, id=event_id)
    can_duplicate = (request.user.role == 'admin') or (orig.organizer == request.user)

    if not can_duplicate:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json':
            return JsonResponse({'error': 'Permission denied'}, status=403)
        messages.error(request, "Permission denied.")
        return redirect('accounts:organizer_dashboard')
    
    # Check subscription limits
    from accounts.services import check_subscription_limits
    if not check_subscription_limits(request.user.organization, 'max_events'):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json':
            return JsonResponse({'error': 'Upgrade plan to create more events.'}, status=400)
        messages.error(request, "Upgrade plan to create more events.")
        return redirect('accounts:organizer_dashboard')

    # Clone
    new_event = Event.objects.create(
        organizer=request.user,  # Set the clone organizer to the user performing the duplicate action
        organization=request.user.organization,
        title=f"Copy of {orig.title}",
        description=orig.description,
        category=orig.category,
        banner=orig.banner,
        date=orig.date + timedelta(days=7),
        time=orig.time,
        end_date=orig.end_date + timedelta(days=7) if orig.end_date else None,
        end_time=orig.end_time,
        venue=orig.venue,
        venue_ref=orig.venue_ref,
        city=orig.city,
        total_capacity=orig.total_capacity,
        ticket_price=orig.ticket_price,
        visibility=orig.visibility,
        password=orig.password,
        is_template=orig.is_template,
        rules=orig.rules,
        status='draft'
    )
    
    # Clone ticket tiers
    for tier in orig.ticket_tiers.all():
        TicketTier.objects.create(
            event=new_event,
            tier_type=tier.tier_type,
            name=tier.name,
            price=tier.price,
            capacity=tier.capacity,
            description=tier.description,
            is_active=tier.is_active,
            early_bird_deadline=tier.early_bird_deadline,
            ticket_limit_per_user=tier.ticket_limit_per_user,
            availability_timer=tier.availability_timer,
            group_size=tier.group_size
        )
    
    # Clone FAQs
    for faq in orig.faqs.all():
        EventFAQ.objects.create(
            event=new_event,
            question=faq.question,
            answer=faq.answer,
            order=faq.order
        )
        
    # Clone Sessions
    for session in orig.sessions.all():
        Session.objects.create(
            event=new_event,
            title=session.title,
            description=session.description,
            start_time=session.start_time + timedelta(days=7),
            end_time=session.end_time + timedelta(days=7),
            speaker=session.speaker
        )
        
    # Clone Sponsors
    for sponsor in orig.sponsors.all():
        Sponsor.objects.create(
            event=new_event,
            name=sponsor.name,
            logo=sponsor.logo,
            website=sponsor.website,
            tier=sponsor.tier,
            booth_number=sponsor.booth_number,
            deliverables=sponsor.deliverables
        )
        
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json' or request.GET.get('ajax') == 'true':
        return JsonResponse({'success': True, 'message': f"Event duplicated successfully as draft: '{new_event.title}'"})
        
    messages.success(request, f"Event duplicated successfully as draft: '{new_event.title}'")
    return redirect('accounts:organizer_dashboard')


@login_required
def publish_event(request, event_id):
    """Publish an event"""
    event = get_object_or_404(Event, id=event_id)
    can_manage = (request.user.role == 'admin') or (event.organizer == request.user)
    
    if not can_manage:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json':
            return JsonResponse({'error': 'Permission denied'}, status=403)
        messages.error(request, "Permission denied.")
        return redirect('accounts:organizer_dashboard')
        
    event.status = 'published'
    event.save()
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json' or request.GET.get('ajax') == 'true':
        return JsonResponse({'success': True, 'status': 'published', 'status_display': event.get_status_display()})
        
    messages.success(request, f"Event '{event.title}' published successfully.")
    return redirect('accounts:organizer_dashboard')


@login_required
def unpublish_event(request, event_id):
    """Unpublish an event (convert to draft)"""
    event = get_object_or_404(Event, id=event_id)
    can_manage = (request.user.role == 'admin') or (event.organizer == request.user)
    
    if not can_manage:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json':
            return JsonResponse({'error': 'Permission denied'}, status=403)
        messages.error(request, "Permission denied.")
        return redirect('accounts:organizer_dashboard')
        
    event.status = 'draft'
    event.save()
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json' or request.GET.get('ajax') == 'true':
        return JsonResponse({'success': True, 'status': 'draft', 'status_display': event.get_status_display()})
        
    messages.success(request, f"Event '{event.title}' unpublished (saved as draft).")
    return redirect('accounts:organizer_dashboard')

