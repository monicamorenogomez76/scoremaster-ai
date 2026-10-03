import React, { useImperativeHandle, useLayoutEffect, useRef, useState } from 'react';
import { createFullScoreRenderer } from './full-score-renderer.js';
import { filterMusicXmlPassage, measureBounds } from './musicxml-passage.js';
import { nextFrame, openSheetMusicDisplay, toggleFullscreen } from './notation.js';
import { preparePlayback } from './playback.js';
import { Icon, TransportBar } from './TransportBar.jsx';
import { useTransport } from './useTransport.js';

const READY_MESSAGE = 'Todas las voces · pulsa Reproducir para cargar los sonidos.';

// Whole score with all voices, page navigation, zoom and ensemble playback.
export function FullScoreViewer({ ref, session }) {
  const section = useRef(null), container = useRef(null), renderer = useRef(null);
  const [view, setView] = useState({ visible: false, status: '', busy: false, page: '', canPrevious: false, canNext: false, zoomLabel: 'Auto', loaded: false });
  const transport = useTransport({
    prepare: onStatus => preparePlayback(session.getFile(), null, onStatus),
    onPosition: (measure, playing) => renderer.current?.follow(measure, playing),
    stoppedMessage: 'Detenido.',
  });

  useLayoutEffect(() => {
    renderer.current = createFullScoreRenderer({ container: container.current, session, filter: filterMusicXmlPassage,
      bounds: measureBounds, createDisplay: openSheetMusicDisplay, onChange: setView, nextFrame });
    const observer = new ResizeObserver(() => renderer.current.fit());
    observer.observe(container.current);
    return () => observer.disconnect();
  }, [session]);

  const stop = () => { transport.reset(); renderer.current.hideMarker(); };
  useImperativeHandle(ref, () => ({
    load() { transport.reset(READY_MESSAGE); return renderer.current.load(); },
    clear() { transport.reset(); renderer.current.clear(); },
    stop,
  }));

  const fullscreen = async () => {
    try { await toggleFullscreen(section.current); await renderer.current.renderPage(); }
    catch { renderer.current.setStatus('La pantalla completa no está disponible en este navegador.'); }
  };
  const tool = (id, label, onClick, content, disabled) =>
    <button id={id} className="score-tool" type="button" aria-label={label} title={label} onClick={onClick} disabled={disabled}>{content}</button>;

  return <section id="embedded-score" ref={section} hidden={!view.visible} className="embedded-score" aria-label="Partitura completa y reproductor">
    <h2>Partitura completa</h2>
    <TransportBar prefix="ensemble" label="Reproducción de todas las voces" volumeLabel="Volumen de reproducción"
      seekLabel="Posición de reproducción" fullscreenId="score-fullscreen" transport={transport}
      playDisabled={!view.loaded} stopDisabled={!view.loaded} onStop={stop} onFullscreen={fullscreen} />
    <p id="ensemble-status" className="loading-status" role="status" aria-live="polite" aria-busy={transport.loading}>{transport.status}</p>
    <p id="full-score-status" className="loading-status" role="status" aria-live="polite" aria-busy={view.busy}>{view.status}</p>
    <div className="score-toolbar" aria-label="Navegación de la partitura completa">
      {tool('score-prev', 'Página anterior', () => renderer.current.previous(), <Icon path="m15 4-8 8 8 8 2-2-6-6 6-6z" />, !view.canPrevious)}
      <span id="score-page" className="score-page-label">{view.page}</span>
      {tool('score-next', 'Página siguiente', () => renderer.current.next(), <Icon path="m9 4 8 8-8 8-2-2 6-6-6-6z" />, !view.canNext)}
      {tool('score-zoom-out', 'Reducir zoom', () => renderer.current.zoomOut(), '−')}
      {tool('score-fit', 'Ajustar al ancho', () => renderer.current.resetZoom(), <Icon path="M5 2h14v20H5zm2 2v16h10V4zM9 7h6v2H9zm0 4h6v2H9z" />)}
      <output id="score-zoom-label">{view.zoomLabel}</output>
      {tool('score-zoom-in', 'Ampliar zoom', () => renderer.current.zoomIn(), '+')}
    </div>
    <div id="full-score-rendering" ref={container} />
  </section>;
}
