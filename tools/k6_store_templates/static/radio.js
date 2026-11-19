'use strict';
(function () {
  var boxes = Array.prototype.slice.call(document.querySelectorAll('[data-module-select]'));
  var selectAll = document.querySelector('[data-select-all]');
  var button = document.querySelector('[data-remove-selected]');
  var count = document.querySelector('[data-selection-count]');
  function update() {
    var selected = boxes.filter(function (box) { return box.checked; }).length;
    if (button) button.disabled = selected === 0;
    if (count) count.textContent = selected + ' selected';
    if (selectAll) {
      selectAll.checked = boxes.length > 0 && selected === boxes.length;
      selectAll.indeterminate = selected > 0 && selected < boxes.length;
    }
  }
  boxes.forEach(function (box) { box.addEventListener('change', update); });
  if (selectAll) selectAll.addEventListener('change', function () {
    boxes.forEach(function (box) { box.checked = selectAll.checked; });
    update();
  });
  document.querySelectorAll('form[data-confirm]').forEach(function (form) {
    form.addEventListener('submit', function (event) {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });
  update();
})();
