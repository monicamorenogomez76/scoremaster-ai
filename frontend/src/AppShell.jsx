import React, { useState } from 'react';
import { BandView } from './BandView.jsx';
import { RehearsalView } from './RehearsalView.jsx';
import { RepertoireView } from './RepertoireView.jsx';
import { SummaryView } from './SummaryView.jsx';

const views = [
  ['summary', 'Resumen', 'M3 10 12 3l9 7v10h-6v-6H9v6H3z'],
  ['repertoire', 'Repertorio', 'M3 6h6l2 2h10v11H3zM3 6v13'],
  ['band', 'Mi banda', 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M17 4a4 4 0 0 1 0 8M22 21v-2a4 4 0 0 0-3-3.8'],
  ['rehearsal', 'Ensayos', 'M8 3v4M16 3v4M3 10h18M4 5h16v16H4zM8 14h3M8 17h7'],
];

export function AppShell({ hidden, user, view, onNavigate, onSignOut, upload, analysis, repertoireMode, onRepertoireModeChange, workTab, onWorkTabChange, bandDraft, onBandDraftChange, minutes, onMinutesChange, onRecalculate, onUpdateBand, onConfirmInstruments, onOpenWork, onOpenPassage, scoreViewer, rehearsalEditing, onEditRehearsal, onCloseRehearsal }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const data = analysis?.data;
  const go = name => { setMenuOpen(false); onNavigate(name); };
  const busy = upload.state.busy;
  return <div id="app-shell" className="app-shell" hidden={hidden}>
    <aside id="sidebar" className={'sidebar' + (menuOpen ? ' is-open' : '')}>
      <div className="sidebar-brand"><img className="brand-logo" src="/static/brand.svg" alt="" width="44" height="44" /><span>ScoreMaster</span></div>
      <p className="nav-label">Espacio de trabajo</p>
      <nav className="app-nav" aria-label="Navegación principal">
        {views.map(([name, label, icon]) => <button key={name} className="nav-item" type="button" data-view-target={name}
          aria-current={view === name ? 'page' : undefined} onClick={() => go(name)}>
          <span className="nav-index"><svg viewBox="0 0 24 24" aria-hidden="true"><path d={icon} /></svg></span>{label}
        </button>)}
      </nav>
      <div className="sidebar-bottom">
        <div className="demo-identity"><strong>{user?.display_name || 'Sesión iniciada'}</strong><span>{user?.email || ''}</span></div>
        <button id="sign-out" className="sign-out" type="button" onClick={onSignOut}>Cerrar sesión</button>
      </div>
    </aside>

    <div className="app-main">
      <header className="topbar">
        <button id="mobile-menu-button" className="mobile-menu-button" type="button" aria-label="Abrir menú"
          aria-expanded={menuOpen} onClick={() => setMenuOpen(open => !open)}>Menú</button>
        <p id="current-page-title" className="topbar-title">{(views.find(([name]) => name === view) || views[0])[1]}</p>
        <span id="current-user" className="topbar-meta">{user?.display_name || user?.email || ''}</span>
      </header>
      <main className="workspace">
        <SummaryView active={view} user={user} hidden={hidden} onNavigate={go} onOpenWork={onOpenWork} busy={busy}
          onPlanRehearsal={() => onEditRehearsal({})} onEditRehearsal={onEditRehearsal} />
        <RepertoireView active={view} user={user} hidden={hidden} analysis={analysis} mode={repertoireMode}
          onModeChange={onRepertoireModeChange} tab={workTab} onTabChange={onWorkTabChange} upload={upload}
          onOpenWork={onOpenWork} onOpenPassage={onOpenPassage} scoreViewer={scoreViewer} />
        <BandView active={view} data={data} draft={bandDraft} onDraftChange={onBandDraftChange} onUpdate={onUpdateBand} onConfirm={onConfirmInstruments} busy={busy} />
        <RehearsalView active={view} hidden={hidden} editing={rehearsalEditing} onEdit={onEditRehearsal} onCloseEditor={onCloseRehearsal} data={data} minutes={minutes} onMinutesChange={onMinutesChange} onRecalculate={onRecalculate} busy={busy} onOpenPassage={onOpenPassage} />
      </main>
    </div>
  </div>;
}
