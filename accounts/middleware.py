from django.contrib.sessions.backends.db import SessionStore
from django.utils.deprecation import MiddlewareMixin

from .models import WindowSession
from .window_session import append_wsid_to_url, get_wsid_from_request, should_scope_request


class WindowSessionMiddleware(MiddlewareMixin):
    """
    Map each browser window/tab to its own Django session via wsid.
    Allows multiple users to stay logged in across separate windows.
    """

    def process_request(self, request):
        request.wsid = None
        if not should_scope_request(request):
            return None

        wsid = get_wsid_from_request(request)
        if not wsid:
            return None

        request.wsid = wsid
        request.session = self._load_session(wsid)
        request._window_scoped_session = True
        return None

    def process_response(self, request, response):
        if not getattr(request, '_window_scoped_session', False):
            return response

        wsid = getattr(request, 'wsid', None)
        if not wsid:
            return response

        if hasattr(request, 'session'):
            request.session.save()
            session_key = request.session.session_key
            if session_key:
                WindowSession.objects.filter(wsid=wsid).update(session_key=session_key)

        if hasattr(response, 'status_code') and response.status_code in (301, 302, 303, 307, 308):
            location = response.get('Location', '')
            if location:
                response['Location'] = append_wsid_to_url(location, wsid)

        return response

    def _load_session(self, wsid):
        mapping = WindowSession.objects.filter(wsid=wsid).first()
        if mapping:
            store = SessionStore(session_key=mapping.session_key)
            if store.exists(mapping.session_key):
                return store
            mapping.delete()

        store = SessionStore()
        store.create()
        WindowSession.objects.create(wsid=wsid, session_key=store.session_key)
        return store
