import React, { useEffect, useImperativeHandle, useLayoutEffect, useRef, useState } from 'react';
import { loadMusicalAnalysis, pageLanes } from '../musicalAnalysis.js';
import { createFullScoreRenderer } from './full-score-renderer.js';
import { filterMusicXmlPassage, measureBounds } from './musicxml-passage.js';
import { nextFrame, openSheetMusicDisplay, toggleFullscreen } from './notation.js';
import { preparePlayback } from './playback.js';
import { Icon, TransportBar } from './TransportBar.jsx';
import { useTransport } from './useTransport.js';
import { currentLanguage, t } from '../i18n.js';

const readyMessage = () => t('Todas las voces · pulsa Reproducir para cargar los sonidos.');

// Whole score with all voices, page navigation, zoom and ensemble playback; with workId, the map of the work can be drawn
// above the measures (2026-11-20).
export function FullScoreViewer({ ref, session, workId }) {
  const section = useRef(null), container = useRef(null), renderer = useRef(null);
  const [view, setView] = useState({ visible: false, status: '', busy: false, page: '', canPrevious: false, canNext: false, zoomLabel: 'Auto', loaded: false });
  const transport = useTransport({
    prepare: onStatus => preparePlayback(session.getFile(), null, onStatus),
    onPosition: (measure, playing) => renderer.current?.follow(measure, playing),
    stoppedMessage: t('Detenido.'),
  });

  useLayoutEffect(() => {
    renderer.current = createFullScoreRenderer({ container: container.current, session, filter: filterMusicXmlPassage,
      bounds: measureBounds, createDisplay: openSheetMusicDisplay, onChange: setView, nextFrame });
    const observer = new ResizeObserver(() => renderer.current.fit());
    observer.observe(container.current);
    return () => observer.disconnect();
  }, [session]);

  // The analysis behind the map is asked for once per work, only when the director shows it.
  const [showAnalysis, setShowAnalysis] = useState(false);
  const [analysisStatus, setAnalysisStatus] = useState('');
  const analyses = useRef(new Map());
  const language = currentLanguage();
  useEffect(() => {
    if (!showAnalysis || !workId) { renderer.current.setOverlay(null); setAnalysisStatus(''); return; }
    let current = true;
    if (!analyses.current.has(workId)) {
      const pending = loadMusicalAnalysis(workId);
      pending.catch(() => analyses.current.delete(workId));
      analyses.current.set(workId, pending);
    }
    setAnalysisStatus(t('Cargando el análisis…'));
    analyses.current.get(workId).then(analysis => {
      if (!current) return;
      renderer.current.setOverlay(cells => pageLanes(analysis, cells), t('Mapa de la obra en estos compases'));
      setAnalysisStatus(t('Sobre la partitura, el mapa de la obra en estos compases: sección, tonalidad, frase, tema, cadencias y dinámica.'));
    }).catch(failure => { if (current) setAnalysisStatus(failure.message); });
    return () => { current = false; };
  }, [showAnalysis, workId, language]);

  const stop = () => { transport.reset(); renderer.current.hideMarker(); };
  useImperativeHandle(ref, () => ({
    load() { transport.reset(readyMessage()); return renderer.current.load(); },
    clear() { transport.reset(); renderer.current.clear(); },
    stop,
  }));

  const fullscreen = async () => {
    try { await toggleFullscreen(section.current); await renderer.current.renderPage(); }
    catch { renderer.current.setStatus(t('La pantalla completa no está disponible en este navegador.')); }
  };
  const tool = (id, label, onClick, content, disabled) =>
    <button id={id} className="score-tool" type="button" aria-label={label} title={label} onClick={onClick} disabled={disabled}>{content}</button>;

  return <section id="embedded-score" ref={section} hidden={!view.visible} className="embedded-score" aria-label={t('Partitura completa y reproductor')}>
    <h2>{t('Partitura completa')}</h2>
    <TransportBar prefix="ensemble" label={t('Reproducción de todas las voces')} volumeLabel={t('Volumen de reproducción')}
      seekLabel={t('Posición de reproducción')} fullscreenId="score-fullscreen" transport={transport}
      playDisabled={!view.loaded} stopDisabled={!view.loaded} onStop={stop} onFullscreen={fullscreen} />
    <p id="ensemble-status" className="loading-status" role="status" aria-live="polite" aria-busy={transport.loading}>{transport.status}</p>
    <p id="full-score-status" className="loading-status" role="status" aria-live="polite" aria-busy={view.busy}>{view.status}</p>
    <div className="score-toolbar" aria-label={t('Navegación de la partitura completa')}>
      {tool('score-prev', t('Página anterior'), () => renderer.current.previous(), <Icon path="m15 4-8 8 8 8 2-2-6-6 6-6z" />, !view.canPrevious)}
      <span id="score-page" className="score-page-label">{view.page}</span>
      {tool('score-next', t('Página siguiente'), () => renderer.current.next(), <Icon path="m9 4 8 8-8 8-2-2 6-6-6-6z" />, !view.canNext)}
      {tool('score-zoom-out', t('Reducir zoom'), () => renderer.current.zoomOut(), '−')}
      {tool('score-fit', t('Ajustar al ancho'), () => renderer.current.resetZoom(), <Icon path="M5 2h14v20H5zm2 2v16h10V4zM9 7h6v2H9zm0 4h6v2H9z" />)}
      <output id="score-zoom-label">{view.zoomLabel}</output>
      {tool('score-zoom-in', t('Ampliar zoom'), () => renderer.current.zoomIn(), '+')}
      {workId && <button id="score-analysis-toggle" className="secondary-action score-analysis-toggle" type="button" aria-pressed={showAnalysis}
        onClick={() => setShowAnalysis(shown => !shown)}>{showAnalysis ? t('Ocultar el mapa') : t('Ver el mapa de la obra')}</button>}
    </div>
    {analysisStatus && <p id="score-analysis-status" className="loading-status" role="status" aria-live="polite">{analysisStatus}</p>}
    {/* It may scroll sideways (beside a PDF, or zoomed in): the keyboard has to reach it. */}
    <div id="full-score-rendering" ref={container} tabIndex={0} role="region" aria-label={t('Partitura completa')} />
  </section>;
}
