import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { currentUser, onUnauthorized, signOut } from './api.js';
import { AppShell } from './AppShell.jsx';
import { saveBand } from './library.js';
import { LoginScreen } from './LoginScreen.jsx';
import { initialBandDraft, readBandProfile } from './labels.js';
import { passageRange } from './rehearsals.js';
import { FullScoreViewer } from './score/FullScoreViewer.jsx';
import { filterMusicXmlPassage } from './score/musicxml-passage.js';
import { PassageDialog } from './score/PassageDialog.jsx';
import { useScoreAnalysis } from './useScoreAnalysis.js';

export function App({ session }) {
  // undefined while the session is checked, null when nobody is signed in.
  const [user, setUser] = useState(undefined);
  const [view, setView] = useState('summary');
  // Repertoire: list of works, form to add one, or the detail of the open work and its tab.
  const [repertoireMode, setRepertoireMode] = useState('list');
  const [workTab, setWorkTab] = useState('score');
  // Saved rehearsal open in the editor: {} for a new one, null when closed.
  const [rehearsalEditing, setRehearsalEditing] = useState(null);
  // Rehearsal open in the director's review (from Ensayos or from the summary assistant).
  const [rehearsalReviewing, setRehearsalReviewing] = useState(null);
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
    onReset: byUser => {
      setAnalysis(null); setBandDraft({}); setConfirmations({});
      if (byUser) { setRepertoireMode('add'); navigate('repertoire'); }
    },
    onAnalysis: (data, profile, shouldNavigate) => {
      setAnalysis(previous => ({ data, fileName: session.getFile()?.name || '', revision: (previous?.revision || 0) + 1 }));
      setBandDraft(initialBandDraft(data.band_fit?.requirements, profile));
      // An uploaded or reopened work opens on its score, in the repertoire.
      if (shouldNavigate) { setRepertoireMode('detail'); setWorkTab('score'); navigate('repertoire'); }
    },
  });
  const addWork = () => { setRepertoireMode('add'); navigate('repertoire'); };
  // A block of a rehearsal or a priority opens the score at its passage with its instruments (the whole
  // band when it names none), loading its work first if another one is open; without measures, its work.
  const openBlock = async ({ work_id: workId, parts, measures, label }) => {
    if (!workId) return;
    const range = passageRange(measures);
    if (!range) return upload.openWork(workId);
    const data = analysis?.data?.work_id === workId ? analysis.data : await upload.openWork(workId, { navigate: false });
    if (!data) return;
    await workspace.openPassage(parts?.length ? parts : data.parts, range, label);
  };
  const recalculate = () => (session.getFile() ? upload.recalculate() : addWork());
  // The edited template is saved for the user's next works; this analysis already sends it.
  const updateBand = () => {
    saveBand(readBandProfile(analysis?.data.band_fit?.requirements, bandDraft)).catch(() => {});
    recalculate();
  };
  // Another band was activated: the open work is recalculated with its template.
  const bandActivated = band => {
    const requirements = analysis?.data.band_fit?.requirements;
    const draft = initialBandDraft(requirements, band.profile);
    setBandDraft(draft);
    if (session.getFile()) upload.recalculate(undefined, readBandProfile(requirements, draft));
  };
  const confirmInstruments = chosen => {
    const next = { ...confirmations, ...chosen };
    setConfirmations(next);
    return session.getFile() ? upload.recalculate(next) : addWork();
  };

  useEffect(() => {
    let current = true;
    currentUser().then(found => { if (current) setUser(found); }).catch(() => { if (current) setUser(null); });
    const stop = onUnauthorized(() => setUser(null));
    return () => { current = false; stop(); };
  }, []);
  const signedIn = Boolean(user);
  const enter = found => { setUser(found); setRepertoireMode('list'); setRehearsalEditing(null); setRehearsalReviewing(null); navigate('summary'); };
  const leave = async () => { await signOut().catch(() => {}); setUser(null); upload.reset(); };

  return <>
    <LoginScreen hidden={signedIn || user === undefined} onSignedIn={enter} />
    <AppShell hidden={!signedIn} user={user} view={view} onNavigate={navigate} onSignOut={leave}
      upload={upload} analysis={analysis} repertoireMode={repertoireMode} onRepertoireModeChange={setRepertoireMode}
      workTab={workTab} onWorkTabChange={setWorkTab} bandDraft={bandDraft}
      rehearsalEditing={rehearsalEditing} onEditRehearsal={rehearsal => { setRehearsalEditing(rehearsal); navigate('rehearsal'); }}
      onCloseRehearsal={() => setRehearsalEditing(null)}
      rehearsalReviewing={rehearsalReviewing} onReviewRehearsal={rehearsal => { setRehearsalEditing(null); setRehearsalReviewing(rehearsal); navigate('rehearsal'); }}
      onCloseReview={() => setRehearsalReviewing(null)} onUserChanged={setUser} onBandDraftChange={setBandDraft}
      minutes={minutes} onMinutesChange={setMinutes} onRecalculate={recalculate} onUpdateBand={updateBand} onConfirmInstruments={confirmInstruments} onBandActivated={bandActivated} onOpenWork={upload.openWork} onOpenPassage={workspace.openPassage} onOpenBlock={openBlock}
      scoreViewer={<FullScoreViewer ref={fullScore} session={session} />} />
    <PassageDialog ref={passage} session={session} />
  </>;
}
