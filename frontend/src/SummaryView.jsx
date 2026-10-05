import React, { useEffect, useState } from 'react';
import { findingLabel, gradeScaleOf, gradeText } from './labels.js';
import { groupPrioritiesBySection, listPriorities, listWorks } from './library.js';
import { View } from './View.jsx';

const measuresText = range => (String(range).includes('-') ? 'cc. ' + String(range).replace('-', '–') : 'c. ' + range);

function Card({ id, title, action, children }) {
  return <section id={id} className="summary-card surface" aria-labelledby={id + '-title'}>
    <div className="summary-card-heading"><h2 id={id + '-title'}>{title}</h2>{action}</div>
    {children}
  </section>;
}

// Home of the director: next rehearsal, works in preparation and the priorities found in them.
export function SummaryView({ active, user, hidden, onNavigate, onOpenWork, busy }) {
  const [works, setWorks] = useState(null);
  const [priorities, setPriorities] = useState(null);
  const [error, setError] = useState('');
  const visible = !hidden && active === 'summary';
  useEffect(() => {
    if (!visible) return undefined;
    let current = true;
    Promise.all([listWorks(), listPriorities()])
      .then(([found, passages]) => { if (current) { setWorks(found); setPriorities(passages); setError(''); } })
      .catch(failure => { if (current) setError(failure.message); });
    return () => { current = false; };
  }, [visible, user?.email]);
  const preparing = (works || []).filter(work => work.preparation_status === 'preparing');
  const link = (label, view) => <button type="button" className="link-action" onClick={() => onNavigate(view)}>{label}</button>;
  const action = <button id="plan-rehearsal" className="primary-action" type="button" onClick={() => onNavigate('rehearsal')}>Planificar ensayo</button>;

  return <View name="summary" active={active} eyebrow="Resumen" title="Tu próximo ensayo, preparado"
    description="Lo que necesitas para dirigir la próxima sesión." action={action}>
    {error && <p className="result-supporting" role="alert">{error}</p>}
    <div className="summary-grid">
      <Card id="summary-rehearsal" title="Próximo ensayo" action={link('Ir a Ensayos', 'rehearsal')}>
        <div className="empty-workspace"><h3>Aún no hay ensayos guardados</h3>
          <p>Cuando guardes un ensayo aparecerán aquí su fecha y su agenda. Mientras tanto, en Ensayos puedes calcular el plan de la obra abierta.</p></div>
      </Card>

      <Card id="summary-works" title="Obras en preparación" action={link('Ver repertorio', 'repertoire')}>
        {works && preparing.length === 0 && <div className="empty-workspace"><h3>Ninguna obra en preparación</h3>
          <p>Marca en Repertorio las obras que estáis preparando para seguirlas desde aquí.</p></div>}
        {preparing.length > 0 && <table className="summary-table">
          <thead><tr><th scope="col">Obra</th><th scope="col">Compositor</th><th scope="col">Dificultad</th></tr></thead>
          <tbody>{preparing.map(work => <tr key={work.id}>
            <td><button type="button" className="link-action" disabled={busy} onClick={() => onOpenWork(work.id)}>{work.title}</button>
              <span className="table-supporting">{work.file_name}</span></td>
            <td>{work.composer || '—'}</td>
            <td>{work.summary?.grade == null ? 'Sin analizar'
              : gradeText(work.summary, gradeScaleOf({ scale: { grades: work.summary.grade_max } }))}</td>
          </tr>)}</tbody>
        </table>}
      </Card>

      <Card id="summary-priorities" title="Prioridades por sección">
        {priorities && priorities.length === 0 && <div className="empty-workspace"><h3>Sin prioridades por ahora</h3>
          <p>Aquí aparecen los pasajes críticos de las obras en preparación. Más adelante se sumarán tus notas de ensayo.</p></div>}
        {priorities && priorities.length > 0 && <table className="summary-table">
          <thead><tr><th scope="col">Sección</th><th scope="col">Obra</th><th scope="col">Pasaje</th><th scope="col">Motivo</th><th scope="col">Origen</th></tr></thead>
          <tbody>{groupPrioritiesBySection(priorities).flatMap(([section, items]) => items.map((item, index) =>
            <tr key={[item.work_id, item.instrument, item.measure_range, index].join('|')}>
              {index === 0 && <th scope="rowgroup" rowSpan={items.length}>{section}</th>}
              <td><button type="button" className="link-action" disabled={busy} onClick={() => onOpenWork(item.work_id)}>{item.title}</button>
                <span className="table-supporting">{item.instrument_label_es || item.instrument}</span></td>
              <td>{measuresText(item.measure_range)}</td>
              <td>{(item.findings || []).map(findingLabel).join(' · ')}</td>
              <td><span className="status-tag">Análisis</span></td>
            </tr>))}</tbody>
        </table>}
      </Card>
    </div>
  </View>;
}
