import React from 'react';

const icons = {
  play: 'M8 4v16l13-8z',
  pause: 'M7 5h4v14H7zm6 0h4v14h-4z',
  stop: 'M6 6h12v12H6z',
  fullscreen: 'M3 3h7v2H5v5H3zm11 0h7v7h-2V5h-5zM3 14h2v5h5v2H3zm16 0h2v7h-7v-2h5z',
};
export const Icon = ({ path }) => <svg viewBox="0 0 24 24" aria-hidden="true"><path d={path} /></svg>;
const speeds = [['0.5', '50 %'], ['0.75', '75 %'], ['1', '100 %'], ['1.25', '125 %'], ['1.5', '150 %']];

// Controls shared by the full score and the passage viewer, so both behave and look alike.
export function TransportBar({ prefix, label, volumeLabel, seekLabel, fullscreenId, transport, playDisabled, stopDisabled, onStop, onFullscreen, group }) {
  const action = transport.playing ? 'Pausar' : 'Reproducir';
  return <>
    <div className={'ensemble-toolbar' + (group ? ' passage-transport' : '')} role={group ? 'group' : undefined} aria-label={label}>
      <button id={prefix + '-play'} className="score-tool transport-primary" type="button" aria-label={action} title={action}
        disabled={playDisabled || transport.loading} onClick={transport.toggle}><Icon path={transport.playing ? icons.pause : icons.play} /></button>
      <button id={prefix + '-stop'} className="score-tool" type="button" aria-label="Detener" title="Detener"
        disabled={stopDisabled} onClick={onStop}><Icon path={icons.stop} /></button>
      <output id={prefix + '-time'}>{transport.time}</output>
      <label>Velocidad <select id={prefix + '-speed'} defaultValue="1" onChange={event => transport.setSpeed(Number(event.target.value))}>
        {speeds.map(([value, text]) => <option key={value} value={value}>{text}</option>)}
      </select></label>
      <label>Volumen <input id={prefix + '-volume'} ref={transport.bindVolume} type="range" min="0" max="100" defaultValue="50" aria-label={volumeLabel} /></label>
      <button id={fullscreenId} className="score-tool" type="button" aria-label="Pantalla completa" title="Pantalla completa" onClick={onFullscreen}><Icon path={icons.fullscreen} /></button>
    </div>
    <input id={prefix + '-seek'} ref={transport.bindSeek} type="range" min="0" max="1" step="0.1" defaultValue="0" aria-label={seekLabel} />
  </>;
}
