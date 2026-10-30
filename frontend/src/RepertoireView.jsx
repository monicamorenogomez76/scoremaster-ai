import React from 'react';
import { DifficultyPanel, PublishedGrades, WorkExplanation } from './DifficultyView.jsx';
import { OverviewPanel } from './OverviewView.jsx';
import { PdfUpload } from './PdfUpload.jsx';
import { UploadWorkspace } from './UploadWorkspace.jsx';
import { VideoSearch } from './videos/VideoSearch.jsx';
import { View } from './View.jsx';
import { WorksList } from './WorksView.jsx';
import { t } from './i18n.js';

const tabs = () => [['score', t('Partitura')], ['difficulty', t('Dificultad')], ['recordings', t('Grabaciones')]];

// Repertoire: the list of works (and the form to add one), or the detail of the open work.
// The detail stays mounted while hidden: the score viewer keeps its renderer between tabs and modes.
export function RepertoireView({ active, user, hidden, analysis, mode, onModeChange, tab, onTabChange, upload, onOpenWork, onOpenPassage, scoreViewer, minutes }) {
  const data = analysis?.data;
  const detail = mode === 'detail' && Boolean(data);
  const busy = upload.state.busy;
  const action = <button id="add-work" className="primary-action" type="button" onClick={() => onModeChange('add')}>{t('Añadir obra')}</button>;
  return <View name="repertoire" active={active} eyebrow={t('Biblioteca')} title={t('Repertorio')}
    description={t('Tus obras, su estado de preparación y su análisis.')} action={action}>
    <div id="upload-root" className="surface" hidden={mode !== 'add'}>
      <h2 className="panel-title">{t('Añadir obra')}</h2>
      <p className="result-supporting">{t('Formatos admitidos: MusicXML (.musicxml, .xml) y MusicXML comprimido (.mxl). Al subirla se analiza y se guarda en tu repertorio.')}</p>
      <UploadWorkspace upload={upload} />
      <PdfUpload visible={!hidden && active === 'repertoire' && mode === 'add'} minutes={minutes} onOpenWork={onOpenWork} />
    </div>

    <div hidden={detail}>
      {/* Keyed by user: a new session never shows the previous user's works. */}
      <WorksList key={user?.email ?? 'signed-out'} visible={!hidden && active === 'repertoire' && !detail}
        revision={analysis?.revision ?? 0} onOpen={onOpenWork} busy={busy} />
    </div>

    <section id="work-detail" className="work-detail" hidden={!detail} aria-labelledby="work-detail-title">
      <div className="work-detail-heading">
        <div>
          <h2 id="work-detail-title">{data?.title || t('Partitura sin título')}</h2>
          <p className="result-supporting">{data?.composer || t('Compositor no indicado en el MusicXML')}</p>
          {data?.source_format === 'pdf' && <p className="pdf-provisional" role="note">{t('Leída de PDF · grado provisional: revisa en la partitura las notas más agudas y graves, y confirma los instrumentos en Mi banda.')}</p>}
        </div>
        <button id="back-to-list" className="secondary-action" type="button" onClick={() => onModeChange('list')}>{t('Volver al repertorio')}</button>
      </div>
      <div className="work-tabs" role="tablist" aria-label={t('Secciones de la obra')}>
        {tabs().map(([name, label]) => <button key={name} id={'work-tab-' + name} type="button" role="tab"
          aria-selected={tab === name} aria-controls={'work-panel-' + name} onClick={() => onTabChange(name)}>{label}</button>)}
      </div>
      <div id="work-panel-score" role="tabpanel" aria-labelledby="work-tab-score" hidden={tab !== 'score'}>{scoreViewer}</div>
      <div id="work-panel-difficulty" role="tabpanel" aria-labelledby="work-tab-difficulty" hidden={tab !== 'difficulty'}>
        {/* First in the tab, where it is seen without scrolling (2026-10-07: «¿dónde lo veo?»). */}
        {data && <WorkExplanation key={data.work_id} workId={data.work_id} onOpenPassage={onOpenPassage} />}
        <OverviewPanel data={data} onStart={() => onModeChange('add')}
          onOpenDifficulty={() => document.getElementById('difficulty-content')?.scrollIntoView({ behavior: 'smooth', block: 'start' })} />
        {data?.work_id && data.difficulty?.grade != null && <PublishedGrades key={data.work_id} workId={data.work_id} grade={data.difficulty.grade} />}
        {data && <DifficultyPanel key={analysis.revision} data={data} onOpenPassage={onOpenPassage} />}
      </div>
      <div id="work-panel-recordings" role="tabpanel" aria-labelledby="work-tab-recordings" hidden={tab !== 'recordings'}>
        {data && <div id="videos-content" className="view-content">
          <section className="result-section result-section--wide">
            <h2>{t('Grabaciones de {title}', { title: data.title || t('la obra') })}</h2>
            <VideoSearch key={analysis.fileName} title={data.title || ''} composer={data.composer || ''} fileName={analysis.fileName} />
          </section>
        </div>}
      </div>
    </section>
  </View>;
}
