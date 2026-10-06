// Shared, framework-free behavior used across every dashboard page:
// collapsible panels (job description rows, "personalizar esta corrida")
// and dismissible flash alerts. Page-specific logic stays in each
// template's own <script> block.

document.addEventListener('click', (e) => {
  const trigger = e.target.closest('[data-collapse-target], [data-bs-toggle="collapse"]');
  if (!trigger) return;

  // Row-style triggers (e.g. a whole <tr>) ignore clicks on their own
  // interactive children so links/buttons/selects inside still work.
  if (trigger.dataset.collapseTarget && e.target.closest('a, button, select, input')) return;

  const targetId = trigger.dataset.collapseTarget || (trigger.dataset.bsTarget || '').replace('#', '');
  const targetEl = targetId && document.getElementById(targetId);
  if (!targetEl) return;

  const isOpen = targetEl.classList.toggle('show');
  trigger.setAttribute('aria-expanded', String(isOpen));
});

document.addEventListener('click', (e) => {
  const closeBtn = e.target.closest('[data-bs-dismiss="alert"]');
  if (!closeBtn) return;
  closeBtn.closest('.alert')?.remove();
});

// Keep vacancy descriptions accessible from the keyboard.
document.addEventListener('keydown', (event) => {
  if (!event.target.matches('.job-row[data-collapse-target]')) return;
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault();
    event.target.click();
  }
});
