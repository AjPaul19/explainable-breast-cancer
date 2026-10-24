/* GCMN theme: the menu, scroll reveal and copy-to-clipboard. No libraries. */
(function () {
  'use strict';
  var root = document.documentElement;
  root.classList.remove('no-js');

  /* ---- full-screen menu with focus trap ---- */
  var btn = document.querySelector('.menu-btn');
  var sheet = document.getElementById('menu-sheet');
  if (btn && sheet) {
    var closeBtn = sheet.querySelector('.sheet-x');
    var lastFocus = null;
    var focusable = function () {
      return sheet.querySelectorAll('a[href], button:not([disabled])');
    };
    var open = function () {
      lastFocus = document.activeElement;
      sheet.hidden = false;
      btn.setAttribute('aria-expanded', 'true');
      document.body.style.overflow = 'hidden';
      var f = focusable();
      if (f.length) { f[0].focus(); }
    };
    var close = function () {
      sheet.hidden = true;
      btn.setAttribute('aria-expanded', 'false');
      document.body.style.overflow = '';
      if (lastFocus) { lastFocus.focus(); }
    };
    btn.addEventListener('click', open);
    closeBtn.addEventListener('click', close);
    sheet.addEventListener('click', function (e) {
      if (e.target.closest('a')) { document.body.style.overflow = ''; }
    });
    document.addEventListener('keydown', function (e) {
      if (sheet.hidden) { return; }
      if (e.key === 'Escape') { close(); return; }
      if (e.key === 'Tab') {
        var f = focusable();
        if (!f.length) { return; }
        var first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    });
  }

  /* ---- reveal on scroll ---- */
  var items = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); }
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
    items.forEach(function (el) { io.observe(el); });
  } else {
    items.forEach(function (el) { el.classList.add('in'); });
  }

  /* ---- copy an account number ---- */
  document.addEventListener('click', function (e) {
    var b = e.target.closest('button.copy');
    if (!b) { return; }
    var text = b.getAttribute('data-copy');
    var done = function () {
      var old = b.textContent;
      b.textContent = 'Copied';
      setTimeout(function () { b.textContent = old; }, 1800);
    };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(done);
    } else {
      var t = document.createElement('textarea');
      t.value = text; t.setAttribute('readonly', ''); t.style.position = 'fixed'; t.style.opacity = '0';
      document.body.appendChild(t); t.select();
      try { document.execCommand('copy'); done(); } catch (err) { /* nothing to do */ }
      document.body.removeChild(t);
    }
  });
})();

/* ---- alive pages: numbers count up, tiles follow the cursor, banners drift, a reading bar ---- */
(function () {
  'use strict';
  var calm = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // tiles: a light that follows the pointer
  document.addEventListener('pointermove', function (e) {
    var t = e.target.closest && e.target.closest('.g-tile');
    if (!t) { return; }
    var r = t.getBoundingClientRect();
    t.style.setProperty('--mx', (e.clientX - r.left) + 'px');
    t.style.setProperty('--my', (e.clientY - r.top) + 'px');
  }, { passive: true });

  // numbers count up when they come into view (years are left as they are)
  var nums = document.querySelectorAll('.g-stat-n');
  if (nums.length && !calm && 'IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) { return; }
        io.unobserve(en.target);
        var el = en.target, raw = el.textContent.trim(), n = parseInt(raw.replace(/[^\d]/g, ''), 10);
        if (!n || (n >= 1800 && n <= 2100)) { return; }
        var start = null, dur = 1100;
        function tick(ts) {
          if (start === null) { start = ts; }
          var p = Math.min(1, (ts - start) / dur), v = Math.round(n * (1 - Math.pow(1 - p, 3)));
          el.textContent = raw.replace(String(n), String(v));
          if (p < 1) { requestAnimationFrame(tick); } else { el.textContent = raw; }
        }
        requestAnimationFrame(tick);
      });
    }, { threshold: 0.4 });
    nums.forEach(function (n) { io.observe(n); });
  }

  // banners: the picture moves a little slower than the page
  var banner = document.querySelector('.g-banner.g-has-bg');
  if (banner && !calm) {
    var ticking = false;
    window.addEventListener('scroll', function () {
      if (ticking) { return; }
      ticking = true;
      requestAnimationFrame(function () {
        var y = Math.min(window.scrollY, 600);
        banner.style.backgroundPosition = 'center ' + (50 + y / 12) + '%';
        ticking = false;
      });
    }, { passive: true });
  }

  // reading pages: a thin bar shows how far you have read
  if (document.querySelector('.g-doc .g-prose')) {
    var bar = document.createElement('div');
    bar.className = 'g-progress';
    bar.setAttribute('aria-hidden', 'true');
    document.body.appendChild(bar);
    var upd = function () {
      var h = document.documentElement.scrollHeight - window.innerHeight;
      bar.style.width = (h > 0 ? Math.min(100, (window.scrollY / h) * 100) : 0) + '%';
    };
    window.addEventListener('scroll', upd, { passive: true });
    upd();
  }
})();
