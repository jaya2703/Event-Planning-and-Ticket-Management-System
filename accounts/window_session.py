"""Per-window session helpers (multi-user in same browser)."""
import re
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
WSID_PATTERN = re.compile(r'^[a-f0-9-]{36}$', re.IGNORECASE)
WSID_PARAM = 'wsid'


def is_valid_wsid(wsid):
    return bool(wsid and WSID_PATTERN.match(wsid))


def get_wsid_from_request(request):
    wsid = (
        request.GET.get(WSID_PARAM)
        or request.POST.get(WSID_PARAM)
        or request.headers.get('X-Window-Session', '').strip()
    )
    if is_valid_wsid(wsid):
        return wsid

    referer = request.META.get('HTTP_REFERER', '')
    if referer:
        qs = parse_qs(urlsplit(referer).query)
        candidate = (qs.get(WSID_PARAM) or [None])[0]
        if is_valid_wsid(candidate):
            return candidate

    return None


def should_scope_request(request):
    path = request.path
    if path.startswith('/static/') or path.startswith('/media/'):
        return False
    if path.startswith('/admin/'):
        return False
    return True


def append_wsid_to_url(url, wsid):
    if not url or not wsid or WSID_PARAM in url:
        return url

    parts = urlsplit(url)
    if parts.scheme and parts.netloc:
        return url

    query = parse_qs(parts.query, keep_blank_values=True)
    query[WSID_PARAM] = [wsid]
    return urlunsplit((
        parts.scheme,
        parts.netloc,
        parts.path,
        urlencode(query, doseq=True),
        parts.fragment,
    ))
