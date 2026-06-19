/*
 * EventPro - Main JavaScript
 * Simple, beginner-friendly JS for interactions
 */

// ── Auto-dismiss alerts after 5 seconds ──
document.addEventListener('DOMContentLoaded', function() {
    // Find all dismissible alerts
    const alerts = document.querySelectorAll('.alert.alert-dismissible');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            // Fade out the alert
            alert.style.transition = 'opacity 0.5s ease';
            alert.style.opacity = '0';
            setTimeout(function() { alert.remove(); }, 500);
        }, 5000); // 5 seconds
    });
});

// ── Navbar active link highlight ──
document.addEventListener('DOMContentLoaded', function() {
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(function(link) {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });
});

// ── Smooth scroll to top button ──
// Create a scroll-to-top button dynamically
document.addEventListener('DOMContentLoaded', function() {
    // Create the button
    const scrollBtn = document.createElement('button');
    scrollBtn.innerHTML = '<i class="bi bi-arrow-up"></i>';
    scrollBtn.className = 'ep-scroll-top-btn';
    scrollBtn.style.cssText = `
        position: fixed; bottom: 2rem; right: 2rem;
        width: 44px; height: 44px;
        background: linear-gradient(135deg, #6c5ce7, #a29bfe);
        color: white; border: none; border-radius: 12px;
        cursor: pointer; display: none; z-index: 9999;
        box-shadow: 0 4px 15px rgba(108,92,231,0.4);
        font-size: 1.1rem; transition: all 0.3s ease;
    `;

    document.body.appendChild(scrollBtn);

    // Show/hide based on scroll position
    window.addEventListener('scroll', function() {
        if (window.scrollY > 300) {
            scrollBtn.style.display = 'block';
        } else {
            scrollBtn.style.display = 'none';
        }
    });

    // Scroll to top on click
    scrollBtn.addEventListener('click', function() {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
});

// ── Image preview before upload ──
// When user selects a file (like event banner or profile pic), show a preview
function previewImage(inputId, previewId) {
    const input = document.getElementById(inputId);
    const preview = document.getElementById(previewId);

    if (input && preview) {
        input.addEventListener('change', function() {
            const file = this.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    preview.src = e.target.result;
                    preview.style.display = 'block';
                };
                reader.readAsDataURL(file);
            }
        });
    }
}

// ── Form loading state ──
// When a form is submitted, disable the button to prevent double-click
document.addEventListener('DOMContentLoaded', function() {
    const forms = document.querySelectorAll('form');
    forms.forEach(function(form) {
        form.addEventListener('submit', function() {
            const submitBtn = form.querySelector('[type="submit"]');
            if (submitBtn) {
                const originalText = submitBtn.innerHTML;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Loading...';
                submitBtn.disabled = true;

                // Re-enable after 10 seconds (in case of slow network)
                setTimeout(function() {
                    submitBtn.innerHTML = originalText;
                    submitBtn.disabled = false;
                }, 10000);
            }
        });
    });
});

// ── Tooltip initialization (Bootstrap 5) ──
document.addEventListener('DOMContentLoaded', function() {
    const tooltipTriggerList = [].slice.call(
        document.querySelectorAll('[data-bs-toggle="tooltip"]')
    );
    tooltipTriggerList.map(function(el) {
        return new bootstrap.Tooltip(el);
    });
});

// ── Counter animation for dashboard stats ──
function animateCounter(element, target, duration) {
    let start = 0;
    const step = target / (duration / 16); // 60fps

    const timer = setInterval(function() {
        start += step;
        if (start >= target) {
            element.textContent = target;
            clearInterval(timer);
        } else {
            element.textContent = Math.floor(start);
        }
    }, 16);
}

// Run counter animations when elements are visible
document.addEventListener('DOMContentLoaded', function() {
    const statNums = document.querySelectorAll('.ep-stat-num');
    statNums.forEach(function(el) {
        const text = el.textContent.trim();
        // Only animate if it's a plain number
        const num = parseInt(text.replace(/[^0-9]/g, ''));
        if (!isNaN(num) && num > 0 && !text.includes('₹') && !text.includes('%')) {
            el.textContent = '0';
            setTimeout(function() {
                animateCounter(el, num, 1000);
            }, 200);
        }
    });
});
