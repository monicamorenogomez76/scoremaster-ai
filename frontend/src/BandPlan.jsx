import React from 'react';
import { PLAN_FAMILIES } from './dashboard.js';

// The band seen from the podium (identity of 2026-10-26): woodwinds in front, brass behind, percussion at the back
// and strings to one side. Each section is drawn stronger the higher its value; the figure is described in words
// (WCAG 1.1.1) and a legend under it names each section with its value, so colour is never the only cue (WCAG 1.4.1).
const ARCS = {
  percussion: { path: 'M40 220 A180 180 0 0 1 400 220', width: 24 },
  brass: { path: 'M82 220 A138 138 0 0 1 358 220', width: 28 },
  woodwinds: { path: 'M126 220 A94 94 0 0 1 314 220', width: 30 },
  strings: { path: 'M168 220 A52 52 0 0 1 220 168', width: 20 },
};
const ORDER = ['woodwinds', 'brass', 'percussion', 'strings'];

export function BandPlan({ id, title, note, values, max, label, description }) {
  const top = Math.max(1, max ?? Math.max(...PLAN_FAMILIES.map(family => values[family] || 0)));
  return <figure id={id} className="band-plan">
    <figcaption className="band-plan-caption"><strong>{title}</strong>{note && <span>{note}</span>}</figcaption>
    <svg className="band-plan-figure" viewBox="0 0 440 236" role="img" aria-label={description}>
      {PLAN_FAMILIES.map(family => <path key={family} d={ARCS[family].path} className={'band-plan-arc band-plan-arc--' + family}
        strokeWidth={ARCS[family].width} style={{ opacity: values[family] ? .45 + .55 * values[family] / top : .2 }} />)}
      <circle cx="220" cy="226" r="8" className="band-plan-podium" />
    </svg>
    <ul className="band-plan-legend" aria-hidden="true">
      {ORDER.map(family => <li key={family} className={values[family] ? '' : 'is-empty'}>
        <span className={'family-dot family-dot--' + family} />{label(family, values[family] || 0)}</li>)}
    </ul>
  </figure>;
}
