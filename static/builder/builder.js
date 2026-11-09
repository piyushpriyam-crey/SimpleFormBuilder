(function () {
  'use strict';

  var CHOICE_TYPES = ['select', 'radio', 'checkbox'];
  var LENGTH_TYPES = ['text', 'textarea', 'email', 'password', 'url', 'hidden'];
  var RANGE_TYPES = ['number'];
  var HEADING_TYPES = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'];
  var TYPE_LABELS = {
    text: 'Text', textarea: 'Textarea', email: 'Email', password: 'Password',
    number: 'Number', url: 'URL', date: 'Date', select: 'Select',
    radio: 'Radio', checkbox: 'Checkbox', file: 'File', hidden: 'Hidden',
    h1: 'Heading 1', h2: 'Heading 2', h3: 'Heading 3',
    h4: 'Heading 4', h5: 'Heading 5', h6: 'Heading 6'
  };

  var uidCounter = 0;
  function newUid(prefix) {
    return prefix + (++uidCounter) + '_' + Date.now();
  }

  function normalizeField(f) {
    return Object.assign({
      uid: newUid('f'),
      max_length: null, min_length: null, min_value: null, max_value: null, css_class: ''
    }, f);
  }

  var pages = (window.PAGES_JSON && window.PAGES_JSON.length ? window.PAGES_JSON : [{ title: 'Page 1', fields: [] }])
    .map(function (p) {
      return {
        uid: newUid('p'),
        title: p.title || 'Page 1',
        fields: (p.fields || []).map(normalizeField)
      };
    });

  var activePageUid = pages[0].uid;
  var selectedUid = null;

  var canvas = document.getElementById('canvas');
  var palette = document.getElementById('palette');
  var pageTabs = document.getElementById('pageTabs');
  var pageTitleInput = document.getElementById('pageTitle');
  var configForm = document.getElementById('fieldConfig');
  var noSelection = document.getElementById('noSelection');

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function fieldName(f) {
    return f.name || f.label.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
  }

  function activePage() {
    return pages.find(function (p) { return p.uid === activePageUid; }) || pages[0];
  }

  function findField(uid) {
    for (var i = 0; i < pages.length; i++) {
      var f = pages[i].fields.find(function (x) { return x.uid === uid; });
      if (f) return f;
    }
    return null;
  }

  // ---------- Rendering ----------

  function renderField(f) {
    var div = document.createElement('div');
    div.className = 'fb-field card mb-2' + (f.uid === selectedUid ? ' selected' : '');
    div.dataset.uid = f.uid;

    var preview = '';
    var cls = f.css_class ? ' ' + f.css_class : '';
    var lenAttrs = '';
    if (LENGTH_TYPES.indexOf(f.field_type) >= 0) {
      if (f.max_length) lenAttrs += ' maxlength="' + f.max_length + '"';
      if (f.min_length) lenAttrs += ' minlength="' + f.min_length + '"';
    }
    if (RANGE_TYPES.indexOf(f.field_type) >= 0) {
      if (f.min_value !== null && f.min_value !== '') lenAttrs += ' min="' + f.min_value + '"';
      if (f.max_value !== null && f.max_value !== '') lenAttrs += ' max="' + f.max_value + '"';
    }
    if (HEADING_TYPES.indexOf(f.field_type) >= 0) {
      preview = '<' + f.field_type + ' class="' + (f.css_class || '').trim() + '">' + escapeHtml(f.label || 'Heading') + '</' + f.field_type + '>';
    } else if (f.field_type === 'textarea') {
      preview = '<textarea class="form-control' + cls + '" rows="2" placeholder="' + escapeHtml(f.placeholder) + '"' + lenAttrs + ' disabled></textarea>';
    } else if (f.field_type === 'select') {
      preview = '<select class="form-select' + cls + '"' + lenAttrs + ' disabled><option>' + escapeHtml(f.placeholder || 'Select...') + '</option></select>';
    } else if (f.field_type === 'radio' || f.field_type === 'checkbox') {
      var opts = (f.choices || '').split('\n').filter(function (l) { return l.trim(); }).slice(0, 3);
      preview = opts.map(function (o) {
        return '<div class="form-check"><input class="form-check-input" type="' + f.field_type + '" disabled><label class="form-check-label">' + escapeHtml(o.trim()) + '</label></div>';
      }).join('');
    } else if (f.field_type === 'file') {
      preview = '<input type="file" class="form-control' + cls + '" disabled>';
    } else if (f.field_type === 'hidden') {
      preview = '<code class="small">hidden input</code>';
    } else {
      var itype = ['email', 'password', 'number', 'url', 'date'].indexOf(f.field_type) >= 0 ? f.field_type : 'text';
      preview = '<input type="' + itype + '" class="form-control' + cls + '" placeholder="' + escapeHtml(f.placeholder) + '" value="' + escapeHtml(f.default_value) + '"' + lenAttrs + ' disabled>';
    }

    var constraints = [];
    if (f.min_length) constraints.push('min ' + f.min_length);
    if (f.max_length) constraints.push('max ' + f.max_length);
    if (f.min_value !== null && f.min_value !== '') constraints.push('min ' + f.min_value);
    if (f.max_value !== null && f.max_value !== '') constraints.push('max ' + f.max_value);
    if (f.css_class) constraints.push('class: ' + f.css_class);
    var constraintHtml = constraints.length
      ? '<div class="text-muted small">' + escapeHtml(constraints.join(' · ')) + '</div>'
      : '';

    div.innerHTML =
      '<div class="card-body py-2">' +
        '<div class="d-flex align-items-center mb-1">' +
          '<span class="drag-handle me-2">&#x2630;</span>' +
          '<span class="badge bg-primary me-2">' + escapeHtml(TYPE_LABELS[f.field_type] || f.field_type) + '</span>' +
          '<strong class="flex-grow-1">' + escapeHtml(f.label || '(no label)') + '</strong>' +
          (f.required ? '<span class="badge bg-danger me-1">required</span>' : '') +
          '<button type="button" class="btn btn-sm btn-outline-danger btn-remove" title="Remove">&times;</button>' +
        '</div>' +
        '<div class="text-muted small mb-1"><code>' + escapeHtml(fieldName(f)) + '</code></div>' +
        constraintHtml +
        preview +
      '</div>';
    return div;
  }

  function renderCanvas() {
    canvas.innerHTML = '';
    var page = activePage();
    page.fields.forEach(function (f) { canvas.appendChild(renderField(f)); });
    if (!page.fields.length) {
      canvas.innerHTML = '<div class="text-center text-muted py-5 border border-dashed rounded">Drop fields here</div>';
    }
  }

  function renderTabs() {
    pageTabs.innerHTML = '';
    pages.forEach(function (p, idx) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn btn-sm ' + (p.uid === activePageUid ? 'btn-primary' : 'btn-outline-secondary');
      btn.textContent = (p.title || 'Page ' + (idx + 1)) + ' (' + p.fields.length + ')';
      btn.addEventListener('click', function () {
        activePageUid = p.uid;
        selectedUid = null;
        renderTabs();
        renderCanvas();
        selectField(null);
      });
      pageTabs.appendChild(btn);
    });
    var page = activePage();
    pageTitleInput.value = page.title;
    document.getElementById('delPageBtn').disabled = pages.length <= 1;
  }

  function selectField(uid) {
    selectedUid = uid;
    renderCanvas();
    var f = findField(uid);
    if (f) {
      noSelection.classList.add('d-none');
      configForm.classList.remove('d-none');
      document.getElementById('cfgLabel').value = f.label || '';
      document.getElementById('cfgName').value = f.name || '';
      document.getElementById('cfgPlaceholder').value = f.placeholder || '';
      document.getElementById('cfgHelpText').value = f.help_text || '';
      document.getElementById('cfgDefault').value = f.default_value || '';
      document.getElementById('cfgRequired').checked = !!f.required;
      document.getElementById('cfgMinLength').value = f.min_length || '';
      document.getElementById('cfgMaxLength').value = f.max_length || '';
      document.getElementById('cfgMinValue').value = f.min_value === null ? '' : f.min_value;
      document.getElementById('cfgMaxValue').value = f.max_value === null ? '' : f.max_value;
      document.getElementById('cfgCssClass').value = f.css_class || '';
      document.getElementById('cfgChoices').value = f.choices || '';
      var isChoice = CHOICE_TYPES.indexOf(f.field_type) >= 0;
      var isLength = LENGTH_TYPES.indexOf(f.field_type) >= 0;
      var isRange = RANGE_TYPES.indexOf(f.field_type) >= 0;
      document.getElementById('choicesGroup').style.display = isChoice ? '' : 'none';
      document.getElementById('lengthGroup').style.display = isLength ? '' : 'none';
      document.getElementById('lengthGroup2').style.display = isLength ? '' : 'none';
      document.getElementById('rangeGroup').style.display = isRange ? '' : 'none';
      document.getElementById('rangeGroup2').style.display = isRange ? '' : 'none';
    } else {
      noSelection.classList.remove('d-none');
      configForm.classList.add('d-none');
    }
  }

  // ---------- Drag & drop ----------

  if (typeof Sortable === 'undefined') {
    console.error('SortableJS failed to load — drag & drop disabled');
  } else {
  document.querySelectorAll('#palette .list-group').forEach(function (list) {
    Sortable.create(list, {
      group: { name: 'fb', pull: 'clone', put: false },
      sort: false,
      draggable: '.palette-item',
      animation: 150
    });
  });

  Sortable.create(canvas, {
    group: 'fb',
    draggable: '.fb-field',
    animation: 150,
    ghostClass: 'ghost',
    onAdd: function (evt) {
      var type = evt.item.dataset.type;
      var label = (evt.item.textContent || '').trim();
      var f = {
        uid: newUid('f'),
        id: null,
        field_type: type,
        label: label,
        name: '',
        placeholder: '',
        help_text: '',
        default_value: '',
        required: false,
        choices: '',
        max_length: null,
        min_length: null,
        min_value: null,
        max_value: null,
        css_class: ''
      };
      activePage().fields.splice(evt.newIndex, 0, f);
      evt.item.remove();
      renderTabs();
      selectField(f.uid);
    },
    onEnd: function () {
      var order = Array.from(canvas.querySelectorAll('.fb-field')).map(function (el) {
        return el.dataset.uid;
      });
      var page = activePage();
      page.fields.sort(function (a, b) {
        return order.indexOf(a.uid) - order.indexOf(b.uid);
      });
    }
  });
  }

  // ---------- Events ----------

  canvas.addEventListener('click', function (e) {
    var removeBtn = e.target.closest('.btn-remove');
    var fieldEl = e.target.closest('.fb-field');
    if (removeBtn && fieldEl) {
      e.stopPropagation();
      var uid = fieldEl.dataset.uid;
      var page = activePage();
      page.fields = page.fields.filter(function (f) { return f.uid !== uid; });
      if (selectedUid === uid) selectedUid = null;
      renderTabs();
      renderCanvas();
      selectField(selectedUid);
      return;
    }
    if (fieldEl) selectField(fieldEl.dataset.uid);
  });

  document.getElementById('applyConfig').addEventListener('click', function () {
    var f = findField(selectedUid);
    if (!f) return;
    f.label = document.getElementById('cfgLabel').value.trim();
    f.name = document.getElementById('cfgName').value.trim();
    f.placeholder = document.getElementById('cfgPlaceholder').value;
    f.help_text = document.getElementById('cfgHelpText').value;
    f.default_value = document.getElementById('cfgDefault').value;
    f.required = document.getElementById('cfgRequired').checked;
    f.choices = document.getElementById('cfgChoices').value;
    f.min_length = document.getElementById('cfgMinLength').value || null;
    f.max_length = document.getElementById('cfgMaxLength').value || null;
    f.min_value = document.getElementById('cfgMinValue').value === '' ? null : parseFloat(document.getElementById('cfgMinValue').value);
    f.max_value = document.getElementById('cfgMaxValue').value === '' ? null : parseFloat(document.getElementById('cfgMaxValue').value);
    f.css_class = document.getElementById('cfgCssClass').value.trim();
    renderCanvas();
    selectField(f.uid);
  });

  document.getElementById('deleteField').addEventListener('click', function () {
    if (!selectedUid) return;
    var page = activePage();
    page.fields = page.fields.filter(function (f) { return f.uid !== selectedUid; });
    selectedUid = null;
    renderTabs();
    renderCanvas();
    selectField(null);
  });

  document.getElementById('clearBtn').addEventListener('click', function () {
    if (!confirm('Remove all fields from all pages?')) return;
    pages.forEach(function (p) { p.fields = []; });
    selectedUid = null;
    renderTabs();
    renderCanvas();
    selectField(null);
  });

  // ---------- Pages ----------

  pageTitleInput.addEventListener('input', function () {
    activePage().title = pageTitleInput.value;
    renderTabs();
  });

  document.getElementById('addPageBtn').addEventListener('click', function () {
    var p = { uid: newUid('p'), title: 'Page ' + (pages.length + 1), fields: [] };
    pages.push(p);
    activePageUid = p.uid;
    selectedUid = null;
    renderTabs();
    renderCanvas();
    selectField(null);
  });

  document.getElementById('delPageBtn').addEventListener('click', function () {
    if (pages.length <= 1) return;
    if (!confirm('Delete this page and all its fields?')) return;
    var idx = pages.findIndex(function (p) { return p.uid === activePageUid; });
    pages.splice(idx, 1);
    activePageUid = pages[Math.max(0, idx - 1)].uid;
    selectedUid = null;
    renderTabs();
    renderCanvas();
    selectField(null);
  });

  // ---------- Save ----------

  document.getElementById('saveBtn').addEventListener('click', function () {
    var btn = this;
    btn.disabled = true;
    btn.textContent = 'Saving...';
    fetch(window.SAVE_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': window.CSRF_TOKEN
      },
      body: JSON.stringify({
        pages: pages.map(function (p) {
          return {
            title: p.title,
            fields: p.fields.map(function (f) {
              return {
                field_type: f.field_type,
                label: f.label,
                name: f.name,
                placeholder: f.placeholder,
                help_text: f.help_text,
                default_value: f.default_value,
                required: f.required,
                choices: f.choices,
                max_length: f.max_length ? parseInt(f.max_length, 10) : null,
                min_length: f.min_length ? parseInt(f.min_length, 10) : null,
                min_value: f.min_value,
                max_value: f.max_value,
                css_class: f.css_class
              };
            })
          };
        })
      })
    }).then(function (res) {
      if (!res.ok) throw new Error('Save failed');
      return res.json();
    }).then(function () {
      btn.textContent = 'Saved!';
      setTimeout(function () { btn.textContent = 'Save'; btn.disabled = false; }, 1200);
    }).catch(function (err) {
      alert(err.message);
      btn.textContent = 'Save';
      btn.disabled = false;
    });
  });

  renderTabs();
  renderCanvas();
})();
