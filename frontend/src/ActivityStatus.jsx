import React, { useEffect, useState } from 'react';
import { activityText } from './progress.js';

// A slow action in progress: an animated bar, the step and the time it has taken. The count starts
// again when the step changes, so each step shows its own wait.
export function ActivityStatus({ label, id, className = '' }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    setSeconds(0);
    if (!label) return undefined;
    const started = Date.now();
    const timer = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [label]);
  if (!label) return null;
  // Screen readers hear the step once; the count changes every second, so it is only visual.
  return <div id={id} className={'activity-status ' + className}>
    <span className="activity-bar" aria-hidden="true"><span /></span>
    <span className="visually-hidden" role="status" aria-live="polite">{label}…</span>
    <span className="activity-text" aria-hidden="true">{activityText(label, seconds)}</span>
  </div>;
}
