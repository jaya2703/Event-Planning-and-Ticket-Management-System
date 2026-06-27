from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import AttendeeProfile, MeetingRequest
from accounts.models import CustomUser
from events.models import Event
from django.utils import timezone
from accounts.services import notify

@login_required
def attendee_directory(request):
    """Browse attendees directory with matchmaking."""
    profile, _ = AttendeeProfile.objects.get_or_create(user=request.user)
    
    # Active matchmaking: find users with overlapping interests
    my_interests = set(i.strip().lower() for i in (profile.skills_interests or '').split(',') if i.strip())
    
    profiles = AttendeeProfile.objects.filter(opt_in_networking=True).exclude(user=request.user).select_related('user')
    
    search_query = request.GET.get('search', '').strip()
    if search_query:
        profiles = profiles.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(company__icontains=search_query) |
            Q(job_title__icontains=search_query) |
            Q(skills_interests__icontains=search_query)
        )
        
    matches = []
    others = []
    for p in profiles:
        p_interests = set(i.strip().lower() for i in (p.skills_interests or '').split(',') if i.strip())
        overlap = my_interests.intersection(p_interests)
        p.match_score = len(overlap)
        p.common_interests = ", ".join(overlap)
        if p.match_score > 0:
            matches.append(p)
        else:
            others.append(p)
            
    matches.sort(key=lambda x: x.match_score, reverse=True)
    
    # Get user's events to propose meetings for
    my_events = Event.objects.filter(bookings__user=request.user, bookings__status='confirmed')
    
    return render(request, 'networking/directory.html', {
        'profile': profile,
        'matches': matches,
        'others': others,
        'my_events': my_events,
    })


@login_required
def update_networking_profile(request):
    """Create or update attendee digital business card."""
    profile, _ = AttendeeProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        profile.company = request.POST.get('company', '').strip()
        profile.job_title = request.POST.get('job_title', '').strip()
        profile.bio = request.POST.get('bio', '').strip()
        profile.skills_interests = request.POST.get('skills_interests', '').strip()
        profile.opt_in_networking = 'opt_in_networking' in request.POST
        profile.save()
        messages.success(request, "Networking profile updated successfully!")
    return redirect('networking:directory')


@login_required
def meeting_list(request):
    """View sent and received meeting requests."""
    sent = MeetingRequest.objects.filter(sender=request.user).select_related('receiver', 'event')
    received = MeetingRequest.objects.filter(receiver=request.user).select_related('sender', 'event')
    return render(request, 'networking/meetings.html', {
        'sent_requests': sent,
        'received_requests': received
    })


@login_required
def send_meeting_request(request, receiver_id):
    """Propose a meeting with another attendee."""
    receiver = get_object_or_404(CustomUser, id=receiver_id)
    if request.method == 'POST':
        event_id = request.POST.get('event_id')
        proposed_time = request.POST.get('proposed_time')
        message = request.POST.get('message', '').strip()
        
        event = get_object_or_404(Event, id=event_id)
        
        MeetingRequest.objects.create(
            sender=request.user,
            receiver=receiver,
            event=event,
            proposed_time=proposed_time,
            message=message,
            status='pending'
        )
        notify(receiver, f"New meeting request from {request.user.get_full_name()}", 'general')
        messages.success(request, f"Meeting request sent to {receiver.get_full_name()}!")
        
    return redirect('networking:directory')


@login_required
def respond_meeting_request(request, meeting_id):
    """Accept or decline meeting requests."""
    meeting = get_object_or_404(MeetingRequest, id=meeting_id, receiver=request.user)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'accept':
            meeting.status = 'accepted'
            meeting.table_number = request.POST.get('table_number', f"Table {timezone.now().second % 20 + 1}")
            meeting.save()
            notify(meeting.sender, f"Meeting request accepted by {request.user.get_full_name()}", 'general')
            messages.success(request, "Meeting request accepted.")
        elif action == 'decline':
            meeting.status = 'declined'
            meeting.save()
            notify(meeting.sender, f"Meeting request declined by {request.user.get_full_name()}", 'general')
            messages.warning(request, "Meeting request declined.")
            
    return redirect('networking:meetings')
