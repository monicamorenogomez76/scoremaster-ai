import React from 'react';
import { PLAN_FAMILIES, workHeadline } from './dashboard.js';

const NAMES = { woodwinds: 'Viento madera', brass: 'Viento metal', percussion: 'Percusión', strings: 'Cuerda' };

// «Dónde trabajar» (2026-10-26): a sentence with the answer and one bar per section of the band, each with its
// name and number of passages, so the colour of the family is never the only cue (WCAG 1.4.1).
export function SectionWork({ counts }) {
  const top = Math.max(1, ...PLAN_FAMILIES.map(family => counts[family] || 0));
  return <>
    <p className="section-work-headline">{workHeadline(counts)}</p>
    <ul className="section-work">
      {PLAN_FAMILIES.map(family => <li key={family} className={counts[family] ? '' : 'is-empty'}>
        <span className="section-work-name"><span className={'family-dot family-dot--' + family} aria-hidden="true" />{NAMES[family]}</span>
        <span className="section-work-track" aria-hidden="true">
          <span className={'section-work-fill section-work-fill--' + family} style={{ width: (counts[family] || 0) / top * 100 + '%' }} />
        </span>
        <span className="section-work-count">{counts[family] || 0}<span className="visually-hidden"> {counts[family] === 1 ? 'pasaje' : 'pasajes'}</span></span>
      </li>)}
    </ul>
  </>;
}
