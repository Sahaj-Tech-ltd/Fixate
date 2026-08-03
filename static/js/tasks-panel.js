/**
 * Fixate Task Manager Panel
 * ─────────────────────────────────────────────────────────────────
 * Vanilla JS, zero frameworks. Integrates with existing Fixate
 * dashboard patterns (glass-panel, fx-slide-panel, openPanel/closePanel).
 *
 * Features:
 *   • Add / edit / delete tasks
 *   • HTML5 drag-and-drop reordering
 *   • 3 priority levels (low / med / high) with colour coding
 *   • Optional due dates with relative time display
 *   • Per-task estimated pomodoros
 *   • Mark complete with strikethrough animation
 *   • Filter by status (all / active / done)
 *   • localStorage persistence under 'fixate_tasks' key
 *
 * CSS, HTML, and JS are clearly sectioned below.
 * ─────────────────────────────────────────────────────────────────
 */

(function () {
  'use strict';

  /* ================================================================
   *  1.  CSS STYLES
   * ================================================================ */
  const CSS = `
    /* ── Task Panel Overrides ─────────────────────────────────── */
    #panel-tasks .fx-panel-body {
      display: flex;
      flex-direction: column;
      gap: 0;
      padding: 0;
      max-height: 70vh;
    }

    /* ── Add-task form ────────────────────────────────────────── */
    .task-add-form {
      display: flex;
      flex-direction: column;
      gap: 8px;
      padding: 14px 16px 12px;
      border-bottom: 1px solid rgba(255,255,255,.08);
    }
    .task-add-row {
      display: flex;
      gap: 8px;
      align-items: center;
    }
    .task-add-form input[type="text"],
    .task-add-form input[type="date"],
    .task-add-form input[type="number"],
    .task-add-form select {
      background: rgba(255,255,255,.07);
      border: 1px solid rgba(255,255,255,.12);
      border-radius: 6px;
      color: var(--text-primary, #eee);
      padding: 6px 10px;
      font-size: 13px;
      outline: none;
      transition: border-color .2s;
    }
    .task-add-form input:focus,
    .task-add-form select:focus {
      border-color: var(--accent, #7c3aed);
    }
    .task-add-form input[type="text"] {
      flex: 1;
      min-width: 0;
    }
    .task-add-form input[type="date"] {
      width: 135px;
    }
    .task-add-form input[type="number"] {
      width: 58px;
      text-align: center;
    }
    .task-add-form select {
      width: 76px;
      cursor: pointer;
    }

    /* ── Filter bar ───────────────────────────────────────────── */
    .task-filters {
      display: flex;
      gap: 0;
      padding: 0 16px;
      border-bottom: 1px solid rgba(255,255,255,.08);
    }
    .task-filter-btn {
      flex: 1;
      padding: 8px 0;
      background: none;
      border: none;
      border-bottom: 2px solid transparent;
      color: var(--text-secondary, #aaa);
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: .6px;
      cursor: pointer;
      transition: color .2s, border-color .2s;
    }
    .task-filter-btn:hover {
      color: var(--text-primary, #eee);
    }
    .task-filter-btn.active {
      color: var(--accent, #7c3aed);
      border-bottom-color: var(--accent, #7c3aed);
    }

    /* ── Task list ────────────────────────────────────────────── */
    .task-list {
      flex: 1;
      overflow-y: auto;
      padding: 8px 0;
      min-height: 60px;
    }
    .task-list::-webkit-scrollbar {
      width: 4px;
    }
    .task-list::-webkit-scrollbar-thumb {
      background: rgba(255,255,255,.15);
      border-radius: 2px;
    }
    .task-empty {
      text-align: center;
      padding: 32px 16px;
      color: var(--text-secondary, #888);
      font-size: 13px;
      font-style: italic;
    }

    /* ── Single task item ─────────────────────────────────────── */
    .task-item {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      padding: 10px 16px;
      margin: 2px 8px;
      border-radius: 8px;
      cursor: grab;
      transition: background .15s, opacity .3s, transform .3s;
      position: relative;
      user-select: none;
    }
    .task-item:hover {
      background: rgba(255,255,255,.05);
    }
    .task-item.dragging {
      opacity: .4;
      transform: scale(.97);
    }
    .task-item.drag-over {
      border-top: 2px solid var(--accent, #7c3aed);
    }
    .task-item.completed .task-title {
      text-decoration: line-through;
      opacity: .45;
    }
    .task-item.completing .task-title {
      animation: strike .35s ease forwards;
    }
    @keyframes strike {
      0%   { text-decoration: none;   opacity: 1; }
      100% { text-decoration: line-through; opacity: .45; }
    }

    /* ── Checkbox ─────────────────────────────────────────────── */
    .task-check {
      flex-shrink: 0;
      width: 18px;
      height: 18px;
      border-radius: 50%;
      border: 2px solid rgba(255,255,255,.25);
      background: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: border-color .2s, background .2s;
      margin-top: 2px;
    }
    .task-check:hover {
      border-color: var(--accent, #7c3aed);
    }
    .task-check.checked {
      border-color: var(--accent, #7c3aed);
      background: var(--accent, #7c3aed);
    }
    .task-check.checked::after {
      content: '✓';
      color: #fff;
      font-size: 11px;
      font-weight: 700;
    }

    /* ── Priority indicator ───────────────────────────────────── */
    .task-priority {
      flex-shrink: 0;
      width: 4px;
      border-radius: 2px;
      align-self: stretch;
      min-height: 18px;
    }
    .task-priority.low  { background: #22c55e; }
    .task-priority.med  { background: #f59e0b; }
    .task-priority.high { background: #ef4444; }

    /* ── Task content ─────────────────────────────────────────── */
    .task-content {
      flex: 1;
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 3px;
    }
    .task-title {
      font-size: 13px;
      font-weight: 500;
      color: var(--text-primary, #eee);
      line-height: 1.3;
      word-break: break-word;
    }
    .task-meta {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }
    .task-due {
      font-size: 11px;
      color: var(--text-secondary, #999);
      display: flex;
      align-items: center;
      gap: 3px;
    }
    .task-due.overdue {
      color: #ef4444;
      font-weight: 600;
    }
    .task-due.due-soon {
      color: #f59e0b;
      font-weight: 600;
    }
    .task-pomodoros {
      font-size: 11px;
      color: var(--text-secondary, #999);
      display: flex;
      align-items: center;
      gap: 3px;
    }

    /* ── Task actions ─────────────────────────────────────────── */
    .task-actions {
      display: flex;
      gap: 4px;
      flex-shrink: 0;
      opacity: 0;
      transition: opacity .15s;
    }
    .task-item:hover .task-actions {
      opacity: 1;
    }
    .task-action-btn {
      background: none;
      border: none;
      cursor: pointer;
      font-size: 14px;
      padding: 2px 5px;
      border-radius: 4px;
      color: var(--text-secondary, #999);
      transition: color .15s, background .15s;
    }
    .task-action-btn:hover {
      color: var(--text-primary, #fff);
      background: rgba(255,255,255,.1);
    }
    .task-action-btn.delete:hover {
      color: #ef4444;
    }

    /* ── Edit mode ────────────────────────────────────────────── */
    .task-item.editing .task-content {
      display: none;
    }
    .task-item.editing .task-actions {
      opacity: 1;
    }
    .task-edit-form {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .task-edit-form input,
    .task-edit-form select {
      background: rgba(255,255,255,.07);
      border: 1px solid rgba(255,255,255,.12);
      border-radius: 6px;
      color: var(--text-primary, #eee);
      padding: 5px 8px;
      font-size: 12px;
      outline: none;
      transition: border-color .2s;
    }
    .task-edit-form input:focus,
    .task-edit-form select:focus {
      border-color: var(--accent, #7c3aed);
    }
    .task-edit-row {
      display: flex;
      gap: 6px;
      align-items: center;
    }
    .task-edit-form input[type="text"] {
      flex: 1;
    }
    .task-edit-form input[type="date"] {
      width: 125px;
    }
    .task-edit-form input[type="number"] {
      width: 52px;
      text-align: center;
    }
    .task-edit-form select {
      width: 72px;
    }

    /* ── Summary bar ──────────────────────────────────────────── */
    .task-summary {
      padding: 8px 16px;
      border-top: 1px solid rgba(255,255,255,.08);
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 11px;
      color: var(--text-secondary, #888);
    }
    .task-clear-done {
      background: none;
      border: none;
      color: var(--text-secondary, #888);
      cursor: pointer;
      font-size: 11px;
      text-decoration: underline;
      transition: color .15s;
    }
    .task-clear-done:hover {
      color: #ef4444;
    }
  `;

  /* ================================================================
   *  2.  HTML MARKUP
   * ================================================================ */
  const HTML = `
    <!-- ── Task Manager Panel ──────────────────────────────── -->
    <div id="panel-tasks" class="fx-slide-panel glass-panel fx-hidden">
      <div class="fx-panel-header">
        <h3>📋 Tasks</h3>
        <button class="task-panel-close" aria-label="Close tasks">✕</button>
      </div>
      <div class="fx-panel-body">
        <!-- Add-task form -->
        <form class="task-add-form" autocomplete="off">
          <div class="task-add-row">
            <input type="text" class="task-add-title" placeholder="Add a new task…" required />
            <button type="submit" class="fx-btn" title="Add task">＋</button>
          </div>
          <div class="task-add-row">
            <select class="task-add-priority" title="Priority">
              <option value="low">🟢 Low</option>
              <option value="med" selected>🟡 Med</option>
              <option value="high">🔴 High</option>
            </select>
            <input type="date" class="task-add-due" title="Due date (optional)" />
            <input type="number" class="task-add-pomodoros" placeholder="🍅" min="0" max="99" title="Estimated pomodoros" />
          </div>
        </form>

        <!-- Filters -->
        <div class="task-filters">
          <button class="task-filter-btn active" data-filter="all">All</button>
          <button class="task-filter-btn" data-filter="active">Active</button>
          <button class="task-filter-btn" data-filter="done">Done</button>
        </div>

        <!-- Task list -->
        <div class="task-list"></div>

        <!-- Summary -->
        <div class="task-summary">
          <span class="task-summary-text"></span>
          <button class="task-clear-done">Clear completed</button>
        </div>
      </div>
    </div>
  `;

  /* ================================================================
   *  3.  VANILLA JS — FixateTasks
   * ================================================================ */
  const STORAGE_KEY = 'fixate_tasks';
  const $ = (sel, ctx) => (ctx || document).querySelector(sel);
  const $$ = (sel, ctx) => [...(ctx || document).querySelectorAll(sel)];

  /* ── Utility: relative time ────────────────────────────────── */
  function relativeTime(dateStr) {
    if (!dateStr) return null;
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    const target = new Date(dateStr + 'T00:00:00');
    const diffMs = target - now;
    const diffDays = Math.round(diffMs / 86400000);
    if (diffDays < -1) return `${Math.abs(diffDays)} days overdue`;
    if (diffDays === -1) return 'Yesterday';
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Tomorrow';
    if (diffDays <= 7) return `in ${diffDays} days`;
    return target.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  }

  function dueClass(dateStr) {
    if (!dateStr) return '';
    const now = new Date(); now.setHours(0,0,0,0);
    const target = new Date(dateStr + 'T00:00:00');
    const diffDays = Math.round((target - now) / 86400000);
    if (diffDays < 0) return 'overdue';
    if (diffDays <= 2) return 'due-soon';
    return '';
  }

  /* ── Data layer ────────────────────────────────────────────── */
  let tasks = [];
  let currentFilter = 'all';
  let draggedId = null;

  function load() {
    try {
      tasks = JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
    } catch { tasks = []; }
  }

  function save() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks));
  }

  function genId() {
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
  }

  /* ── DOM references (set on init) ──────────────────────────── */
  let panel, listEl, formEl, summaryEl, filterBtns;

  /* ── Rendering ─────────────────────────────────────────────── */
  function filtered() {
    if (currentFilter === 'active') return tasks.filter(t => !t.done);
    if (currentFilter === 'done')   return tasks.filter(t => t.done);
    return tasks;
  }

  function renderList() {
    const items = filtered();
    if (!items.length) {
      listEl.innerHTML = `<div class="task-empty">${
        tasks.length ? 'No tasks match this filter.' : 'No tasks yet — add one above!'
      }</div>`;
    } else {
      listEl.innerHTML = items.map(renderItem).join('');
    }
    renderSummary();
    bindListEvents();
  }

  function renderItem(t) {
    const due = relativeTime(t.due);
    const dueCls = dueClass(t.due);
    return `
      <div class="task-item ${t.done ? 'completed' : ''}"
           data-id="${t.id}" draggable="true">
        <div class="task-priority ${t.priority}"></div>
        <button class="task-check ${t.done ? 'checked' : ''}"
                data-action="toggle" aria-label="Toggle complete"></button>
        <div class="task-content">
          <span class="task-title">${esc(t.title)}</span>
          <div class="task-meta">
            ${due ? `<span class="task-due ${dueCls}">📅 ${due}</span>` : ''}
            ${t.pomodoros ? `<span class="task-pomodoros">🍅 ${t.pomodoros}</span>` : ''}
          </div>
        </div>
        <div class="task-actions">
          <button class="task-action-btn" data-action="edit" title="Edit">✏️</button>
          <button class="task-action-btn delete" data-action="delete" title="Delete">🗑</button>
        </div>
      </div>`;
  }

  function renderSummary() {
    const total = tasks.length;
    const done = tasks.filter(t => t.done).length;
    const active = total - done;
    summaryEl.querySelector('.task-summary-text').textContent =
      `${active} active · ${done} done · ${total} total`;
  }

  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  /* ── Bind events on list items ─────────────────────────────── */
  function bindListEvents() {
    $$('.task-item', listEl).forEach(el => {
      el.addEventListener('dragstart', onDragStart);
      el.addEventListener('dragend', onDragEnd);
      el.addEventListener('dragover', onDragOver);
      el.addEventListener('dragenter', onDragEnter);
      el.addEventListener('dragleave', onDragLeave);
      el.addEventListener('drop', onDrop);
    });
    $$('.task-check, .task-action-btn', listEl).forEach(btn => {
      btn.addEventListener('click', onAction);
    });
  }

  /* ── Actions ───────────────────────────────────────────────── */
  function onAction(e) {
    const btn = e.currentTarget;
    const action = btn.dataset.action;
    const itemEl = btn.closest('.task-item');
    const id = itemEl.dataset.id;

    if (action === 'toggle')  return toggleTask(id);
    if (action === 'delete')  return deleteTask(id);
    if (action === 'edit')    return startEdit(id, itemEl);
    if (action === 'save')    return saveEdit(id, itemEl);
    if (action === 'cancel')  return cancelEdit(itemEl);
  }

  function addTask(title, priority, due, pomodoros) {
    tasks.unshift({
      id: genId(),
      title: title.trim(),
      priority,
      due: due || null,
      pomodoros: pomodoros ? parseInt(pomodoros, 10) : 0,
      done: false,
      createdAt: Date.now()
    });
    save();
    renderList();
  }

  function deleteTask(id) {
    tasks = tasks.filter(t => t.id !== id);
    save();
    renderList();
  }

  function toggleTask(id) {
    const t = tasks.find(t => t.id === id);
    if (!t) return;
    t.done = !t.done;
    // Animate strikethrough
    const el = $(`.task-item[data-id="${id}"]`, listEl);
    if (el && t.done) {
      el.classList.add('completing');
      setTimeout(() => { save(); renderList(); }, 380);
    } else {
      save();
      renderList();
    }
  }

  /* ── Inline edit ───────────────────────────────────────────── */
  function startEdit(id, itemEl) {
    const t = tasks.find(t => t.id === id);
    if (!t) return;
    itemEl.classList.add('editing');
    itemEl.draggable = false;

    const form = document.createElement('div');
    form.className = 'task-edit-form';
    form.innerHTML = `
      <input type="text" class="task-edit-title" value="${esc(t.title)}" />
      <div class="task-edit-row">
        <select class="task-edit-priority">
          <option value="low"  ${t.priority === 'low'  ? 'selected' : ''}>🟢 Low</option>
          <option value="med"  ${t.priority === 'med'  ? 'selected' : ''}>🟡 Med</option>
          <option value="high" ${t.priority === 'high' ? 'selected' : ''}>🔴 High</option>
        </select>
        <input type="date" class="task-edit-due" value="${t.due || ''}" />
        <input type="number" class="task-edit-pomodoros" value="${t.pomodoros || ''}" min="0" max="99" placeholder="🍅" />
      </div>`;

    const actionsEl = itemEl.querySelector('.task-actions');
    actionsEl.innerHTML = `
      <button class="task-action-btn" data-action="save" title="Save">✔️</button>
      <button class="task-action-btn delete" data-action="cancel" title="Cancel">✖</button>`;

    itemEl.insertBefore(form, actionsEl);

    // Bind new action buttons
    $$('.task-action-btn', actionsEl).forEach(btn => {
      btn.addEventListener('click', onAction);
    });

    // Focus title input
    const titleInput = form.querySelector('.task-edit-title');
    titleInput.focus();
    titleInput.select();

    // Enter to save
    titleInput.addEventListener('keydown', e => {
      if (e.key === 'Enter') saveEdit(id, itemEl);
      if (e.key === 'Escape') cancelEdit(itemEl);
    });
  }

  function saveEdit(id, itemEl) {
    const t = tasks.find(t => t.id === id);
    if (!t) return;
    const form = itemEl.querySelector('.task-edit-form');
    if (!form) return;
    const newTitle = form.querySelector('.task-edit-title').value.trim();
    if (!newTitle) return;
    t.title = newTitle;
    t.priority = form.querySelector('.task-edit-priority').value;
    t.due = form.querySelector('.task-edit-due').value || null;
    t.pomodoros = parseInt(form.querySelector('.task-edit-pomodoros').value, 10) || 0;
    save();
    renderList();
  }

  function cancelEdit(itemEl) {
    renderList();
  }

  /* ── Drag & Drop ───────────────────────────────────────────── */
  function onDragStart(e) {
    const item = e.currentTarget;
    draggedId = item.dataset.id;
    item.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', draggedId);
  }

  function onDragEnd(e) {
    e.currentTarget.classList.remove('dragging');
    $$('.task-item.drag-over', listEl).forEach(el => el.classList.remove('drag-over'));
    draggedId = null;
  }

  function onDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  }

  function onDragEnter(e) {
    e.preventDefault();
    const item = e.currentTarget;
    if (item.dataset.id !== draggedId) {
      item.classList.add('drag-over');
    }
  }

  function onDragLeave(e) {
    e.currentTarget.classList.remove('drag-over');
  }

  function onDrop(e) {
    e.preventDefault();
    const targetEl = e.currentTarget;
    targetEl.classList.remove('drag-over');
    const targetId = targetEl.dataset.id;
    if (!draggedId || draggedId === targetId) return;

    const fromIdx = tasks.findIndex(t => t.id === draggedId);
    const toIdx   = tasks.findIndex(t => t.id === targetId);
    if (fromIdx === -1 || toIdx === -1) return;

    const [moved] = tasks.splice(fromIdx, 1);
    tasks.splice(toIdx, 0, moved);
    save();
    renderList();
  }

  /* ── Panel open / close ────────────────────────────────────── */
  function open() {
    // Use existing Fixate.openPanel if available
    if (window.Fixate && typeof window.Fixate.openPanel === 'function') {
      window.Fixate.openPanel('tasks');
    } else {
      panel.classList.remove('fx-hidden');
    }
    renderList();
  }

  function close() {
    if (window.Fixate && typeof window.Fixate.closePanel === 'function') {
      window.Fixate.closePanel('tasks');
    } else {
      panel.classList.add('fx-hidden');
    }
  }

  /* ── Dock button injection ─────────────────────────────────── */
  function injectDockButton() {
    const footer = $('footer');
    if (!footer || $('.task-dock-btn', footer)) return;
    const btn = document.createElement('button');
    btn.className = 'fx-amb-btn task-dock-btn';
    btn.textContent = '📋';
    btn.title = 'Tasks';
    btn.addEventListener('click', () => {
      if (panel && !panel.classList.contains('fx-hidden')) {
        close();
      } else {
        open();
      }
    });
    footer.appendChild(btn);
  }

  /* ── Init ──────────────────────────────────────────────────── */
  function init() {
    // Inject CSS
    const style = document.createElement('style');
    style.id = 'tasks-panel-css';
    style.textContent = CSS;
    document.head.appendChild(style);

    // Inject HTML
    const container = document.createElement('div');
    container.innerHTML = HTML.trim();
    document.body.appendChild(container.firstElementChild);

    // Cache DOM refs
    panel     = $('#panel-tasks');
    listEl    = $('.task-list', panel);
    formEl    = $('.task-add-form', panel);
    summaryEl = $('.task-summary', panel);
    filterBtns = $$('.task-filter-btn', panel);

    // Load persisted tasks
    load();

    // Add form submit
    formEl.addEventListener('submit', e => {
      e.preventDefault();
      const title = $('.task-add-title', formEl).value.trim();
      if (!title) return;
      addTask(
        title,
        $('.task-add-priority', formEl).value,
        $('.task-add-due', formEl).value,
        $('.task-add-pomodoros', formEl).value
      );
      formEl.reset();
      $('.task-add-priority', formEl).value = 'med';
    });

    // Filter buttons
    filterBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        filterBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentFilter = btn.dataset.filter;
        renderList();
      });
    });

    // Clear completed
    $('.task-clear-done', panel).addEventListener('click', () => {
      tasks = tasks.filter(t => !t.done);
      save();
      renderList();
    });

    // Close button
    $('.task-panel-close', panel).addEventListener('click', close);

    // Inject dock button
    injectDockButton();

    // Initial render
    renderList();
  }

  /* ── Expose namespace ──────────────────────────────────────── */
  window.FixateTasks = {
    init,
    open,
    close,
    getTasks: () => tasks,
    addTask: (title, priority, due, pomodoros) => {
      addTask(title, priority || 'med', due, pomodoros);
    }
  };

  // Auto-init when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
