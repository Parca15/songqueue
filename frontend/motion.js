/**
 * SongQueue · motion.js — física Apple (§3–§6) sobre Motion One + fallback WAAPI.
 * Cargar Motion antes: <script src="https://cdn.jsdelivr.net/npm/motion@11/dist/motion.js"></script>
 * Todo respeta prefers-reduced-motion (§14): cross-fade corto, sin overshoot.
 */
(function () {
  'use strict';

  const reduceMotion = () =>
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const M = () => (window.Motion ? window.Motion : null);

  /** Defaults Apple: críticamente amortiguado; bounce solo con momentum (§4). */
  const SPRING_DEFAULT = { type: 'spring', bounce: 0, duration: 0.35 };
  const SPRING_MOMENTUM = { type: 'spring', bounce: 0.2, duration: 0.4 };

  /** Proyección de momentum de Apple (§6): d≈0.998 scroll normal. */
  function project(initialVelocity, decelerationRate = 0.998) {
    return ((initialVelocity / 1000) * decelerationRate) / (1 - decelerationRate);
  }

  /** Rubber-band en bordes (§9). */
  function rubberband(overshoot, dimension, constant = 0.55) {
    return ((overshoot * dimension * constant) / (dimension + constant * Math.abs(overshoot)));
  }

  function waapi(el, keyframes, opts) {
    if (!el || !el.animate) return null;
    try {
      return el.animate(keyframes, { fill: 'both', ...opts });
    } catch {
      return null;
    }
  }

  /** Entrada: materializa (blur+scale+y juntos, §12), reversible simétrica (§7). */
  function enter(el, { y = 14, momentum = false, delay = 0 } = {}) {
    if (!el) return;
    if (reduceMotion()) {
      waapi(el, [{ opacity: 0 }, { opacity: 1 }], { duration: 150, delay, easing: 'ease-out' });
      return;
    }
    const m = M();
    const spring = momentum ? SPRING_MOMENTUM : SPRING_DEFAULT;
    if (m && m.animate) {
      m.animate(
        el,
        { opacity: [0, 1], y: [y, 0], scale: [0.98, 1], filter: ['blur(6px)', 'blur(0px)'] },
        { ...spring, delay }
      );
    } else {
      waapi(
        el,
        [
          { opacity: 0, transform: `translateY(${y}px) scale(0.98)`, filter: 'blur(6px)' },
          { opacity: 1, transform: 'translateY(0) scale(1)', filter: 'blur(0px)' },
        ],
        { duration: 350, delay, easing: 'cubic-bezier(0.32,0.72,0.35,1)' }
      );
    }
  }

  /** Salida por el mismo eje de entrada (§7). */
  function exit(el, { y = 10 } = {}) {
    if (!el) return Promise.resolve();
    if (reduceMotion()) {
      waapi(el, [{ opacity: 1 }, { opacity: 0 }], { duration: 150, easing: 'ease-in' });
      return Promise.resolve();
    }
    const m = M();
    if (m && m.animate) {
      return m.animate(el, { opacity: [1, 0], y: [0, y], scale: [1, 0.98] }, SPRING_DEFAULT).finished.catch(() => {});
    }
    waapi(el, [{ opacity: 1 }, { opacity: 0 }], { duration: 180, easing: 'ease-in' });
    return Promise.resolve();
  }

  /** Stagger para listas (resultados, cola): hint en dirección del gesto (§8). */
  function staggerIn(items, baseDelay = 0) {
    if (!items || !items.length) return;
    const step = reduceMotion() ? 0 : 28;
    items.forEach((el, i) => enter(el, { y: 12, delay: baseDelay + i * step * 0.001 }));
  }

  /** Toast causal: aparece en el evento real, sale por el mismo eje (§13, §7). */
  function toast(el) {
    if (!el) return;
    enter(el, { y: -8 });
    clearTimeout(el._t);
    el._t = setTimeout(() => exit(el), 3600);
  }

  /** Feedback press 1:1 (§1): scale 0.97 en pointer-down, no en click. */
  function pressable(scope = document) {
    scope.querySelectorAll('.btn, .search-box button, .actions button, .song-card .add-btn').forEach((b) => {
      if (b._pressBound) return;
      b._pressBound = true;
      b.addEventListener('pointerdown', () => {
        if (reduceMotion()) return;
        b.animate(
          [{ transform: 'scale(1)' }, { transform: 'scale(0.97)' }],
          { duration: 100, easing: 'ease-out', fill: 'forwards' }
        );
      });
      ['pointerup', 'pointercancel', 'pointerleave'].forEach((ev) =>
        b.addEventListener(ev, () => {
          if (reduceMotion()) return;
          b.animate([{ transform: 'scale(0.97)' }, { transform: 'scale(1)' }], {
            duration: 180,
            easing: 'cubic-bezier(0.32,0.72,0.35,1)',
          });
        })
      );
    });
  }

  /**
   * Sheet arrastrable con handoff de velocidad (§2,§5,§6) + rubber-band (§9).
   * Uso: makeDraggable(sheetEl, { onDismiss }) — drag vertical, suelta con
   * velocidad → proyecta destino y hace spring con la velocidad real.
   */
  function makeDraggable(sheet, { dismissThreshold = 120, onDismiss = null } = {}) {
    if (!sheet) return () => {};
    let startY = 0, grabOffset = 0, currentY = 0, dragging = false;
    const history = [];

    const setY = (y) => {
      currentY = y;
      sheet.style.transform = `translateY(${y}px)`;
    };
    const liveY = () => currentY; // valor live on-screen (§3): nunca el target lógico

    sheet.addEventListener('pointerdown', (e) => {
      // Solo arrastre desde el handle o el borde superior del sheet
      if (e.target.closest('input,button,textarea,a')) return;
      dragging = true;
      startY = e.clientY;
      grabOffset = e.clientY - sheet.getBoundingClientRect().top; // respeta agarre (§2)
      history.length = 0;
      history.push({ y: e.clientY, t: performance.now() });
      try { sheet.setPointerCapture(e.pointerId); } catch {}
      sheet.style.transition = 'none';
    });

    sheet.addEventListener('pointermove', (e) => {
      if (!dragging) return;
      const raw = e.clientY - startY;
      history.push({ y: e.clientY, t: performance.now() });
      if (history.length > 6) history.shift();
      // Rubber-band hacia arriba (overshoot negativo), libre hacia abajo
      const y = raw < 0 ? rubberband(raw, sheet.offsetHeight || 400) : raw;
      setY(liveY() * 0 + y);
    });

    const end = (e) => {
      if (!dragging) return;
      dragging = false;
      const now = performance.now();
      const recent = history.filter((h) => now - h.t < 120);
      let velocity = 0;
      if (recent.length >= 2) {
        const a = recent[0], b = recent[recent.length - 1];
        velocity = ((b.y - a.y) / Math.max(1, b.t - a.t)) * 1000; // px/s
      }
      const projected = liveY() + project(velocity); // §6: destino desde proyección
      const shouldDismiss = projected > dismissThreshold || (liveY() > dismissThreshold && velocity > -200);
      const m = M();
      if (shouldDismiss) {
        const target = window.innerHeight;
        if (!reduceMotion() && m && m.animate) {
          m.animate(sheet, { y: [liveY(), target] }, { ...SPRING_MOMENTUM, velocity }).finished
            .catch(() => {}).finally(() => onDismiss && onDismiss());
        } else {
          onDismiss && onDismiss();
        }
      } else {
        // Vuelve con la velocidad del dedo (handoff §5), sin brick-wall (§3)
        if (!reduceMotion() && m && m.animate) {
          m.animate(sheet, { y: [liveY(), 0] }, { ...SPRING_DEFAULT, velocity }).finished
            .catch(() => {}).finally(() => setY(0));
        } else {
          setY(0);
        }
      }
    };
    sheet.addEventListener('pointerup', end);
    sheet.addEventListener('pointercancel', end);
    return () => { sheet.style.transform = ''; };
  }

  /** Abre overlay+sheet con animación interrumpible (desde valor live, §3). */
  function openSheet(overlay, sheet) {
    if (!overlay) return;
    overlay.classList.remove('hidden');
    requestAnimationFrame(() => {
      enter(sheet || overlay.querySelector('.dialog-content'), { y: 24 });
      pressable(overlay);
    });
  }

  function closeSheet(overlay, sheet) {
    if (!overlay) return;
    const el = sheet || overlay.querySelector('.dialog-content');
    exit(el).finally(() => overlay.classList.add('hidden'));
  }

  window.SQMotion = {
    enter, exit, staggerIn, toast, pressable,
    makeDraggable, openSheet, closeSheet,
    project, rubberband, reduceMotion,
    SPRING_DEFAULT, SPRING_MOMENTUM,
  };
})();
