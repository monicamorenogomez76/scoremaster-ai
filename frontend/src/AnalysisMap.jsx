import React, { useEffect, useRef, useState } from 'react';
import { articulationText, cadenceText, harmonyDetailsText, keyName, markText, meterText, modulationText, orchestrationText,
  periodText, phrasesText, relationText, rhythmText, textureKindText, textureText, themeText } from './musicalAnalysis.js';
import { t } from './i18n.js';

const at = left => ({ left: left + '%' });
const spanned = item => ({ left: item.left + '%', width: item.width + '%' });

// The map of the work (2026-11-20): the form as in a conservatory analysis, every lane on one axis of measures. The
// sections are buttons that choose the sheet below; the other lanes are drawn, and the tables say the same in text.
export function WorkMap({ map, selected, onSelect }) {
  // When the map is wider than its box it scrolls sideways, and says so: overlay scrollbars hide until used.
  const scroller = useRef(null);
  const [wider, setWider] = useState(false);
  useEffect(() => {
    const box = scroller.current;
    if (!box) return undefined;
    const measure = () => setWider(box.scrollWidth > box.clientWidth + 1);
    measure();
    if (typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(measure);
    observer.observe(box);
    return () => observer.disconnect();
  }, [map.minWidth]);
  return <section className="work-map" aria-labelledby="work-map-title">
    <div className="work-map-heading">
      <h3 id="work-map-title">{t('Mapa de la obra')}</h3>
      <p className="result-supporting">{t('Pulsa una sección para ver su ficha. Todo va en el mismo eje de compases.')}</p>
    </div>
    {wider && <p className="work-map-more">{t('El mapa sigue a la derecha: desplázalo para ver toda la obra →')}</p>}
    <div ref={scroller} className="work-map-scroll" tabIndex={0} role="region" aria-label={t('Mapa de la obra')}>
      <div className="work-map-lanes" style={{ minWidth: map.minWidth + 'px' }}>
        <div className="work-map-lane" aria-hidden="true">
          <span className="work-map-label">{t('compás')}</span>
          <div className="work-map-track work-map-track--axis">
            {map.ticks.map(tick => <span key={tick.measure} className="work-map-tick" style={at(tick.left)}>{tick.measure}</span>)}
          </div>
        </div>
        <div className="work-map-lane">
          <span className="work-map-label" aria-hidden="true">{t('Forma')}</span>
          <ol className="work-map-track work-map-track--form" aria-label={t('Secciones de la obra en orden')}>
            {map.sections.map(section => <li key={section.id} style={spanned(section)}>
              <button type="button" className={'work-map-section work-map-colour--' + section.colour}
                aria-pressed={section.id === selected} onClick={() => onSelect(section.id)}
                title={section.label + ' · ' + t('cc. {first}–{last}', { first: section.first, last: section.last }) + ' · ' + keyName(section.key)}
                aria-label={t('Sección {label}, cc. {first}–{last}, {key}', { label: section.label, first: section.first,
                  last: section.last, key: keyName(section.key) })}>
                <strong>{section.label}</strong>
                <span>{t('cc. {first}–{last}', { first: section.first, last: section.last })}</span>
              </button>
            </li>)}
          </ol>
        </div>
        <div className="work-map-lane" aria-hidden="true">
          <span className="work-map-label">{t('Tonalidad')}</span>
          <div className="work-map-track work-map-track--keys">
            {map.keys.map(key => <span key={key.left} className={'work-map-key work-map-tint--' + key.colour} style={spanned(key)}
              title={key.name}>{key.name}</span>)}
          </div>
        </div>
        {map.phrases.length > 0 && <div className="work-map-lane" aria-hidden="true">
          <span className="work-map-label">{t('Frases')}</span>
          <div className="work-map-track work-map-track--phrases">
            {map.phrases.map(phrase => <span key={phrase.left} className="work-map-phrase" style={spanned(phrase)} />)}
          </div>
        </div>}
        {map.themes.length > 0 && <div className="work-map-lane" aria-hidden="true">
          <span className="work-map-label">{t('Temas')}</span>
          <div className="work-map-track work-map-track--themes">
            {map.themes.map(theme => <span key={theme.id + theme.left} className="work-map-theme" style={at(theme.left)}>{theme.label}</span>)}
          </div>
        </div>}
        {map.cadences.length > 0 && <div className="work-map-lane" aria-hidden="true">
          <span className="work-map-label">{t('Cadencias')}</span>
          <div className="work-map-track work-map-track--cadences">
            {map.cadences.map(cadence => <span key={cadence.id} className="work-map-cadence" style={at(cadence.left)}
              title={t('{kind} (c. {measure})', { kind: cadenceText(cadence.kind), measure: cadence.measure })}>{cadence.symbol}</span>)}
          </div>
        </div>}
        {map.dynamics.length > 0 && <div className="work-map-lane" aria-hidden="true">
          <span className="work-map-label">{t('Dinámica')}</span>
          <div className="work-map-track work-map-track--bars">
            {map.dynamics.map((level, place) => <span key={place} className="work-map-bar" style={{ height: level * 100 + '%' }} />)}
            {map.climax && <span className="work-map-climax" style={at(map.climax.left)}>
              {t('★ clímax c. {measure} · {dynamic}', map.climax)}</span>}
          </div>
        </div>}
        {map.playing.length > 0 && <div className="work-map-lane" aria-hidden="true">
          <span className="work-map-label">{t('Partes')}</span>
          <div className="work-map-track work-map-track--bars work-map-track--playing">
            {map.playing.map((share, place) => <span key={place} className="work-map-bar" style={{ height: share * 100 + '%' }} />)}
          </div>
        </div>}
      </div>
    </div>
    <ul className="work-map-legend">
      <li>{t('Mismo color, mismo material: una sección que vuelve lleva el color de la primera vez.')}</li>
      <li><span aria-hidden="true">●</span> {t('cadencia auténtica')}</li>
      <li><span aria-hidden="true">◐</span> {t('semicadencia')}</li>
      <li><span aria-hidden="true">○</span> {t('cadencia plagal')}</li>
      <li><span aria-hidden="true">◇</span> {t('cadencia rota')}</li>
    </ul>
  </section>;
}

// The sheet of one section: what the tables spread over the topics, together, with its commentary when there is one.
export function SectionSheet({ analysis, section, comment, onSelect }) {
  const labelOf = id => analysis.sections.find(item => item.id === id)?.label || id;
  const place = analysis.sections.findIndex(item => item.id === section.id);
  const neighbour = step => analysis.sections[(place + step + analysis.sections.length) % analysis.sections.length].id;
  const cadences = analysis.cadences.filter(cadence => cadence.section === section.id)
    .map(cadence => t('{kind} (c. {measure})', { kind: cadenceText(cadence.kind), measure: cadence.measure })).join(', ');
  const join = (...items) => items.filter(item => item && item !== '—').join(' · ');
  const facts = [
    [t('Material'), join(section.like ? t('vuelve el material de {section}', { section: labelOf(section.like) }) : t('nuevo'),
      themeText(section))],
    [t('Frases'), join(phrasesText(section), ...section.periods.map(periodText))],
    [t('Armonía'), join(keyName(section.key) + ' (' + relationText(section.relation) + ')',
      ...section.modulations.map(modulationText), harmonyDetailsText(section), cadences)],
    [t('Textura'), join(textureKindText(section.texture_kind), textureText(section.texture), t('{count} partes', { count: section.playing.length }),
      section.melody && t('melodía: {part}', { part: section.melody }) + (section.doubled_by.length
        ? ' ' + t('(doblada por {parts})', { parts: section.doubled_by.join(', ') }) : ''))],
    [t('Orquestación'), orchestrationText(section)],
    [t('Ritmo'), join(section.tempo ? '♩ = ' + section.tempo : '', section.meter, rhythmText(section), meterText(section))],
    [t('Dinámica'), join(section.dynamics.join(' '), articulationText(section))],
    [t('Marcas'), [...section.marks, ...section.marks_at_end].map(markText).join(', ')],
  ].filter(([, text]) => text && text !== '—');
  return <section className={'section-sheet work-map-edge--' + section.colour} aria-labelledby="section-sheet-title" aria-live="polite">
    <div className="section-sheet-heading">
      <h3 id="section-sheet-title">{t('Sección {label} · cc. {first}–{last}', section)}</h3>
      {analysis.sections.length > 1 && <div className="section-sheet-actions">
        <button type="button" className="secondary-action" onClick={() => onSelect(neighbour(-1))}>{t('← Anterior')}</button>
        <button type="button" className="secondary-action" onClick={() => onSelect(neighbour(1))}>{t('Siguiente →')}</button>
      </div>}
    </div>
    <dl className="section-sheet-facts">
      {facts.map(([topic, text]) => <div key={topic}><dt>{topic}</dt><dd>{text}</dd></div>)}
    </dl>
    {comment && <div className="analysis-commentary">
      <p className="analysis-commentary-label">{t('Comentario')}</p>
      <p>{comment}</p>
    </div>}
  </section>;
}
