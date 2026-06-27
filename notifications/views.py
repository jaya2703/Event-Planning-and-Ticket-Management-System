from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from accounts.models import Notification


@login_required
def notification_list(request):
    if request.user.role == 'admin':
        return redirect('accounts:admin_dashboard')
    
    # Evaluate the queryset first to preserve is_read=False for the template rendering
    notifications = list(Notification.objects.filter(user=request.user).order_by('-created_at'))
    
    # Calculate unread count before marking them read
    unread_count = sum(1 for n in notifications if not n.is_read)
    
    # Mark them as read in the database
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    
    return render(request, 'notifications/list.html', {
        'notifications': notifications,
        'unread_count_before': unread_count,
    })
