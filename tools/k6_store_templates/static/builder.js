'use strict';
(function () {
  var form = document.getElementById('builder-form');
  if (!form) return;
  var live = document.querySelector('[data-builder-live]');
  var status = document.querySelector('[data-builder-status]');
  var outTheme = document.querySelector('[data-builder-theme]');
  var outPacks = document.querySelector('[data-builder-packs-out]');
  var outCaps = document.querySelector('[data-builder-caps]');
  var outModules = document.querySelector('[data-builder-modules]');
  var outGates = document.querySelector('[data-builder-gates]');
  var buildButton = document.getElementById('build-button');
  // JS is active: require a validated preview before build.
  buildButton.disabled = true;
  var fallback = document.getElementById('fallback-result');
  if (fallback) fallback.hidden = true;
  var timer = null;
  var controller = null;
  var seq = 0;

  function selection() {
    var theme = (form.querySelector('input[name="theme"]:checked') || {}).value || 'flux';
    var packs = Array.prototype.map.call(
      form.querySelectorAll('input[name="pack"]:checked:not(:disabled)'),
      function (el) { return el.value; }
    );
    return { theme: theme, packs: packs };
  }

  function renderError(message) {
    live.hidden = false;
    status.textContent = message;
    outTheme.textContent = selection().theme;
    outPacks.textContent = '—';
    outCaps.textContent = '—';
    outModules.textContent = '—';
    outGates.textContent = '{}';
    buildButton.disabled = true;
  }

  function schedule() {
    if (timer) clearTimeout(timer);
    ++seq;
    if (controller) controller.abort();
    buildButton.disabled = true;
    live.hidden = false;
    status.textContent = 'Checking selection…';
    timer = setTimeout(preview, 250);
  }

  async function preview() {
    var sel = selection();
    var mine = ++seq;
    if (controller) controller.abort();
    controller = new AbortController();
    live.hidden = false;
    status.textContent = 'Checking selection…';
    buildButton.disabled = true;
    try {
      var res = await fetch(form.dataset.previewUrl, {
        method: 'POST',
        headers: { Accept: 'application/json' },
        body: new FormData(form),
        signal: controller.signal
      });
      var data = await res.json();
      if (mine !== seq) return; // stale response
      if (data && data.ok) {
        status.textContent = 'Selection is valid. Choose Build to start a build.';
        outTheme.textContent = (data.plan && data.plan.theme) || sel.theme;
        outPacks.textContent = (data.plan.packs || []).join(' + ') || 'base';
        outCaps.textContent = (data.plan.capabilities || []).join(', ') || '—';
        outModules.textContent = (data.plan.modules || []).join(', ') || '—';
        outGates.textContent = JSON.stringify(data.gates || {}, null, 2);
        buildButton.disabled = false;
      } else {
        renderError((data && data.error) || ('Preview failed (HTTP ' + res.status + ').'));
      }
    } catch (err) {
      if (mine !== seq || (err && err.name === 'AbortError')) return;
      renderError('Preview unavailable: ' + (err && err.message ? err.message : err));
    }
  }

  var designer = form.querySelector('input[name="pack"][value="designer"]');
  var panel = form.querySelector('[data-designer-panel]');
  function syncDesigner() {
    if (!designer || !panel) return;
    panel.hidden = !designer.checked;
    panel.querySelectorAll('input[name="theme"]').forEach(function(el) {el.disabled = !designer.checked;});
    if (!designer.checked) panel.querySelector('details').open = false;
  }
  form.addEventListener('change', function(event) {
    if (event.target === designer) syncDesigner();
    schedule();
  });
  syncDesigner();
  form.addEventListener('submit', function (event) {
    if (event.submitter === buildButton) {
      if (buildButton.disabled) event.preventDefault();
      return;
    }
    event.preventDefault();
    if (timer) clearTimeout(timer);
    preview();
  });
  // Explicit preview only; never auto-build.
  schedule();
})();
