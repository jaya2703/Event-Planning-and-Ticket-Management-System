/**
 * EventPro — per-window session id (wsid)
 * Each browser window gets its own session so multiple users can log in at once.
 */
(function () {
    var PARAM = 'wsid';
    var STORAGE_KEY = 'eventpro_wsid';

    function newWsid() {
        if (window.crypto && crypto.randomUUID) {
            return crypto.randomUUID();
        }
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
            var r = Math.random() * 16 | 0;
            var v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    function getStoredWsid() {
        try {
            return sessionStorage.getItem(STORAGE_KEY);
        } catch (e) {
            return null;
        }
    }

    function setStoredWsid(id) {
        try {
            sessionStorage.setItem(STORAGE_KEY, id);
        } catch (e) { /* ignore */ }
    }

    function isScopedPath() {
        var path = window.location.pathname;
        return path.indexOf('/static/') !== 0 &&
            path.indexOf('/media/') !== 0 &&
            path.indexOf('/admin/') !== 0;
    }

    if (!isScopedPath()) {
        return;
    }

    var url = new URL(window.location.href);
    var urlWsid = url.searchParams.get(PARAM);
    var storedWsid = getStoredWsid();

    if (!urlWsid) {
        var wsid = storedWsid || newWsid();
        setStoredWsid(wsid);
        url.searchParams.set(PARAM, wsid);
        window.location.replace(url.toString());
        return;
    }

    if (!storedWsid || storedWsid !== urlWsid) {
        setStoredWsid(urlWsid);
    }

    window.EVENTPRO_WSID = urlWsid;

    function withWsid(href) {
        if (!href || !window.EVENTPRO_WSID) return href;
        if (href.charAt(0) === '#' || href.indexOf('javascript:') === 0 || href.indexOf('mailto:') === 0) {
            return href;
        }
        try {
            var link = new URL(href, window.location.origin);
            if (link.origin !== window.location.origin) return href;
            if (!link.searchParams.get(PARAM)) {
                link.searchParams.set(PARAM, window.EVENTPRO_WSID);
            }
            return link.pathname + link.search + link.hash;
        } catch (e) {
            return href;
        }
    }

    function patchLinks(root) {
        (root || document).querySelectorAll('a[href]').forEach(function (a) {
            var href = a.getAttribute('href');
            var patched = withWsid(href);
            if (patched && patched !== href) {
                a.setAttribute('href', patched);
            }
        });
    }

    function patchForms(root) {
        (root || document).querySelectorAll('form').forEach(function (form) {
            if (form.querySelector('input[name="' + PARAM + '"]')) return;
            var input = document.createElement('input');
            input.type = 'hidden';
            input.name = PARAM;
            input.value = window.EVENTPRO_WSID;
            form.appendChild(input);
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        patchLinks(document);
        patchForms(document);
    });

    document.addEventListener('click', function (e) {
        var a = e.target.closest('a[href]');
        if (!a) return;
        var patched = withWsid(a.getAttribute('href'));
        if (patched && patched !== a.getAttribute('href')) {
            a.setAttribute('href', patched);
        }
    }, true);

    document.addEventListener('submit', function (e) {
        var form = e.target;
        if (!form || form.tagName !== 'FORM') return;
        patchForms(form);
    }, true);
})();
