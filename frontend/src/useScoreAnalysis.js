import { useCallback, useEffect, useRef, useState } from 'react';
import { applyInstrumentAssignments, inspectInstruments } from './instrument-session.js';

export function useScoreAnalysis(workspace) {
  const [state, setState] = useState({ busy: false, message: '', error: false });
  const [parts, setParts] = useState([]);
  const [assignments, setAssignments] = useState({});
  const file = useRef(null), xml = useRef(null), generation = useRef(0), controller = useRef(null);
  const invalidate = useCallback(() => {
    controller.current?.abort();
    return ++generation.current;
  }, []);

  const reset = useCallback(async () => {
    invalidate(); file.current = null; xml.current = null;
    setParts([]); setAssignments({}); setState({ busy: false, message: '', error: false });
    await workspace.reset();
  }, [invalidate, workspace]);

  const selectFile = async selected => {
    const version = invalidate(); file.current = selected; xml.current = null;
    setParts([]); setAssignments({});
    setState({ busy: Boolean(selected), message: selected ? 'Cargando datos de instrumentos…' : '', error: false });
    try {
      await workspace.reset();
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

  const analyze = useCallback(async (selected, profile, navigate = true) => {
    if (!selected) { setState({ busy: false, message: 'Selecciona un archivo MusicXML.', error: true }); return; }
    const version = invalidate();
    const request = new AbortController(); controller.current = request;
    setState({ busy: true, message: 'Analizando la partitura. Puede tardar unos segundos…', error: false });
    try {
      await workspace.prepareAnalysis();
      if (version !== generation.current) return;
      let data, completedProfile = profile;
      // Preserve legacy defaults: one player per score part, then recompute BandFit.
      for (let attempt = 0; attempt < 2; attempt++) {
        const body = new FormData(); body.append('file', selected);
        body.append('band_profile', JSON.stringify(completedProfile));
        body.append('total_minutes', workspace.getMinutes());
        const response = await fetch('/analyze', { method: 'POST', body, signal: request.signal });
        try { data = await response.json(); }
        catch { throw new Error('El servidor devolvió una respuesta no válida. Vuelve a intentarlo.'); }
        if (version !== generation.current) return;
        if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'No se pudo analizar la partitura.');
        const names = data.parts || [];
        const missing = names.some(name => completedProfile[workspace.apiInstrumentName(name)] === undefined);
        completedProfile = Object.fromEntries(names.map(name => {
          const key = workspace.apiInstrumentName(name); return [key, completedProfile[key] ?? 1];
        }));
        if (!missing) break;
      }
      workspace.showAnalysis(data, completedProfile, navigate);
      setState({ busy: false, message: '', error: false });
    } catch (error) {
      if (version !== generation.current || error.name === 'AbortError') return;
      setState({ busy: false, message: error.message, error: true });
    } finally {
      if (version === generation.current) controller.current = null;
    }
  }, [invalidate, workspace]);

  useEffect(() => {
    workspace.setAnalysisHandler(analyze);
    return () => { invalidate(); workspace.setAnalysisHandler(() => {}); };
  }, [analyze, invalidate, workspace]);

  const submit = () => {
    if (!file.current) return analyze(null, {});
    const mapped = applyInstrumentAssignments(file.current, xml.current, assignments);
    workspace.setFile(mapped.file, mapped.source);
    return analyze(mapped.file, workspace.readProfile());
  };
  return { state, parts, assignments, setAssignments, selectFile, reset, submit };
}
