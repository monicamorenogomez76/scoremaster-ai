import React from 'react';
import { agendaCalendarLabel, agendaSchedule, blockWorkText } from './rehearsals.js';

// Coloured timeline of a saved agenda: each block as wide as its minutes, coloured by its type
// like the rehearsal plan, with the work rehearsed in it.
export function AgendaCalendar({ blocks, start }) {
  if (!blocks.length) return null;
  return <div className="rehearsal-calendar agenda-calendar">
    <div className="calendar-track" role="list" aria-label="Calendario de la agenda">
      {agendaSchedule(blocks, start).map((block, index) => {
        const description = [block.start + '–' + block.end, block.title || 'Bloque ' + (index + 1), blockWorkText(block), block.minutes + ' min'].join(' · ');
        return <div key={index} role="listitem" className={'calendar-slot calendar-slot--' + (block.group || 'other')}
          style={{ flexGrow: block.share, flexBasis: 0 }}>
          <div className="calendar-block" aria-label={description} title={description}>
            <span className="calendar-time">{block.start}</span>
            <span className="calendar-name">{agendaCalendarLabel(block)}</span>
            {block.work_title && <span className="calendar-work">{block.work_title}</span>}
          </div>
        </div>;
      })}
    </div>
  </div>;
}
