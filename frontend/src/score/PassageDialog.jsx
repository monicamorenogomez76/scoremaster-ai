import React, { useEffect, useImperativeHandle, useRef, useState } from 'react';
import { displayInstrumentName } from '../labels.js';
import { filterMusicXmlPassage, parseMeasureRange } from './musicxml-passage.js';
import { nextFrame, openSheetMusicDisplay, toggleFullscreen } from './notation.js';
import { highlightMeasure } from './playback-guide.js';
import { preparePlayback } from './playback.js';
import { Icon, TransportBar } from './TransportBar.jsx';
import { useTransport } from './useTransport.js';

const ZOOM = { min: .75, max: 1.5, step: .1 };

// One instrument over a measure range: the whole passage is drawn and scrolls inside the dialog.
export function PassageDialog({ ref, session }) {
  const dialog = useRef(null), frame = useRef(null), container = useRef(null), passage = useRef(null);
  const [info, setInfo] = useState({ title: 'Partitura del pasaje', status: 'Selecciona un pasaje para abrir la partitura.', range: '', zoom: '100%', position: '' });
  const show = changes => setInfo(previous => ({ ...previous, ...changes }));
  const transport = useTransport({
    prepare: onStatus => preparePlayback(session.getFile(), passage.current, onStatus),
    onPosition: measure => {
      const state = passage.current;
      if (!state || measure === state.currentMeasure) return;
      state.currentMeasure = measure;
      show({ position: 'Compás ' + measure + ' de ' + state.firstMeasure + '–' + state.lastMeasure });
      highlightMeasure(state.renderer, measure, container.current);
    },
    stoppedMessage: '',
  });

  function stop() {
    transport.reset();
    const state = passage.current;
    state?.renderer?.cursor?.hide();
    if (state) state.currentMeasure = undefined;
    show({ position: '' });
  }

  async function render() {
    const state = passage.current;
    const { firstMeasure: first, lastMeasure: last } = state;
    show({ range: 'Pasaje completo · compases ' + first + '–' + last + ' · ' + (last - first + 1) + ' compases · desplázate para revisarlos',
      status: 'Cargando el pasaje completo…' });
    await nextFrame();
    const stale = () => state !== passage.current || !dialog.current.open;
    if (stale()) return;
    const target = container.current;
    target.replaceChildren();
    const xml = filterMusicXmlPassage(state.source, state.instrument, first + '-' + last);
    const renderer = openSheetMusicDisplay(target, { autoResize: true, backend: 'svg', drawTitle: false,
      drawPartNames: true, drawMeasureNumbers: true, cursorsOptions: [{ type: 3, color: '#6366f1', alpha: .25, follow: false }] });
    await renderer.load(xml);
    if (stale()) return;
    renderer.render();
    state.renderer = renderer;
    const svg = target.querySelector('svg');
    if (svg) {
      svg.style.width = (state.zoom * 100) + '%';
      svg.style.maxWidth = 'none';
      renderer.playbackScale = svg.getBoundingClientRect().width / Number.parseFloat(svg.getAttribute('width'));
    }
    target.scrollTop = 0; target.scrollLeft = 0;
    if (state.currentMeasure !== undefined) highlightMeasure(renderer, state.currentMeasure, target);
    show({ zoom: Math.round(state.zoom * 100) + '%',
      status: 'Notación original · tonalidad escrita del MusicXML · ' + displayInstrumentName(state.instrument) + ' · audio en sonido real (instrumentos transpositores)' });
  }
  const rerender = () => render().catch(error => show({ status: error.message || 'No se pudo representar este pasaje.' }));

  useImperativeHandle(ref, () => ({
    async open(instrument, measureRange) {
      stop();
      const [firstMeasure, lastMeasure] = parseMeasureRange(measureRange);
      const state = { instrument, firstMeasure, lastMeasure, zoom: 1 };
      passage.current = state;
      show({ title: displayInstrumentName(instrument) + ' · compases ' + measureRange });
      if (!dialog.current.open) dialog.current.showModal();
      try {
        state.source = await session.loadSource();
        if (state === passage.current) await render();
      } catch (error) {
        show({ status: error.message || 'No se pudo representar este pasaje.' });
      }
    },
    getPassage: () => passage.current,
    highlight: measure => highlightMeasure(passage.current?.renderer, measure, container.current),
    stop,
  }));

  // Closing by button, Escape or code always stops the passage audio.
  useEffect(() => {
    const node = dialog.current;
    const closed = async () => {
      stop();
      if (document.fullscreenElement === frame.current) await document.exitFullscreen();
    };
    node.addEventListener('close', closed);
    return () => node.removeEventListener('close', closed);
  });

  const zoomTo = value => {
    const state = passage.current;
    if (!state) return;
    state.zoom = Math.max(ZOOM.min, Math.min(ZOOM.max, value));
    rerender();
  };
  const fullscreen = async () => {
    try { await toggleFullscreen(frame.current); await render(); }
    catch { transport.reset('La pantalla completa no está disponible en este navegador.'); }
  };

  return <dialog id="notation-dialog" ref={dialog} className="score-dialog" aria-labelledby="notation-title">
    <div id="passage-view" ref={frame} className="passage-view">
      <div className="score-dialog-head">
        <div>
          <h2 id="notation-title">{info.title}</h2>
          <p id="notation-status" className="score-dialog-status">{info.status}</p>
        </div>
        <button id="notation-close" className="score-tool score-close" type="button" aria-label="Cerrar partitura" title="Cerrar partitura"
          onClick={() => dialog.current.close()}><Icon path="m6 4 6 6 6-6 2 2-6 6 6 6-2 2-6-6-6 6-2-2 6-6-6-6z" /></button>
      </div>
      <TransportBar prefix="passage" group label="Reproducción del pasaje" volumeLabel="Volumen del pasaje" seekLabel="Posición del pasaje"
        fullscreenId="passage-fullscreen" transport={transport} onStop={stop} onFullscreen={fullscreen} />
      <div className="passage-progress">
        <output id="passage-position" className="score-page-label" aria-live="polite">{info.position}</output>
        <span id="playback-status" className="loading-status" role="status" aria-live="polite" aria-busy={transport.loading}>{transport.status}</span>
      </div>
      <div id="notation-score" ref={container} className="score-rendering" />
      <div className="score-toolbar" aria-label="Controles de partitura">
        <span id="notation-page-label" className="score-page-label">{info.range}</span>
        <button id="notation-zoom-out" className="score-tool" type="button" aria-label="Reducir zoom" title="Reducir zoom"
          onClick={() => zoomTo((passage.current?.zoom ?? 1) - ZOOM.step)}>−</button>
        <button id="notation-fit" className="score-tool" type="button" aria-label="Ajustar al ancho" title="Ajustar al ancho"
          onClick={() => zoomTo(1)}><Icon path="M5 2h14v20H5zm2 2v16h10V4zM9 7h6v2H9zm0 4h6v2H9z" /></button>
        <output id="notation-zoom-label">{info.zoom}</output>
        <button id="notation-zoom-in" className="score-tool" type="button" aria-label="Ampliar zoom" title="Ampliar zoom"
          onClick={() => zoomTo((passage.current?.zoom ?? 1) + ZOOM.step)}>+</button>
      </div>
    </div>
  </dialog>;
}
