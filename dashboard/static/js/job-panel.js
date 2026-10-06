(() => {
  'use strict';
  const jobs = JSON.parse(document.getElementById('page-jobs').textContent);
  const byId = new Map(jobs.map(job => [String(job.id), job]));
  const dialog = document.getElementById('job-panel');
  const field = name => document.getElementById(`panel-${name}`);
  const pendingFavorites = new Set(), pendingStatuses = new Set();
  let current = null, opener = null, refreshFavorites = false;
  const favoritesView = new URLSearchParams(location.search).get('favorites') === '1';
  const descriptionNodes = text => {
    const fragment = document.createDocumentFragment();
    let list = null;
    for (const raw of text.split('\n')) {
      const line = raw.trim().replace(/\\([\-+&#*])/g, '$1');
      if (!line) { list = null; continue; }
      const heading = line.match(/^(?:#{1,6}\s+(.+)|\*\*(.+)\*\*)$/);
      const item = line.match(/^[-*+]\s+(.+)/);
      let node;
      if (item) {
        if (!list) { list = document.createElement('ul'); fragment.append(list); }
        node = document.createElement('li'); node.textContent = item[1]; list.append(node);
      } else {
        list = null; node = document.createElement(heading ? 'h4' : 'p');
        node.textContent = heading ? heading[1] || heading[2] : line; fragment.append(node);
      }
    }
    return fragment;
  };
  const feedback = (message, error = false) => {
    const target = dialog.open ? field('feedback') : document.getElementById('favorite-feedback');
    target.textContent = message;
    target.classList.toggle('is-error', error);
    clearTimeout(target.feedbackTimer);
    target.feedbackTimer = setTimeout(() => { target.textContent = ''; }, 5000);
  };
  const syncControls = job => {
    document.querySelectorAll(`[data-favorite-job="${job.id}"]`).forEach(button => {
      button.setAttribute('aria-pressed', String(job.is_favorite));
      button.setAttribute('aria-label', `${job.is_favorite ? 'Quitar de' : 'Guardar en'} favoritos: ${job.title}`);
      button.firstElementChild.textContent = job.is_favorite ? '★' : '☆';
      button.disabled = pendingFavorites.has(job.id);
    });
    document.querySelectorAll(`.status-select[data-job-id="${job.id}"]`).forEach(select => {
      select.value = job.status;
      select.dataset.current = job.status;
      select.disabled = pendingStatuses.has(job.id);
    });
    if (current === job) {
      field('favorite').setAttribute('aria-pressed', String(job.is_favorite));
      field('favorite').textContent = job.is_favorite ? '★ Guardado en favoritos' : '☆ Guardar favorito';
      field('favorite').disabled = pendingFavorites.has(job.id);
    }
  };
  const render = job => {
    current = job;
    field('title').textContent = job.title || 'Vacante';
    field('company').textContent = job.company || 'Empresa sin especificar';
    field('location').textContent = [job.location, job.is_remote ? 'Remoto' : ''].filter(Boolean).join(' · ');
    field('date').textContent = `Publicado: ${job.posted || job.scraped || 'Sin fecha'}`;
    field('source').textContent = job.source || 'Oferta de empleo';
    field('score').textContent = `${job.score} / 100 de afinidad`;
    field('description').replaceChildren(descriptionNodes(job.description || 'Sin descripción disponible.'));
    field('stack').replaceChildren(...job.stack.map(tech => {
      const badge = document.createElement('span'); badge.className = 'badge badge-stack'; badge.textContent = tech; return badge;
    }));
    const link = field('link');
    link.hidden = true; link.removeAttribute('href');
    try { const url = new URL(job.job_url); if (['http:', 'https:'].includes(url.protocol)) { link.href = url.href; link.hidden = false; } } catch (_) {}
    field('status').dataset.jobId = job.id;
    const index = jobs.indexOf(job);
    field('position').textContent = `${index + 1} de ${jobs.length} en esta página`;
    field('prev').disabled = index === 0;
    field('next').disabled = index === jobs.length - 1;
    document.querySelectorAll('[data-panel-job]').forEach(row => row.setAttribute('aria-expanded', String(row.dataset.panelJob === String(job.id))));
    syncControls(job);
    dialog.querySelector('.panel-content').scrollTop = 0;
  };
  const open = (id, trigger) => {
    const job = byId.get(String(id)); if (!job) return;
    opener = trigger; render(job);
    dialog.showModal(); document.body.classList.add('panel-open');
  };
  dialog.querySelector('.panel-close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
  });
  dialog.addEventListener('close', () => {
    document.body.classList.remove('panel-open');
    document.querySelectorAll('[data-panel-job]').forEach(row => row.setAttribute('aria-expanded', 'false'));
    field('feedback').textContent = '';
    current = null;
    opener?.focus({preventScroll: true});
    if (refreshFavorites) location.reload();
  });
  field('prev').addEventListener('click', () => { const job = jobs[jobs.indexOf(current) - 1]; if (job) render(job); });
  field('next').addEventListener('click', () => { const job = jobs[jobs.indexOf(current) + 1]; if (job) render(job); });

  const saveFavorite = async job => {
    if (!job || pendingFavorites.has(job.id)) return;
    pendingFavorites.add(job.id); syncControls(job);
    try {
      const response = await fetch(`/job/${job.id}/favorite`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({favorite: !job.is_favorite})});
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error('save');
      job.is_favorite = result.favorite;
      if (favoritesView && !job.is_favorite) {
        if (dialog.open) refreshFavorites = true;
        else location.reload();
      }
      feedback(job.is_favorite ? 'Vacante guardada en favoritos' : 'Vacante quitada de favoritos');
    } catch (_) { feedback('No se pudo guardar el favorito. Intenta de nuevo.', true); }
    finally { pendingFavorites.delete(job.id); syncControls(job); }
  };
  field('favorite').addEventListener('click', () => saveFavorite(current));
  document.addEventListener('click', event => {
    const favorite = event.target.closest('[data-favorite-job]');
    if (favorite) { saveFavorite(byId.get(favorite.dataset.favoriteJob)); return; }
    const button = event.target.closest('[data-open-job]');
    if (button) { open(button.dataset.openJob, button); return; }
    const row = event.target.closest('[data-panel-job]');
    if (row && !event.target.closest('button, a, select, input')) open(row.dataset.panelJob, row);
  });
  document.addEventListener('keydown', event => {
    if (event.target.matches('[data-panel-job]') && ['Enter', ' '].includes(event.key)) {
      event.preventDefault(); open(event.target.dataset.panelJob, event.target);
    }
  });
  document.addEventListener('change', async event => {
    if (!event.target.matches('.status-select')) return;
    const job = byId.get(event.target.dataset.jobId);
    if (!job || pendingStatuses.has(job.id)) return;
    const status = event.target.value;
    pendingStatuses.add(job.id); syncControls(job);
    try {
      const response = await fetch(`/job/${job.id}/status`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({status})});
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error('save');
      job.status = status; feedback('Estado actualizado correctamente');
    } catch (_) { feedback('No se pudo guardar el estado. Intenta de nuevo.', true); }
    finally { pendingStatuses.delete(job.id); syncControls(job); }
  });
})();
