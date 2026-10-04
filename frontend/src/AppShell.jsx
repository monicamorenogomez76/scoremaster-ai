import React, { useState } from 'react';
import { BandView } from './BandView.jsx';
import { DifficultyView } from './DifficultyView.jsx';
import { OverviewView } from './OverviewView.jsx';
import { RehearsalView } from './RehearsalView.jsx';
import { UploadWorkspace } from './UploadWorkspace.jsx';
import { VideoSearch } from './videos/VideoSearch.jsx';
import { View } from './View.jsx';

const views = [
  ['overview', 'Inicio', 'M3 10 12 3l9 7v10h-6v-6H9v6H3z'],
  ['analyze', 'Analizar partitura', 'M5 3h10l4 4v14H5zM9 11h6M9 15h6'],
  ['difficulty', 'Dificultad', 'M4 20V10M10 20V4M16 20v-8M22 20V7'],
  ['band', 'Mi banda', 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M17 4a4 4 0 0 1 0 8M22 21v-2a4 4 0 0 0-3-3.8'],
  ['rehearsal', 'Plan de ensayo', 'M8 3v4M16 3v4M3 10h18M4 5h16v16H4zM8 14h3M8 17h7'],
  ['videos', 'Vídeos', 'M4 5h16v14H4zM10 9l5 3-5 3z'],
];

export function AppShell({ hidden, view, onNavigate, onSignOut, upload, analysis, bandDraft, onBandDraftChange, minutes, onMinutesChange, onRecalculate, onOpenPassage, scoreViewer }) {
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
        <div className="demo-identity"><strong>Sesión de demo</strong><span>Plantilla temporal · análisis guardados</span></div>
        <button id="sign-out" className="sign-out" type="button" onClick={onSignOut}>Salir de la demo</button>
      </div>
    </aside>

    <div className="app-main">
      <header className="topbar">
        <button id="mobile-menu-button" className="mobile-menu-button" type="button" aria-label="Abrir menú"
          aria-expanded={menuOpen} onClick={() => setMenuOpen(open => !open)}>Menú</button>
        <p id="current-page-title" className="topbar-title">{(views.find(([name]) => name === view) || views[0])[1]}</p>
        <span className="topbar-meta">Modo demo</span>
      </header>
      <main className="workspace">
        <OverviewView active={view} data={data} onNavigate={go} />

        <View name="analyze" active={view} eyebrow="ScoreLint" title="Analizar partitura"
          description="Carga MusicXML para calcular la dificultad y localizar pasajes críticos.">
          <div id="upload-root" className="surface"><UploadWorkspace upload={upload} /></div>
          {scoreViewer}
        </View>

        <DifficultyView key={analysis?.revision ?? 0} active={view} data={data} onOpenPassage={onOpenPassage} />
        <BandView active={view} data={data} draft={bandDraft} onDraftChange={onBandDraftChange} onUpdate={onRecalculate} busy={busy} />
        <RehearsalView active={view} data={data} minutes={minutes} onMinutesChange={onMinutesChange} onRecalculate={onRecalculate} busy={busy} onOpenPassage={onOpenPassage} />

        <View name="videos" active={view} eyebrow="Repertorio" title="Vídeos relacionados"
          description="Busca grabaciones para la obra analizada.">
          {data
            ? <div id="videos-content" className="view-content">
                <section className="result-section result-section--wide">
                  <h2>Vídeos relacionados con {data.title || 'la obra'}</h2>
                  <VideoSearch key={analysis.fileName} title={data.title || ''} composer={data.composer || ''} fileName={analysis.fileName} />
                </section>
              </div>
            : <div id="videos-content" className="view-content empty-workspace"><h2>Aún no hay vídeos</h2><p>Analiza una partitura para buscar grabaciones relacionadas.</p></div>}
        </View>
      </main>
    </div>
  </div>;
}
