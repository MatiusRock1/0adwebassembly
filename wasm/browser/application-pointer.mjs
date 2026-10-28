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
    const packed = app.ccall('Phase4MousePosition', 'number', [], []) >>> 0;
    const rect = canvas.getBoundingClientRect();
    cursor.style.transform = `translate(${rect.left + (packed & 65535) * rect.width / canvas.width - hotspot[0]}px,${rect.top + (packed >>> 16) * rect.height / canvas.height - hotspot[1]}px)`;
    frame = requestAnimationFrame(paint);
  }
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
