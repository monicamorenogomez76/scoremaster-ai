import React from 'react';
import { agendaCalendarLabel, agendaSchedule, blockGroup, blockWorkText } from './rehearsals.js';
import { t } from './i18n.js';

// Coloured timeline of a saved agenda: each block as wide as its minutes, coloured by its type
// like the rehearsal plan; the work rehearsed in it is its main text (requested 2026-10-05).
// With onOpenBlock, the boxes of a work open its passage in the score.
export function AgendaCalendar({ blocks, start, onOpenBlock }) {
  if (!blocks.length) return null;
  return <div className="rehearsal-calendar agenda-calendar">
    <div className="calendar-track" role="list" aria-label={t('Calendario de la agenda')}>
      {agendaSchedule(blocks, start).map((block, index) => {
        const description = [block.start + '–' + block.end, block.title || t('Bloque {number}', { number: index + 1 }), blockWorkText(block), block.minutes + ' min'].join(' · ');
        return <div key={index} role="listitem" className={'calendar-slot calendar-slot--' + blockGroup(block)}
          style={{ flexGrow: block.share, flexBasis: 0 }}>
          {(() => {
            const content = <>
              <span className="calendar-time">{block.start} · {block.minutes} min</span>
              <span className="calendar-work">{block.work_title || t('Toda la banda')}</span>
              <span className="calendar-name">{agendaCalendarLabel(block)}</span>
            </>;
            return onOpenBlock && block.work_id
              ? <button type="button" className="calendar-block" aria-label={t('Abrir · {description}', { description })} title={description}
                  onClick={() => onOpenBlock({ ...block, label: block.title + ' · ' + block.work_title })}>{content}</button>
              : <div className="calendar-block" aria-label={description} title={description}>{content}</div>;
          })()}
        </div>;
      })}
    </div>
  </div>;
}
