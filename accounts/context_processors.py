def sidebar_context(request):
    if request.user.is_authenticated:
        from accounts.models import Notification
        unread = Notification.objects.filter(user=request.user, is_read=False).count()
        return {'sidebar_unread_notifications': unread}
    return {'sidebar_unread_notifications': 0}


def window_session_context(request):
    wsid = getattr(request, 'wsid', None)
    return {'wsid': wsid}
