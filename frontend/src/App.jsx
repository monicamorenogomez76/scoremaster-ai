import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { currentUser, onUnauthorized, signOut } from './api.js';
import { AppShell } from './AppShell.jsx';
import { LoginScreen } from './LoginScreen.jsx';
import { initialBandDraft, readBandProfile } from './labels.js';
import { FullScoreViewer } from './score/FullScoreViewer.jsx';
import { filterMusicXmlPassage } from './score/musicxml-passage.js';
import { PassageDialog } from './score/PassageDialog.jsx';
import { useScoreAnalysis } from './useScoreAnalysis.js';

export function App({ session }) {
  // undefined while the session is checked, null when nobody is signed in.
  const [user, setUser] = useState(undefined);
  const [view, setView] = useState('overview');
  // revision changes with every successful analysis so explorers restart from the top.
  const [analysis, setAnalysis] = useState(null);
  const [bandDraft, setBandDraft] = useState({});
  // Instruments confirmed by the user: part name → catalog identity (step 09).
  const [confirmations, setConfirmations] = useState({});
  const [minutes, setMinutes] = useState('60');
  const fullScore = useRef(null), passage = useRef(null);

  // Score file, notation and audio shared by the upload workflow and both viewers.
  const workspace = useMemo(() => ({
    getFile: session.getFile,
    setFile: session.setFile,
    loadSource: session.loadSource,
    async reset() { session.clear(); fullScore.current.clear(); passage.current.stop(); },
    async prepareAnalysis() { fullScore.current.clear(); passage.current.stop(); },
    showScore() { fullScore.current.load(); },
    openPassage(selection, measureRange, label) { fullScore.current.stop(); return passage.current.open(selection, measureRange, label); },
  }), [session]);

  // Diagnostic handle used by the browser tests to load synthetic scores and passages.
  useEffect(() => {
    window.scoremasterWorkspace = {
      loadSource: workspace.loadSource,
      setFile: workspace.setFile,
      openPassage: workspace.openPassage,
      getPassage: () => passage.current.getPassage(),
      highlightPassageMeasure: measure => passage.current.highlight(measure),
      filterPassage: filterMusicXmlPassage,
      loadScore: () => fullScore.current.load(),
    };
    return () => { delete window.scoremasterWorkspace; };
  }, [workspace]);

  const navigate = useCallback(name => {
    setView(name);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);
  const upload = useScoreAnalysis(workspace, {
    minutes,
    getProfile: () => readBandProfile(analysis?.data.band_fit?.requirements, bandDraft),
    getConfirmations: () => confirmations,
    onReset: () => { setAnalysis(null); setBandDraft({}); setConfirmations({}); navigate('analyze'); },
    onAnalysis: (data, profile, shouldNavigate) => {
      setAnalysis(previous => ({ data, fileName: session.getFile()?.name || '', revision: (previous?.revision || 0) + 1 }));
      setBandDraft(initialBandDraft(data.band_fit?.requirements, profile));
      if (shouldNavigate) navigate('analyze');
    },
  });
  const recalculate = () => (session.getFile() ? upload.recalculate() : navigate('analyze'));
  const confirmInstruments = chosen => {
    const next = { ...confirmations, ...chosen };
    setConfirmations(next);
    return session.getFile() ? upload.recalculate(next) : navigate('analyze');
  };

  useEffect(() => {
    let current = true;
    currentUser().then(found => { if (current) setUser(found); }).catch(() => { if (current) setUser(null); });
    const stop = onUnauthorized(() => setUser(null));
    return () => { current = false; stop(); };
  }, []);
  const signedIn = Boolean(user);
  const enter = found => { setUser(found); navigate('overview'); };
  const leave = async () => { await signOut().catch(() => {}); setUser(null); upload.reset(); };

  return <>
    <LoginScreen hidden={signedIn || user === undefined} onSignedIn={enter} />
    <AppShell hidden={!signedIn} user={user} view={view} onNavigate={navigate} onSignOut={leave}
      upload={upload} analysis={analysis} bandDraft={bandDraft} onBandDraftChange={setBandDraft}
      minutes={minutes} onMinutesChange={setMinutes} onRecalculate={recalculate} onConfirmInstruments={confirmInstruments} onOpenPassage={workspace.openPassage}
      scoreViewer={<FullScoreViewer ref={fullScore} session={session} />} />
    <PassageDialog ref={passage} session={session} />
  </>;
}
