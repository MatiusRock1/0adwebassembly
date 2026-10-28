// Pointer Lock confines input across monitor boundaries. SDL retains its
// ordinary absolute cursor and the original game handles all camera/GUI input.
export function installFullscreenPointer({ canvas, surface, getApplication, report }) {
  const cursor = document.createElement('img');
  cursor.className = 'original-pointer';
  cursor.alt = '';
  cursor.draggable = false;
  cursor.hidden = true;
  surface.append(cursor);
  let frame = 0;
  let hotspot = [0, 0];
  let visible = false;
  // SDL's published position trails the mouse by the engine's frames in
  // flight. Draw the locked cursor from the browser's own movement, summed as
  // SDL sums it, and adopt SDL's position again once the mouse rests.
  const RESYNC_MILLISECONDS = 250;
  let position = [0, 0];
  let residual = [0, 0];
  let lastMove = -Infinity;
  function updateCursor() {
    // SDL builds this data URL directly from the licensed original cursor.
    // Reuse those bytes; no replacement artwork or guessed pointer shape.
    const css = canvas.style.cursor;
    const match = /^url\(["']?(data:image\/[^"')]+)["']?\)\s*(\d+)?\s*(\d+)?/.exec(css);
    visible = !!match;
    if (match) {
      if (cursor.getAttribute('src') !== match[1]) cursor.src = match[1];
      hotspot = [Number(match[2] || 0), Number(match[3] || 0)];
    }
    cursor.hidden = !visible || document.pointerLockElement !== canvas;
  }
  new MutationObserver(updateCursor).observe(canvas, { attributes: true, attributeFilter: ['style'] });
  function paint() {
    const app = getApplication();
    if (document.pointerLockElement !== canvas || !app) { frame = 0; return; }
    if (performance.now() - lastMove > RESYNC_MILLISECONDS) {
      const packed = app.ccall('Phase4MousePosition', 'number', [], []) >>> 0;
      position = [packed & 65535, packed >>> 16];
      residual = [0, 0];
    }
    const rect = canvas.getBoundingClientRect();
    cursor.style.transform = `translate(${rect.left + position[0] * rect.width / canvas.width - hotspot[0]}px,${rect.top + position[1] * rect.height / canvas.height - hotspot[1]}px)`;
    frame = requestAnimationFrame(paint);
  }
  // Same arithmetic as Emscripten's SDL under Pointer Lock: movement scaled
  // from CSS to canvas pixels, sub-pixel remainders kept, clamped to the window.
  canvas.addEventListener('mousemove', event => {
    if (document.pointerLockElement !== canvas) return;
    const rect = canvas.getBoundingClientRect();
    const size = [canvas.width, canvas.height];
    const movement = [event.movementX * canvas.width / rect.width, event.movementY * canvas.height / rect.height];
    for (const axis of [0, 1]) {
      residual[axis] += movement[axis];
      const step = Math.trunc(residual[axis]);
      residual[axis] -= step;
      position[axis] = Math.min(Math.max(position[axis] + step, 0), size[axis] - 1);
    }
    lastMove = performance.now();
  });
  function capture() {
    try {
      const pending = canvas.requestPointerLock();
      pending?.catch(error => report(`No se pudo capturar el ratón: ${error.message}. Haz clic en el juego para reintentar.`));
    } catch (error) { report(`No se pudo capturar el ratón: ${error.message}`); }
  }
  document.addEventListener('pointerlockchange', () => {
    // Browser confinement does not emit mouseenter when it starts over the
    // fullscreen button. Tell SDL which surface owns mouse focus; otherwise
    // its original edge-scroll and cursor can remain disabled after mouseleave.
    const rect = canvas.getBoundingClientRect();
    canvas.dispatchEvent(new MouseEvent(document.pointerLockElement === canvas ? 'mouseenter' : 'mouseleave', {
      clientX: rect.left + rect.width / 2, clientY: rect.top + rect.height / 2
    }));
    updateCursor();
    cancelAnimationFrame(frame);
    frame = 0;
    lastMove = -Infinity;
    if (document.pointerLockElement === canvas) frame = requestAnimationFrame(paint);
  });
  canvas.addEventListener('click', () => {
    if (document.fullscreenElement === surface && document.pointerLockElement !== canvas) capture();
  });
  document.addEventListener('keydown', event => {
    if ((event.code === 'Escape' || event.key === 'Escape') && document.pointerLockElement === canvas) document.exitPointerLock();
  }, true);
  document.addEventListener('fullscreenchange', () => {
    if (document.fullscreenElement !== surface && document.pointerLockElement === canvas) document.exitPointerLock();
  });
  window.addEventListener('blur', () => {
    if (document.pointerLockElement === canvas) document.exitPointerLock();
  });
  updateCursor();
  return {
    enter() {
      // Pointer Lock must be requested before fullscreen consumes activation.
      capture();
      return surface.requestFullscreen({ navigationUI: 'hide' });
    },
    release() {
      if (document.pointerLockElement === canvas) document.exitPointerLock();
      cancelAnimationFrame(frame);
      cursor.hidden = true;
    }
  };
}
