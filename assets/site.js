/* Helm & Horizon — shared behaviour */
(function () {
  'use strict';

  /* ---- Mobile nav ---- */
  var toggle = document.querySelector('.nav__toggle');
  var nav = document.getElementById('site-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      var open = nav.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    var closeNav = function () {
      nav.classList.remove('is-open');
      toggle.setAttribute('aria-expanded', 'false');
    };
    nav.addEventListener('click', function (e) {
      if (e.target.tagName === 'A') closeNav();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && nav.classList.contains('is-open')) {
        closeNav();
        toggle.focus();
      }
    });
    document.addEventListener('click', function (e) {
      if (!nav.classList.contains('is-open')) return;
      if (!nav.contains(e.target) && !toggle.contains(e.target)) closeNav();
    });
  }

  /* ---- Scroll reveal ---- */
  var reveals = document.querySelectorAll('.reveal');
  if (reveals.length && 'IntersectionObserver' in window) {
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-in');
            io.unobserve(entry.target);
          }
        });
      },
      { rootMargin: '0px 0px -8% 0px', threshold: 0.05 }
    );
    reveals.forEach(function (el) {
      io.observe(el);
    });
  } else {
    reveals.forEach(function (el) {
      el.classList.add('is-in');
    });
  }

  /* ---- Current year ---- */
  document.querySelectorAll('[data-year]').forEach(function (el) {
    el.textContent = String(new Date().getFullYear());
  });

  /* ----------------------------------------------------------------------
     Subscription + submission forms.
     Posts JSON to the endpoint in data-endpoint. Falls back to a mailto
     handoff when no endpoint is configured yet, so the site is never a
     dead end before the backend is wired up.
     ---------------------------------------------------------------------- */
  document.querySelectorAll('form[data-hh-form]').forEach(function (form) {
    var status = form.querySelector('.form__status');
    var button = form.querySelector('button[type="submit"]');
    var endpoint = form.getAttribute('data-endpoint') || '';

    function setStatus(msg, ok) {
      if (!status) return;
      status.textContent = msg;
      status.className = 'form__status ' + (ok ? 'is-ok' : 'is-err');
    }

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var data = {};
      new FormData(form).forEach(function (v, k) {
        data[k] = typeof v === 'string' ? v.trim() : v;
      });

      if (!data.email || !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(data.email)) {
        setStatus('Please enter a valid email address.', false);
        return;
      }

      /* No backend configured yet — hand off to email so nothing is lost. */
      if (!endpoint || endpoint.indexOf('REPLACE') === 0) {
        var kind = form.getAttribute('data-hh-form');
        var subject =
          kind === 'submission'
            ? 'Helm & Horizon — outlook submission'
            : 'Helm & Horizon — subscribe';
        var lines = Object.keys(data).map(function (k) {
          return k + ': ' + data[k];
        });
        var href =
          'mailto:editor@thehelmandhorizon.com?subject=' +
          encodeURIComponent(subject) +
          '&body=' +
          encodeURIComponent(lines.join('\n'));

        /* Windows and several mail clients silently drop mailto: URLs past
           roughly 2,000 characters, which would lose a long submission. */
        if (href.length > 1800) {
          setStatus(
            'Your submission is too long to hand off by email link. Please email it directly to editor@thehelmandhorizon.com — the hosted form endpoint is not connected yet.',
            false
          );
          return;
        }

        setStatus(
          'Opening your email client to complete the request. The hosted form endpoint is not connected yet.',
          true
        );
        window.location.href = href;
        return;
      }

      if (button) {
        button.disabled = true;
        button.dataset.label = button.textContent;
        button.textContent = 'Sending...';
      }

      fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      })
        .then(function (res) {
          return res
            .json()
            .catch(function () {
              return {};
            })
            .then(function (payload) {
              /* Surface the server's own message so a reader is told what
                 actually went wrong rather than a blanket failure. */
              if (!res.ok) {
                var e = new Error(payload.error || 'HTTP ' + res.status);
                /* Only trust the message when the API actually supplied one.
                   A bare status code is not something to show a reader. */
                e.fromServer = typeof payload.error === 'string' && payload.error.length > 0;
                throw e;
              }
              return payload;
            });
        })
        .then(function (payload) {
          form.reset();
          /* The API distinguishes "confirmation sent" from "already on the
             list", so prefer its message over the form's generic one. */
          setStatus(
            (payload && payload.message) ||
              form.getAttribute('data-success') ||
              'Thank you. Check your inbox to confirm your subscription.',
            true
          );
        })
        .catch(function (err) {
          /* Network-level failures carry browser text like "Failed to fetch",
             so only show a message that actually came from our API. */
          setStatus(
            err && err.fromServer
              ? err.message
              : 'Something went wrong. Please email editor@thehelmandhorizon.com and we will add you manually.',
            false
          );
        })
        .finally(function () {
          if (button) {
            button.disabled = false;
            button.textContent = button.dataset.label || 'Submit';
          }
        });
    });
  });
})();
