(() => {
  'use strict';
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const animations = new Set();
  const animate = (element, frames, options) => {
    if ((reducedMotion.matches || document.documentElement.classList.contains('motion-paused')) || !element.animate) return;
    const animation = element.animate(frames, options);
    animations.add(animation);
    animation.finished.catch(() => {}).finally(() => animations.delete(animation));
  };
  reducedMotion.addEventListener('change', () => {
    if ((reducedMotion.matches || document.documentElement.classList.contains('motion-paused'))) animations.forEach(animation => animation.cancel());
  });

  // Brief, staggered entrance; content is never hidden while awaiting JavaScript.
  document.querySelectorAll('.stat-card').forEach((card, index) => {
    animate(card, [{opacity: .4, transform: 'translateY(12px)'}, {opacity: 1, transform: 'translateY(0)'}],
      {duration: 420, delay: index * 65, easing: 'cubic-bezier(.2,.7,.2,1)'});
  });

  // A visual encoding of the existing score, without changing its value.
  document.querySelectorAll('.score-hot, .score-warm, .score-cold').forEach(badge => {
    const score = Number(badge.textContent.trim());
    if (!Number.isFinite(score)) return;
    const track = document.createElement('span');
    track.className = 'score-track';
    track.setAttribute('aria-hidden', 'true');
    const fill = document.createElement('i');
    fill.style.setProperty('--score', `${Math.min(100, Math.max(0, score))}%`);
    track.append(fill);
    badge.after(track);
  });

  document.addEventListener('pointerdown', event => {
    const button = event.target.closest('.btn');
    if (!button || button.disabled || (reducedMotion.matches || document.documentElement.classList.contains('motion-paused')) || event.button !== 0) return;
    const bounds = button.getBoundingClientRect();
    const wave = document.createElement('span');
    wave.className = 'click-wave';
    wave.setAttribute('aria-hidden', 'true');
    wave.style.setProperty('--wave-size', `${Math.max(bounds.width, bounds.height) * 2}px`);
    wave.style.setProperty('--wave-x', `${event.clientX - bounds.left}px`);
    wave.style.setProperty('--wave-y', `${event.clientY - bounds.top}px`);
    button.append(wave);
    setTimeout(() => wave.remove(), 500);
  });

  const heading = document.querySelector('.illustrated-heading');
  let pointerFrame = 0;
  heading?.addEventListener('pointermove', event => {
    if ((reducedMotion.matches || document.documentElement.classList.contains('motion-paused')) || pointerFrame) return;
    pointerFrame = requestAnimationFrame(() => {
      const bounds = heading.getBoundingClientRect();
      heading.style.setProperty('--pointer-x', `${event.clientX - bounds.left}px`);
      heading.style.setProperty('--pointer-y', `${event.clientY - bounds.top}px`);
      pointerFrame = 0;
    });
  });

  // Scroll position, not simulated loading or search progress.
  const progress = document.createElement('div');
  progress.className = 'reading-progress';
  progress.setAttribute('aria-hidden', 'true');
  document.body.append(progress);
  let scrollFrame = 0;
  const updateProgress = () => {
    const distance = document.documentElement.scrollHeight - window.innerHeight;
    const amount = distance > 0 ? Math.min(1, Math.max(0, window.scrollY / distance)) : 0;
    progress.style.transform = `scaleX(${amount})`;
    scrollFrame = 0;
  };
  const scheduleProgress = () => { if (!scrollFrame) scrollFrame = requestAnimationFrame(updateProgress); };
  window.addEventListener('scroll', scheduleProgress, {passive: true});
  window.addEventListener('resize', scheduleProgress);
  new ResizeObserver(scheduleProgress).observe(document.body);
  updateProgress();

  const region = document.createElement('div');
  region.className = 'toast-region';
  region.setAttribute('role', 'status');
  region.setAttribute('aria-live', 'polite');
  document.body.append(region);
  document.addEventListener('job-status-feedback', event => {
    const toast = document.createElement('div');
    toast.className = `feedback-toast${event.detail.ok ? '' : ' error'}`;
    toast.textContent = event.detail.ok ? 'Estado actualizado correctamente' : 'No se pudo guardar el estado. Intenta de nuevo.';
    region.replaceChildren(toast);
    setTimeout(() => toast.remove(), 4500);
  });
})();

(() => {
  'use strict';
  const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
  const root = document.documentElement;
  const storageKey = 'job-hunter-motion-paused';
  let manuallyPaused = false;
  try { manuallyPaused = localStorage.getItem(storageKey) === 'true'; } catch (_) { /* Storage may be disabled. */ }
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'motion-toggle';
  document.querySelector('.topbar')?.append(button);
  const sync = () => {
    const paused = manuallyPaused || preference.matches;
    root.classList.toggle('motion-paused', paused);
    button.setAttribute('aria-pressed', String(paused));
    button.textContent = paused ? 'Animaciones en pausa' : 'Pausar animaciones';
    button.title = preference.matches ? 'Movimiento reducido según la preferencia de tu sistema' : 'Activar o pausar los efectos visuales';
    button.disabled = preference.matches;
    if (paused) document.getAnimations().forEach(animation => {
      // CSS loops pause via the root class. Finish only finite entrance animations.
      if (animation.effect?.getTiming().iterations !== Infinity) {
        try { animation.finish(); } catch (_) { /* A detached effect needs no action. */ }
      }
    });
  };
  button.addEventListener('click', () => {
    manuallyPaused = !manuallyPaused;
    try { localStorage.setItem(storageKey, String(manuallyPaused)); } catch (_) {}
    sync();
  });
  preference.addEventListener('change', sync);
  sync();

  const hero = document.querySelector('.illustrated-heading');
  if (hero) {
    const orbit = document.createElement('span');
    orbit.className = 'ambient-orbit';
    orbit.setAttribute('aria-hidden', 'true');
    hero.append(orbit);
  }
  document.querySelectorAll('.nav-item .ui-icon > *, .stat-card .ui-icon > *').forEach(shape => {
    shape.setAttribute('pathLength', '100');
  });

  // Offscreen artwork and background tabs do not keep decorative loops running.
  const surfaces = [...document.querySelectorAll('.illustrated-heading, .sidebar-art')];
  const visible = new Set(surfaces);
  const updateSleep = () => surfaces.forEach(surface => {
    surface.classList.toggle('ambient-sleep', document.hidden || !visible.has(surface));
  });
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => entry.isIntersecting ? visible.add(entry.target) : visible.delete(entry.target));
      updateSleep();
    });
    surfaces.forEach(surface => observer.observe(surface));
  }
  document.addEventListener('visibilitychange', updateSleep);
  updateSleep();
})();
