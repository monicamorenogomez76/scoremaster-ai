import React, { useEffect, useImperativeHandle, useLayoutEffect, useRef, useState } from 'react';
import { loadMusicalAnalysis, pageLanes } from '../musicalAnalysis.js';
import { createFullScoreRenderer } from './full-score-renderer.js';
import { filterMusicXmlPassage, measureBounds } from './musicxml-passage.js';
import { nextFrame, openSheetMusicDisplay, toggleFullscreen } from './notation.js';
import { preparePlayback } from './playback.js';
import { Icon, TransportBar } from './TransportBar.jsx';
import { useTransport } from './useTransport.js';
import { currentLanguage, t } from '../i18n.js';
import { saveEdits } from '../noteCorrections.js';

const readyMessage = () => t('Todas las voces · pulsa Reproducir para cargar los sonidos.');

// Whole score with all voices, page navigation, zoom and ensemble playback; with workId, the map of the work can be drawn
// above the measures (2026-11-20).
export function FullScoreViewer({ ref, session, workId, onSaved }) {
  const section = useRef(null), container = useRef(null), renderer = useRef(null);
  const [view, setView] = useState({ visible: false, status: '', busy: false, page: '', canPrevious: false, canNext: false, zoomLabel: 'Auto', loaded: false, editing: false, edits: 0 });
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState({ text: '', error: false });
  const saveRef = useRef(null);
  const transport = useTransport({
    prepare: onStatus => preparePlayback(session.getFile(), null, onStatus),
    onPosition: (measure, playing) => renderer.current?.follow(measure, playing),
    stoppedMessage: t('Detenido.'),
  });

  useLayoutEffect(() => {
    renderer.current = createFullScoreRenderer({ container: container.current, session, filter: filterMusicXmlPassage,
      bounds: measureBounds, createDisplay: openSheetMusicDisplay, onChange: setView, nextFrame, onSave: () => saveRef.current?.(),
      onDuration: edit => saveRef.current?.([edit]) });
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
    const key = workId + '|' + language;   // the parts are named in the language of the interface
    if (!analyses.current.has(key)) {
      const pending = loadMusicalAnalysis(workId);
      pending.catch(() => analyses.current.delete(key));
      analyses.current.set(key, pending);
    }
    setAnalysisStatus(t('Cargando el análisis…'));
    analyses.current.get(key).then(analysis => {
      if (!current) return;
      renderer.current.setOverlay(cells => pageLanes(analysis, cells), t('Mapa de la obra en estos compases'));
      setAnalysisStatus(t('Sobre la partitura, el mapa de la obra en estos compases: sección, tonalidad, frase, tema, cadencias y dinámica.'));
    }).catch(failure => { if (current) setAnalysisStatus(failure.message); });
    return () => { current = false; };
  }, [showAnalysis, workId, language]);

  const stop = () => { transport.reset(); renderer.current.hideMarker(); };

  // The changes made on the score are saved together; the work then opens again with them (2026-11-23).
  // A figure comes as extra: it is saved at once with the changes waiting.
  const save = async (extra = []) => {
    const edits = [...renderer.current.getEdits(), ...extra];
    if (!edits.length || saving || !workId) return;
    setSaving(true); setSaveMessage({ text: '', error: false });
    try {
      await saveEdits(workId, edits);
      renderer.current.saved();
      setSaveMessage({ text: edits.length === 1 ? t('1 cambio guardado. La obra se ha vuelto a analizar.')
        : t('{count} cambios guardados. La obra se ha vuelto a analizar.', { count: edits.length }), error: false });
      await onSaved?.();
    } catch (failure) { setSaveMessage({ text: failure.message, error: true }); }
    finally { setSaving(false); }
  };
  saveRef.current = save;
  // Unsaved changes are not lost by closing the page without a warning.
  useEffect(() => {
    if (!view.edits) return;
    const warn = event => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [view.edits]);
  const toggleEditing = () => { setSaveMessage({ text: '', error: false }); renderer.current.setEditing(!view.editing); };
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
      {workId && <button id="score-edit-toggle" className="secondary-action score-edit-toggle" type="button" aria-pressed={view.editing}
        disabled={!view.loaded} onClick={toggleEditing}>{view.editing ? t('Terminar de editar') : t('Editar notas')}</button>}
    </div>
    {view.editing && <div className="score-editing-bar">
      <p id="score-edit-help" className="score-edit-help">{t('Haz clic en una nota o muévete con ← →; Alt+↑ ↓ cambia de pentagrama. ↑ ↓ sube o baja un grado, con Mayús medio tono y con Cmd o Ctrl una octava. A–G da el nombre de la nota; + − = ponen sostenido, bemol o becuadro; Supr la deja en silencio. 3 a 7 cambian la figura (semicorchea, corchea, negra, blanca, redonda) y el punto pone o quita el puntillo: se guarda al momento. Cmd o Ctrl+S guarda.')}</p>
      <div className="score-edit-actions">
        <span className="score-edit-count">{view.edits === 1 ? t('1 cambio sin guardar') : t('{count} cambios sin guardar', { count: view.edits })}</span>
        <button className="primary-action" type="button" disabled={!view.edits || saving} onClick={() => save()}>{saving ? t('Guardando…') : t('Guardar cambios')}</button>
        <button className="secondary-action" type="button" disabled={!view.edits || saving} onClick={() => renderer.current.discardEdits()}>{t('Descartar')}</button>
      </div>
    </div>}
    {saveMessage.text && <p className={saveMessage.error ? 'score-compare-error' : 'loading-status'} role={saveMessage.error ? 'alert' : 'status'}>{saveMessage.text}</p>}
    {analysisStatus && <p id="score-analysis-status" className="loading-status" role="status" aria-live="polite">{analysisStatus}</p>}
    {/* It may scroll sideways (beside a PDF, or zoomed in): the keyboard has to reach it. */}
    <div id="full-score-rendering" ref={container} tabIndex={0} role="region" aria-label={t('Partitura completa')}
      aria-describedby={view.editing ? 'score-edit-help' : undefined} className={view.editing ? 'score-editing' : undefined} />
  </section>;
}
