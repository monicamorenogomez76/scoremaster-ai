import React, { useState } from 'react';
import { ActivityStatus } from './ActivityStatus.jsx';
import { BandView } from './BandView.jsx';
import { ConcertsView } from './ConcertsView.jsx';
import { EvaluationView } from './EvaluationView.jsx';
import { RehearsalView } from './RehearsalView.jsx';
import { RepertoireView } from './RepertoireView.jsx';
import { SettingsView } from './SettingsView.jsx';
import { SummaryView } from './SummaryView.jsx';

const views = [
  ['summary', 'Resumen', 'M3 10 12 3l9 7v10h-6v-6H9v6H3z'],
  ['repertoire', 'Repertorio', 'M3 6h6l2 2h10v11H3zM3 6v13'],
  ['band', 'Mi banda', 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M17 4a4 4 0 0 1 0 8M22 21v-2a4 4 0 0 0-3-3.8'],
  ['concerts', 'Conciertos', 'M9 18V5l12-2v13M9 18a3 3 0 1 1-6 0 3 3 0 0 1 6 0zM21 16a3 3 0 1 1-6 0 3 3 0 0 1 6 0z'],
  ['rehearsal', 'Ensayos', 'M8 3v4M16 3v4M3 10h18M4 5h16v16H4zM8 14h3M8 17h7'],
  ['evaluation', 'Valoraciones', 'M9 5H6a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V6a1 1 0 0 0-1-1h-3M9 5a3 3 0 0 1 6 0v1H9zM9 13l2 2 4-4'],
];

export function AppShell({ hidden, user, view, onNavigate, onSignOut, upload, analysis, repertoireMode, onRepertoireModeChange, workTab, onWorkTabChange, bandDraft, onBandDraftChange, minutes, onMinutesChange, onRecalculate, onUpdateBand, onConfirmInstruments, onBandActivated, onOpenWork, onOpenPassage, scoreViewer, rehearsalEditing, onEditRehearsal, onCloseRehearsal, onOpenBlock, onOpenEvaluationPassage,
  rehearsalReviewing, onReviewRehearsal, onCloseReview, onUserChanged }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const data = analysis?.data;
  const go = name => { setMenuOpen(false); onNavigate(name); };
  const busy = upload.state.busy;
  // The sections sit in a bar across the top (author's choice, 2026-10-25); on a narrow screen they fold behind «Menú».
  return <div id="app-shell" className="app-shell" hidden={hidden}>
    <header className="topbar">
      <div className="topbar-brand"><img className="brand-logo" src="/static/brand.svg" alt="" width="36" height="36" /><span>ScoreMaster</span></div>
      <button id="mobile-menu-button" className="mobile-menu-button" type="button" aria-controls="app-menu"
        aria-expanded={menuOpen} onClick={() => setMenuOpen(open => !open)}>Menú</button>
      <div id="app-menu" className={'topbar-menu' + (menuOpen ? ' is-open' : '')}>
        <nav className="app-nav" aria-label="Navegación principal">
          {views.map(([name, label, icon]) => <button key={name} className="nav-item" type="button" data-view-target={name}
            aria-current={view === name ? 'page' : undefined} onClick={() => go(name)}>
            <span className="nav-index"><svg viewBox="0 0 24 24" aria-hidden="true"><path d={icon} /></svg></span>{label}
          </button>)}
        </nav>
        <div className="topbar-account">
          <button type="button" className="nav-item" data-view-target="settings" aria-current={view === 'settings' ? 'page' : undefined}
            onClick={() => go('settings')}>
            <span className="nav-index"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></svg></span>
            <span className="settings-text">Configuración</span>
          </button>
          <span id="current-user" className="topbar-meta">{user?.display_name || user?.email || ''}</span>
          <button id="sign-out" className="sign-out" type="button" onClick={onSignOut}>Cerrar sesión</button>
        </div>
      </div>
      <ActivityStatus id="app-activity" className="topbar-activity" label={busy ? upload.state.message : ''} />
    </header>
    <main className="workspace">
        <SummaryView active={view} user={user} hidden={hidden} onNavigate={go} onOpenWork={onOpenWork} onOpenBlock={onOpenBlock} busy={busy}
          onPlanRehearsal={() => onEditRehearsal({})} onEditRehearsal={onEditRehearsal}
          onReviewRehearsal={onReviewRehearsal} />
        <RepertoireView active={view} user={user} hidden={hidden} analysis={analysis} mode={repertoireMode}
          onModeChange={onRepertoireModeChange} tab={workTab} onTabChange={onWorkTabChange} upload={upload}
          onOpenWork={onOpenWork} onOpenPassage={onOpenPassage} scoreViewer={scoreViewer} />
        <BandView active={view} hidden={hidden} onBandActivated={onBandActivated} data={data} draft={bandDraft} onDraftChange={onBandDraftChange} onUpdate={onUpdateBand} onConfirm={onConfirmInstruments} busy={busy} />
        <SettingsView active={view} user={user} onUserChanged={onUserChanged} />
        <ConcertsView active={view} hidden={hidden} onOpenBlock={onOpenBlock} />
        <EvaluationView active={view} hidden={hidden} onOpenBlock={onOpenBlock} onOpenEvaluationPassage={onOpenEvaluationPassage} />
        <RehearsalView active={view} hidden={hidden} onOpenBlock={onOpenBlock} reviewing={rehearsalReviewing}
          onReview={onReviewRehearsal} onCloseReview={onCloseReview} editing={rehearsalEditing} onEdit={onEditRehearsal} onCloseEditor={onCloseRehearsal} data={data} minutes={minutes} onMinutesChange={onMinutesChange} onRecalculate={onRecalculate} busy={busy} onOpenPassage={onOpenPassage} />
      </main>
  </div>;
}
