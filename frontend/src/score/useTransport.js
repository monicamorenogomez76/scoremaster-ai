import { useCallback, useEffect, useRef, useState } from 'react';
import { preparePlayback, stopPlayback } from './playback.js';

export const clock = seconds => Math.floor(seconds / 60) + ':' + String(Math.floor(seconds % 60)).padStart(2, '0');

// Shared play/pause/stop lifecycle for both viewers. `prepare(onStatus)` resolves to a transport
// from playback.js; a newer request or a stop discards any older one still loading.
export function useTransport({ prepare, onPosition, stoppedMessage }) {
  const [state, setState] = useState({ ready: false, loading: false, playing: false, time: '0:00 / 0:00', status: stoppedMessage });
  const transport = useRef(null), generation = useRef(0), playing = useRef(false);
  const settings = useRef({ speed: 1, volume: .5 });
  const latest = useRef({ prepare, onPosition }); latest.current = { prepare, onPosition };
  const seek = useRef(null);

  const reset = useCallback((status = stoppedMessage) => {
    generation.current++; stopPlayback();
    transport.current = null; playing.current = false;
    if (seek.current) { seek.current.value = 0; seek.current.disabled = true; }
    setState({ ready: false, loading: false, playing: false, time: '0:00 / 0:00', status });
  }, [stoppedMessage]);

  const toggle = useCallback(async () => {
    const current = transport.current;
    if (current) { if (playing.current) current.pause(); else await current.play(); return; }
    const token = ++generation.current;
    const isCurrent = () => token === generation.current;
    setState(previous => ({ ...previous, loading: true, status: 'Cargando sonidos…' }));
    try {
      const ready = await latest.current.prepare(message => {
        if (isCurrent()) setState(previous => ({ ...previous, status: message }));
      });
      if (!ready || !isCurrent()) return;
      transport.current = ready;
      ready.setSpeed(settings.current.speed);
      ready.setVolume(settings.current.volume);
      if (seek.current) { seek.current.max = ready.duration; seek.current.disabled = false; }
      ready.subscribe(update => {
        if (!isCurrent()) return;
        playing.current = update.playing;
        if (seek.current) seek.current.value = update.position;
        setState(previous => ({ ...previous, ready: true, playing: update.playing, time: clock(update.position) + ' / ' + clock(update.duration) }));
        latest.current.onPosition?.(update.currentMeasure, update.playing);
      });
      await ready.play();
    } catch (error) {
      if (!isCurrent()) return;
      reset(error.name === 'AbortError' ? 'Carga cancelada o demasiado lenta. Puedes volver a intentarlo.' : error.message || 'No se pudo cargar el sonido. Comprueba la conexión a Internet.');
    } finally {
      if (isCurrent()) setState(previous => ({ ...previous, loading: false }));
    }
  }, [reset]);

  const setSpeed = useCallback(value => { settings.current.speed = value; transport.current?.setSpeed(value); }, []);

  // Native listeners: the seek bar moves 20 times per second without re-rendering, and
  // programmatic value changes (keyboard, tests) still reach the transport.
  const bindSeek = useCallback(node => {
    seek.current = node;
    if (node) node.disabled = !transport.current;
    node?.addEventListener('change', () => transport.current?.seek(Number(node.value)));
  }, []);
  const bindVolume = useCallback(node => {
    node?.addEventListener('input', () => {
      settings.current.volume = Number(node.value) / 100;
      transport.current?.setVolume(settings.current.volume);
    });
  }, []);

  useEffect(() => () => { generation.current++; }, []);
  return { ...state, toggle, reset, setSpeed, bindSeek, bindVolume };
}
