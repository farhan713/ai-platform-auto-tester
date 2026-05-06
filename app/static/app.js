// Shared client-side utilities for the Skylar IQ QA Tool.
// Exposes window.SQA = { toast, escapeHtml, fetchJSON }.

(function () {
  // ---- Theme toggle (persisted to localStorage) -----------------------------
  const themeBtn = document.getElementById('theme-toggle');
  const themeIcon = document.getElementById('theme-icon');
  function applyTheme(t) {
    document.documentElement.setAttribute('data-theme', t);
    if (themeIcon) themeIcon.textContent = t === 'dark' ? '☀' : '🌙';
  }
  applyTheme(localStorage.getItem('skylar.theme') || 'light');
  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      const cur = document.documentElement.getAttribute('data-theme') || 'light';
      const next = cur === 'dark' ? 'light' : 'dark';
      localStorage.setItem('skylar.theme', next);
      applyTheme(next);
    });
  }

  // ---- Toasts ---------------------------------------------------------------
  function toast(msg, kind) {
    const c = document.getElementById('toasts');
    if (!c) return;
    const el = document.createElement('div');
    el.className = 'toast ' + (kind || 'info');
    el.textContent = msg;
    c.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }, 4500);
  }

  // ---- Helpers --------------------------------------------------------------
  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;').replaceAll("'", '&#39;');
  }
  async function fetchJSON(url, opts) {
    const r = await fetch(url, opts);
    if (!r.ok) {
      let body = '';
      try { body = await r.text(); } catch (e) {}
      throw new Error('HTTP ' + r.status + ' ' + (body || ''));
    }
    return await r.json();
  }
  function fmtDuration(ms) {
    if (ms == null) return '-';
    if (ms < 1000) return ms + ' ms';
    return (ms / 1000).toFixed(1) + ' s';
  }
  function fmtDate(iso) {
    if (!iso) return '-';
    try {
      const d = new Date(iso);
      return d.toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
    } catch (e) { return iso; }
  }

  // ---- Tab controller -------------------------------------------------------
  function initTabs(root) {
    root = root || document;
    root.querySelectorAll('.tabs').forEach(group => {
      const tabs = group.querySelectorAll('.tab');
      tabs.forEach(tab => {
        tab.addEventListener('click', () => {
          const target = tab.dataset.tab;
          tabs.forEach(t => t.classList.toggle('active', t === tab));
          document.querySelectorAll('.tab-panel').forEach(p => {
            p.classList.toggle('active', p.dataset.panel === target);
          });
          // Update URL hash for deep-linking
          if (history.replaceState) history.replaceState(null, '', '#' + target);
        });
      });
      // Open tab from hash on load
      const hash = (location.hash || '').replace(/^#/, '');
      if (hash) {
        const tab = group.querySelector(`.tab[data-tab="${hash}"]`);
        if (tab) tab.click();
      }
    });
  }
  document.addEventListener('DOMContentLoaded', () => initTabs());

  window.SQA = { toast, escapeHtml, fetchJSON, fmtDuration, fmtDate, initTabs };
})();
