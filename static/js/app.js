/* Бригадир.Про — PWA, тёмная тема, автосохранение (разделы 7.4–7.5 ТЗ) */
(function () {
  'use strict';

  // --- Service Worker ---
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(function () {});
    });
  }

  // --- Тёмная тема ---
  var root = document.documentElement;
  function currentTheme() {
    return root.getAttribute('data-theme') || 'light';
  }
  function applyTheme(theme) {
    root.setAttribute('data-theme', theme);
    try { localStorage.setItem('theme', theme); } catch (e) {}
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', theme === 'dark' ? '#1b1a18' : '#262421');
    document.querySelectorAll('[data-theme-toggle]').forEach(function (b) {
      b.textContent = theme === 'dark' ? '☀' : '☾';
      b.setAttribute('aria-label', theme === 'dark' ? 'Светлая тема' : 'Тёмная тема');
    });
  }
  document.addEventListener('click', function (e) {
    var t = e.target.closest('[data-theme-toggle]');
    if (!t) return;
    applyTheme(currentTheme() === 'dark' ? 'light' : 'dark');
  });
  applyTheme(currentTheme());

  // --- Установка на домашний экран ---
  var deferredPrompt = null;
  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    deferredPrompt = e;
    document.querySelectorAll('[data-install]').forEach(function (b) { b.classList.remove('hidden'); });
  });
  document.addEventListener('click', function (e) {
    var t = e.target.closest('[data-install]');
    if (!t || !deferredPrompt) return;
    deferredPrompt.prompt();
    deferredPrompt.userChoice.finally(function () {
      deferredPrompt = null;
      document.querySelectorAll('[data-install]').forEach(function (b) { b.classList.add('hidden'); });
    });
  });
  window.addEventListener('appinstalled', function () {
    document.querySelectorAll('[data-install]').forEach(function (b) { b.classList.add('hidden'); });
  });

  // --- Автосохранение черновиков форм каждые 10 секунд (раздел 7.4 ТЗ) ---
  function autosaveKey(form) {
    return 'draft:' + location.pathname + ':' + (form.getAttribute('data-autosave') || 'form');
  }
  function fieldsOf(form) {
    return Array.prototype.slice.call(form.querySelectorAll('input, textarea, select')).filter(function (el) {
      return el.name && el.type !== 'password' && el.type !== 'file' && el.type !== 'hidden' && el.type !== 'submit';
    });
  }
  function restore(form) {
    var raw;
    try { raw = localStorage.getItem(autosaveKey(form)); } catch (e) { return; }
    if (!raw) return;
    var data;
    try { data = JSON.parse(raw); } catch (e) { return; }
    fieldsOf(form).forEach(function (el) {
      if (!(el.name in data)) return;
      if (el.type === 'checkbox') el.checked = !!data[el.name];
      else if (!el.value) el.value = data[el.name];
    });
    var note = form.querySelector('[data-autosave-note]');
    if (note) note.classList.remove('hidden');
  }
  function save(form) {
    var data = {};
    fieldsOf(form).forEach(function (el) {
      data[el.name] = el.type === 'checkbox' ? el.checked : el.value;
    });
    try { localStorage.setItem(autosaveKey(form), JSON.stringify(data)); } catch (e) {}
  }
  document.querySelectorAll('form[data-autosave]').forEach(function (form) {
    restore(form);
    setInterval(function () { save(form); }, 10000);
    form.addEventListener('submit', function () {
      try { localStorage.removeItem(autosaveKey(form)); } catch (e) {}
    });
    var clearBtn = form.querySelector('[data-autosave-clear]');
    if (clearBtn) clearBtn.addEventListener('click', function () {
      try { localStorage.removeItem(autosaveKey(form)); } catch (e) {}
      location.reload();
    });
  });
})();
