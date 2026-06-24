/**
 * Renders ranked category performance bars from existing chart JSON data.
 * Visualization layer only — does not fetch or compute analytics.
 */
(function (global) {
    const PALETTE = ['#6366F1', '#7C73E8', '#9490E8', '#A8A3EF', '#BDB9F5', '#94A3B8'];

    function fmtCurrency(n) {
        if (n >= 100000) return '₹' + (n / 100000).toFixed(1) + 'L';
        if (n >= 1000) return '₹' + Math.round(n / 1000) + 'k';
        return '₹' + Math.round(n);
    }

    function epRenderCategoryRank(containerId, labels, values, options) {
        options = options || {};
        const mode = options.mode || 'events';
        const valueLabel = options.valueLabel || (mode === 'revenue' ? 'revenue' : 'events');
        const maxRows = options.maxRows || 6;

        const listEl = document.getElementById(containerId + '-list');
        const totalEl = document.getElementById(containerId + '-total');
        const totalLbl = document.getElementById(containerId + '-total-lbl');
        const badgeEl = document.getElementById(containerId + '-badge');
        const emptyEl = document.getElementById(containerId + '-empty');
        if (!listEl) return;

        labels = labels || [];
        values = (values || []).map(Number);
        if (!labels.length || !values.length) {
            listEl.innerHTML = '';
            if (emptyEl) emptyEl.classList.remove('d-none');
            return;
        }
        if (emptyEl) emptyEl.classList.add('d-none');

        let pairs = labels.map((name, i) => ({ name, value: values[i] || 0 }));
        if (options.filterZero) {
            pairs = pairs.filter((p) => p.value > 0);
        }
        if (!pairs.length) {
            listEl.innerHTML = '';
            if (emptyEl) emptyEl.classList.remove('d-none');
            return;
        }
        pairs.sort((a, b) => b.value - a.value);
        const top = pairs.slice(0, maxRows);
        const rest = pairs.slice(maxRows);
        if (rest.length && !options.filterZero) {
            top.push({
                name: 'Others',
                value: rest.reduce((s, r) => s + r.value, 0),
            });
        }

        const total = pairs.reduce((s, r) => s + r.value, 0) || 1;
        const leader = top[0] ? top[0].value : 0;

        if (totalEl) {
            if (mode === 'revenue') {
                totalEl.textContent = fmtCurrency(total);
                if (totalLbl) totalLbl.textContent = 'Total revenue';
            } else {
                totalEl.textContent = String(Math.round(total));
                if (totalLbl) totalLbl.textContent = 'Total events';
            }
        }
        if (badgeEl) badgeEl.textContent = pairs.length + ' categor' + (pairs.length === 1 ? 'y' : 'ies');

        listEl.innerHTML = top.map((row, idx) => {
            const pct = Math.round((row.value / total) * 1000) / 10;
            const barW = leader ? Math.max(4, Math.round((row.value / leader) * 100)) : 0;
            const color = PALETTE[Math.min(idx, PALETTE.length - 1)];
            const isLeader = idx === 0 && row.name !== 'Others';
            const growthHtml = isLeader
                ? '<span class="ep-cat-rank-growth up"><i class="bi bi-arrow-up-short"></i>Top</span>'
                : '<span class="ep-cat-rank-growth neutral">—</span>';
            const metricVal = mode === 'revenue'
                ? fmtCurrency(row.value)
                : Math.round(row.value) + ' events';

            return (
                '<div class="ep-cat-rank-row">' +
                '<div class="ep-cat-rank-row-head">' +
                '<span class="ep-cat-rank-name">' + escapeHtml(row.name) + '</span>' +
                '<span class="ep-cat-rank-pct">' + pct + '%</span>' +
                '</div>' +
                '<div class="ep-cat-rank-bar-track">' +
                '<div class="ep-cat-rank-bar-fill" style="width:' + barW + '%;background:' + color + '"></div>' +
                '</div>' +
                '<div class="ep-cat-rank-meta">' +
                '<span class="ep-cat-rank-meta-item"><i class="bi bi-' + (mode === 'revenue' ? 'currency-rupee' : 'calendar-event') + '"></i> ' + metricVal + '</span>' +
                '<span class="ep-cat-rank-meta-item ep-cat-rank-share">' + pct + '% share</span>' +
                growthHtml +
                '</div>' +
                '</div>'
            );
        }).join('');
    }

    function escapeHtml(s) {
        const d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    global.epRenderCategoryRank = epRenderCategoryRank;
})(window);
