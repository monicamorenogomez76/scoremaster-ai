import React, { useCallback, useState } from 'react';
import { AppShell } from './AppShell.jsx';
import { LoginScreen } from './LoginScreen.jsx';
import { initialBandDraft, readBandProfile } from './labels.js';
import { useScoreAnalysis } from './useScoreAnalysis.js';

const SESSION_KEY = 'scoremaster-demo-session';
// The demo session is a local convenience, not authentication; storage may be unavailable.
function readDemoSession() {
  try { return sessionStorage.getItem(SESSION_KEY) === 'active'; } catch { return false; }
}
function writeDemoSession(active) {
  try { if (active) sessionStorage.setItem(SESSION_KEY, 'active'); else sessionStorage.removeItem(SESSION_KEY); } catch { /* session stays in memory */ }
}

export function App({ workspace }) {
  const [signedIn, setSignedIn] = useState(readDemoSession);
  const [view, setView] = useState('overview');
  // revision changes with every successful analysis so explorers restart from the top.
  const [analysis, setAnalysis] = useState(null);
  const [bandDraft, setBandDraft] = useState({});
  const [minutes, setMinutes] = useState('60');

  const navigate = useCallback(name => {
    setView(name);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);
  const upload = useScoreAnalysis(workspace, {
    minutes,
    getProfile: () => readBandProfile(analysis?.data.parts, bandDraft),
    onReset: () => { setAnalysis(null); setBandDraft({}); navigate('analyze'); },
    onAnalysis: (data, profile, shouldNavigate) => {
      setAnalysis(previous => ({ data, revision: (previous?.revision || 0) + 1 }));
      setBandDraft(initialBandDraft(data.parts, profile));
      if (shouldNavigate) navigate('analyze');
    },
  });
  const recalculate = () => (workspace.getFile() ? upload.recalculate() : navigate('analyze'));

  const enterDemo = () => { writeDemoSession(true); setSignedIn(true); navigate('overview'); };
  const leaveDemo = () => { writeDemoSession(false); setSignedIn(false); };

  return <>
    <LoginScreen hidden={signedIn} onEnter={enterDemo} />
    <AppShell hidden={!signedIn} workspace={workspace} view={view} onNavigate={navigate} onSignOut={leaveDemo}
      upload={upload} analysis={analysis} bandDraft={bandDraft} onBandDraftChange={setBandDraft}
      minutes={minutes} onMinutesChange={setMinutes} onRecalculate={recalculate} />
  </>;
}
