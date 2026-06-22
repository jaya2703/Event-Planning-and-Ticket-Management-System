/** EventPro Enterprise — SweetAlert toasts, confirm dialogs */
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
});
