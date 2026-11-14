import htmx from 'htmx.org';
import Alpine from 'alpinejs';
import persist from '@alpinejs/persist';
import focus from '@alpinejs/focus';
import Quill from 'quill';

// 1. Globale Verfügbarkeit für Django-Templates herstellen
window.htmx = htmx;
window.Quill = Quill;
window.Alpine = Alpine;

// 2. Alpine.js Plugins registrieren
Alpine.plugin(persist);
Alpine.plugin(focus);

// 3. Automatisches Django CSRF-Token Handling für alle htmx Requests
document.body.addEventListener('htmx:configRequest', (event) => {
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
  if (csrfToken) {
    event.detail.headers['X-CSRFToken'] = csrfToken;
  }
});

// 4. Hilfsfunktion zur Initialisierung des lokalen RTF-Editors (CMS-Seiten mit Bild-Upload)
window.initCmsEditor = function (editorSelector, hiddenInputSelector, uploadUrl) {
  const container = document.querySelector(editorSelector);
  const hiddenInput = document.querySelector(hiddenInputSelector);
  if (!container || !hiddenInput) return null;

  const quill = new Quill(container, {
    theme: 'snow',
    modules: {
      toolbar: {
        container: [
          [{ header: [1, 2, 3, false] }],
          ['bold', 'italic', 'underline', 'strike'],
          [{ list: 'ordered' }, { list: 'bullet' }],
          ['link', 'image', 'blockquote', 'code-block'],
          ['clean']
        ],
        handlers: {
          image: function () {
            const input = document.createElement('input');
            input.setAttribute('type', 'file');
            input.setAttribute('accept', 'image/*');
            input.click();

            input.onchange = async () => {
              const file = input.files[0];
              if (!file) return;

              const formData = new FormData();
              formData.append('image', file);

              const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
              const response = await fetch(uploadUrl, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken },
                body: formData
              });

              if (response.ok) {
                const data = await response.json();
                const range = quill.getSelection(true);
                quill.insertEmbed(range.index, 'image', data.url);
              }
            };
          }
        }
      }
    }
  });

  quill.on('text-change', () => {
    hiddenInput.value = quill.root.innerHTML;
  });

  if (hiddenInput.value) {
    quill.clipboard.dangerouslyPasteHTML(hiddenInput.value);
  }
  return quill;
};

// 5. Triage-Board: Vim-Style Keyboard Navigation (J/K, Enter, Esc)
window.triageBoard = function (approveUrlTemplate) {
  return {
    activeIndex: 0,
    showAlternatives: false,
    rows() {
      return Array.from(document.querySelectorAll('[data-triage-row]'));
    },
    focusRow(index) {
      const rows = this.rows();
      if (!rows.length) return;
      this.activeIndex = Math.max(0, Math.min(index, rows.length - 1));
      rows.forEach((row) => row.classList.remove('triage-row-focused'));
      const row = rows[this.activeIndex];
      if (row) {
        row.classList.add('triage-row-focused');
        row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }
    },
    next() { this.showAlternatives = false; this.focusRow(this.activeIndex + 1); },
    prev() { this.showAlternatives = false; this.focusRow(this.activeIndex - 1); },
    toggleAlternatives() {
      this.showAlternatives = !this.showAlternatives;
      const row = this.rows()[this.activeIndex];
      row?.querySelector('[data-alternatives]')?.classList.toggle('hidden', !this.showAlternatives);
    },
    approve() {
      const row = this.rows()[this.activeIndex];
      if (!row) return;
      const url = row.dataset.approveUrl;
      if (!url) return;
      htmx.ajax('POST', url, { target: row, swap: 'outerHTML' }).then(() => {
        this.showAlternatives = false;
        this.focusRow(Math.min(this.activeIndex, this.rows().length - 1));
      });
    },
    init() {
      this.$nextTick(() => this.focusRow(0));
      window.addEventListener('keydown', (event) => {
        if (['INPUT', 'TEXTAREA', 'SELECT'].includes(event.target.tagName)) return;
        if (event.key === 'j' || event.key === 'ArrowDown') { event.preventDefault(); this.next(); }
        if (event.key === 'k' || event.key === 'ArrowUp') { event.preventDefault(); this.prev(); }
        if (event.key === 'Enter') { event.preventDefault(); this.approve(); }
        if (event.key === 'Escape') { event.preventDefault(); this.toggleAlternatives(); }
      });
    }
  };
};

// 6. Collection-Board: Alpine.js Selection- & CSV-State
window.collectionBoard = function () {
  return {
    selectedIds: [],
    selectAll: false,
    dateFrom: '',
    dateTo: '',
    toggleAll() {
      const boxes = Array.from(document.querySelectorAll('input[data-row-select]'));
      this.selectAll = !this.selectAll;
      boxes.forEach((box) => { box.checked = this.selectAll; });
      this.syncSelected();
    },
    syncSelected() {
      this.selectedIds = Array.from(document.querySelectorAll('input[data-row-select]:checked'))
        .map((box) => box.value);
      this.selectAll = this.selectedIds.length > 0 &&
        this.selectedIds.length === document.querySelectorAll('input[data-row-select]').length;
    },
    exportUrl(baseUrl) {
      const url = new URL(baseUrl, window.location.origin);
      if (this.selectedIds.length) url.searchParams.set('ids', this.selectedIds.join(','));
      if (this.dateFrom) url.searchParams.set('date_from', this.dateFrom);
      if (this.dateTo) url.searchParams.set('date_to', this.dateTo);
      return url.toString();
    },
    exportCsv(baseUrl) {
      window.location.href = this.exportUrl(baseUrl);
    }
  };
};

// 7. Universeller CSV-Export für Tabellen (Filter + Selektion)
window.csvTable = function () {
  return {
    selectedIds: [],
    selectAll: false,
    dateFrom: '',
    dateTo: '',
    statusFilter: '',
    syncSelected() {
      this.selectedIds = Array.from(document.querySelectorAll('input[data-row-select]:checked'))
        .map((box) => box.value);
    },
    toggleAll() {
      const boxes = Array.from(document.querySelectorAll('input[data-row-select]'));
      this.selectAll = !this.selectAll;
      boxes.forEach((box) => { box.checked = this.selectAll; });
      this.syncSelected();
    },
    exportCsv(baseUrl) {
      const url = new URL(baseUrl, window.location.origin);
      if (this.selectedIds.length) url.searchParams.set('ids', this.selectedIds.join(','));
      if (this.dateFrom) url.searchParams.set('date_from', this.dateFrom);
      if (this.dateTo) url.searchParams.set('date_to', this.dateTo);
      if (this.statusFilter) url.searchParams.set('status', this.statusFilter);
      window.location.href = url.toString();
    }
  };
};

Alpine.start();
