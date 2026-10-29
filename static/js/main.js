/* ==========================================================================
   main.js - small scripts used on every page
     1. dark / light mode switch
     2. mobile menu
     3. flash messages (close button + auto-hide)
     4. confirm box for forms with data-confirm="..."
     5. Show / Hide on password fields
     6. admin Students page: reveal passwords
     7. dashboard accuracy chart
     8. upload page: live word count
   (Typing / listening scripts are in assignment.js)
   ========================================================================== */
(function () {
  'use strict';

  /* ---------- 1. DARK / LIGHT MODE ----------
     The theme is stored as data-theme="light|dark" on <html> (set in base.html before the
     page paints). The colours for each theme are in static/css/style.css (section 1). */
  var THEME_KEY = 'steno-theme';
  var themeBtn = document.getElementById('theme-toggle');
  if (themeBtn) {
    themeBtn.addEventListener('click', function () {
      var root = document.documentElement;
      var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      try { localStorage.setItem(THEME_KEY, next); } catch (e) { /* private mode: ignore */ }
    });
  }

  /* ---------- 2. MOBILE MENU ---------- */
  var navBtn = document.getElementById('nav-toggle');
  var nav = document.getElementById('main-nav');
  if (navBtn && nav) {
    navBtn.addEventListener('click', function () {
      var open = nav.classList.toggle('is-open');
      navBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  /* ---------- 3. FLASH MESSAGES ---------- */
  var AUTO_HIDE_MS = 7000;            // EDIT: how long a message stays (milliseconds)
  document.querySelectorAll('.messages .message').forEach(function (box) {
    var close = box.querySelector('[data-dismiss]');
    if (close) close.addEventListener('click', function () { box.remove(); });
    setTimeout(function () { box.remove(); }, AUTO_HIDE_MS);
  });

  /* ---------- 4. CONFIRM BEFORE SUBMITTING (e.g. delete buttons) ---------- */
  document.querySelectorAll('form[data-confirm]').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      if (!window.confirm(form.getAttribute('data-confirm'))) e.preventDefault();
    });
  });

  /* ---------- 5. SHOW / HIDE PASSWORD ---------- */
  document.querySelectorAll('[data-toggle-password]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var input = btn.parentElement.querySelector('input');
      if (!input) return;
      var show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.textContent = show ? 'Hide' : 'Show';
    });
  });

  /* ---------- 6. ADMIN: reveal student passwords ---------- */
  function setPw(code, btn, show) {
    code.textContent = show ? code.getAttribute('data-pw') : '••••••';
    code.classList.toggle('revealed', show);
    if (btn) btn.textContent = show ? 'Hide' : 'Show';
  }
  document.querySelectorAll('[data-pw-toggle]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var code = btn.parentElement.querySelector('[data-pw]');
      setPw(code, btn, !code.classList.contains('revealed'));
    });
  });
  var showAll = document.getElementById('pw-show-all');
  if (showAll) {
    showAll.addEventListener('click', function () {
      var reveal = showAll.getAttribute('data-on') !== '1';
      document.querySelectorAll('[data-pw]').forEach(function (code) {
        setPw(code, code.parentElement.querySelector('[data-pw-toggle]'), reveal);
      });
      showAll.setAttribute('data-on', reveal ? '1' : '0');
      showAll.textContent = reveal ? 'Hide all passwords' : 'Show all passwords';
    });
  }

  /* ---------- 7. DASHBOARD CHART (accuracy of the last sessions) ---------- */
  var chartBox = document.getElementById('trend-chart');
  var dataTag = document.getElementById('trend-data');
  if (chartBox && dataTag) {
    var values = JSON.parse(dataTag.textContent);
    var W = 600, H = 160, padL = 34, padR = 10, padT = 10, padB = 20;
    var lo = Math.max(0, Math.floor((Math.min.apply(null, values) - 5) / 10) * 10);   // chart floor
    var hi = 100;
    var x = function (i) { return padL + (i * (W - padL - padR)) / Math.max(1, values.length - 1); };
    var y = function (v) { return padT + (1 - (v - lo) / (hi - lo)) * (H - padT - padB); };
    var svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none">';
    [lo, (lo + hi) / 2, hi].forEach(function (g) {
      svg += '<line class="trend-grid" x1="' + padL + '" x2="' + (W - padR) + '" y1="' + y(g) + '" y2="' + y(g) + '"/>' +
             '<text class="trend-label" x="0" y="' + (y(g) + 4) + '">' + Math.round(g) + '%</text>';
    });
    svg += '<polyline class="trend-line" points="' + values.map(function (v, i) { return x(i) + ',' + y(v); }).join(' ') + '"/>';
    values.forEach(function (v, i) { svg += '<circle class="trend-dot" cx="' + x(i) + '" cy="' + y(v) + '" r="4"/>'; });
    chartBox.innerHTML = svg + '</svg>';
  }

  /* ---------- 8. UPLOAD PAGE: live word count ---------- */
  var para = document.getElementById('id_paragraph_text');
  var wc = document.getElementById('word-count');
  if (para && wc && !document.getElementById('typing-form')) {
    var count = function () { wc.textContent = para.value.trim() ? para.value.trim().split(/\s+/).length : 0; };
    para.addEventListener('input', count);
    count();
  }
})();
