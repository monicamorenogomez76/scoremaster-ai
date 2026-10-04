import { useCallback, useEffect, useRef, useState } from 'react';
import { applyInstrumentAssignments, inspectInstruments } from './instrument-session.js';
import { apiFetch } from './api.js';
import { completeBandProfile } from './labels.js';

// options: { minutes, getProfile(), getConfirmations(), onReset(), onAnalysis(data, profile, navigate) }.
// Read through a ref so changing them never aborts a request in flight.
export function useScoreAnalysis(workspace, options) {
  const [state, setState] = useState({ busy: false, message: '', error: false });
  const [parts, setParts] = useState([]);
  const [assignments, setAssignments] = useState({});
  const file = useRef(null), xml = useRef(null), generation = useRef(0), controller = useRef(null);
  const latest = useRef(options); latest.current = options;
  const invalidate = useCallback(() => {
    controller.current?.abort();
    return ++generation.current;
  }, []);

  const clearSelection = useCallback(async () => {
    setParts([]); setAssignments({});
    latest.current.onReset();
    await workspace.reset();
  }, [workspace]);

  const reset = useCallback(async () => {
    invalidate(); file.current = null; xml.current = null;
    setState({ busy: false, message: '', error: false });
    await clearSelection();
  }, [clearSelection, invalidate]);

  const selectFile = async selected => {
    const version = invalidate(); file.current = selected; xml.current = null;
    setState({ busy: Boolean(selected), message: selected ? 'Cargando datos de instrumentos…' : '', error: false });
    try {
      await clearSelection();
      if (!selected || version !== generation.current) return;
      workspace.setFile(selected);
      const source = await workspace.loadSource();
      if (version !== generation.current) return;
      const inspected = inspectInstruments(source);
      xml.current = inspected.parts.length ? inspected.xml : null;
      setParts(inspected.parts);
      setAssignments(Object.fromEntries(inspected.parts.map(part => [part.id, part.initialChoice])));
      setState({ busy: false, message: '', error: false });
    } catch (error) {
      if (version === generation.current) setState({ busy: false, message: error.message, error: true });
    }
  };

  const analyze = useCallback(async (selected, profile, navigate = true, confirmations = latest.current.getConfirmations()) => {
    if (!selected) { setState({ busy: false, message: 'Selecciona un archivo MusicXML.', error: true }); return; }
    const version = invalidate();
    const request = new AbortController(); controller.current = request;
    setState({ busy: true, message: 'Analizando la partitura. Puede tardar unos segundos…', error: false });
    try {
      await workspace.prepareAnalysis();
      if (version !== generation.current) return;
      let data, completedProfile = profile;
      // First analysis: the musicians each instrument needs, then recompute BandFit with that template.
      for (let attempt = 0; attempt < 2; attempt++) {
        const body = new FormData(); body.append('file', selected);
        body.append('band_profile', JSON.stringify(completedProfile));
        body.append('total_minutes', latest.current.minutes || '60');
        body.append('instrument_overrides', JSON.stringify(confirmations || {}));
        const response = await apiFetch('/analyze', { method: 'POST', body, signal: request.signal });
        try { data = await response.json(); }
        catch { throw new Error('El servidor devolvió una respuesta no válida. Vuelve a intentarlo.'); }
        if (version !== generation.current) return;
        if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'No se pudo analizar la partitura.');
        const completed = completeBandProfile(data.band_fit?.requirements, completedProfile);
        completedProfile = completed.profile;
        if (!completed.missing) break;
      }
      latest.current.onAnalysis(data, completedProfile, navigate);
      workspace.showScore();
      setState({ busy: false, message: '', error: false });
    } catch (error) {
      if (version !== generation.current || error.name === 'AbortError') return;
      setState({ busy: false, message: error.message, error: true });
    } finally {
      if (version === generation.current) controller.current = null;
    }
  }, [invalidate, workspace]);

  useEffect(() => invalidate, [invalidate]);

  const submit = () => {
    if (!file.current) return analyze(null, {});
    const mapped = applyInstrumentAssignments(file.current, xml.current, assignments);
    workspace.setFile(mapped.file, mapped.source);
    return analyze(mapped.file, latest.current.getProfile());
  };
  // Band and rehearsal views recompute the current score without leaving their view.
  const recalculate = confirmations => analyze(workspace.getFile(), latest.current.getProfile(), false,
    confirmations ?? latest.current.getConfirmations());
  return { state, parts, assignments, setAssignments, selectFile, reset, submit, recalculate };
}
