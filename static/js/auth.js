/*
 * EventPro - Auth page interactions
 * Password visibility toggle and strength checklist
 */

document.addEventListener('DOMContentLoaded', function () {
    initPasswordToggles();
    initPasswordStrength();
});

function initPasswordToggles() {
    document.querySelectorAll('[data-toggle-password]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            const input = document.getElementById(btn.getAttribute('data-toggle-password'));
            if (!input) return;

            const isHidden = input.type === 'password';
            input.type = isHidden ? 'text' : 'password';
            btn.querySelector('i').className = isHidden ? 'bi bi-eye-slash' : 'bi bi-eye';
        });
    });
}

function initPasswordStrength() {
    const passwordInput = document.getElementById('id_password1');
    const checklist = document.getElementById('ep-password-checklist');
    if (!passwordInput || !checklist) return;

    const ruleSelector = checklist.classList.contains('ep-password-rules-light')
        ? '.ep-password-rules-light [data-rule]'
        : '[data-rule]';

    const rules = {
        length: function (value) { return value.length >= 8; },
        lower: function (value) { return /[a-z]/.test(value); },
        upper: function (value) { return /[A-Z]/.test(value); },
        number: function (value) { return /[0-9]/.test(value); },
        special: function (value) { return /[!@#$%^&*(),.?":{}|<>]/.test(value); }
    };

    passwordInput.addEventListener('input', function () {
        const value = passwordInput.value;
        Object.keys(rules).forEach(function (rule) {
            const item = checklist.querySelector('[data-rule="' + rule + '"]');
            if (!item) return;
            const met = rules[rule](value);
            item.classList.toggle('ep-rule-met', met);
            item.querySelector('i').className = met ? 'bi bi-check-circle-fill' : 'bi bi-circle';
        });
    });
}
