/** EventPro Enterprise — SweetAlert toasts, confirm dialogs, admin sidebar accordion */
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-confirm]').forEach(function (el) {
        el.addEventListener('click', function (e) {
            e.preventDefault();
            const href = el.getAttribute('href');
            const msg = el.getAttribute('data-confirm') || 'Are you sure?';
            Swal.fire({
                title: 'Confirm',
                text: msg,
                icon: 'question',
                showCancelButton: true,
                confirmButtonColor: '#6366F1',
                cancelButtonColor: '#94A3B8',
                confirmButtonText: 'Yes, proceed'
            }).then(function (r) { if (r.isConfirmed && href) window.location.href = href; });
        });
    });

    document.querySelectorAll('.ep-alert.alert-success').forEach(function (el) {
        const text = el.textContent.trim();
        if (text && typeof Swal !== 'undefined') {
            Swal.fire({ toast: true, position: 'top-end', icon: 'success', title: text.slice(0, 80), showConfirmButton: false, timer: 3500 });
        }
    });

    initAdminSidebarAccordion();
});

function initAdminSidebarAccordion() {
    const accordion = document.getElementById('epAdminNavAccordion');
    if (!accordion) return;

    const STORAGE_KEY = 'epAdminNavGroups';
    let saved = {};
    try {
        saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '{}');
    } catch (e) { saved = {}; }

    const groups = accordion.querySelectorAll('.ep-nav-group');

    function setOpen(group, open) {
        const id = group.dataset.navGroup;
        const btn = group.querySelector('.ep-nav-group-btn');
        group.classList.toggle('is-open', open);
        if (btn) btn.setAttribute('aria-expanded', open ? 'true' : 'false');
        if (id) saved[id] = open;
    }

    groups.forEach(function (group) {
        const id = group.dataset.navGroup;
        const hasActive = !!group.querySelector('.ep-nav-subitem.active');
        const shouldOpen = hasActive || (id && saved[id] === true) || group.classList.contains('is-open');
        setOpen(group, shouldOpen);

        const btn = group.querySelector('.ep-nav-group-btn');
        if (btn) {
            btn.addEventListener('click', function () {
                const isOpen = group.classList.contains('is-open');
                setOpen(group, !isOpen);
                try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(saved)); } catch (e) {}
            });
        }
    });

    try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(saved)); } catch (e) {}

    const sidebar = document.getElementById('epAppSidebar');
    const fab = document.getElementById('epSidebarFab');
    const backdrop = document.getElementById('epSidebarBackdrop');

    function closeMobile() {
        sidebar?.classList.remove('is-mobile-open');
        backdrop?.classList.remove('is-visible');
        document.body.classList.remove('ep-sidebar-open');
    }
    function openMobile() {
        sidebar?.classList.add('is-mobile-open');
        backdrop?.classList.add('is-visible');
        document.body.classList.add('ep-sidebar-open');
    }

    fab?.addEventListener('click', openMobile);
    backdrop?.addEventListener('click', closeMobile);
    accordion.querySelectorAll('.ep-nav-subitem, .ep-nav-direct').forEach(function (link) {
        link.addEventListener('click', function () {
            if (window.innerWidth < 992) closeMobile();
        });
    });
}
