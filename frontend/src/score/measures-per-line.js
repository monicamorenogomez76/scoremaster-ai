// How many measures each line of the score shows (2026-11-25), chosen by the director and kept in this browser; null is
// automatic. No more than sixteen: a longer line of a whole band stops the browser while it is drawn.
export const MEASURE_CHOICES = [1, 2, 3, 4, 5, 6, 8, 10, 12, 16];
const KEY = 'scoremaster-measures-per-line';
const deviceStorage = () => { try { return globalThis.localStorage; } catch { return undefined; } };

export function keptMeasures(storage = deviceStorage()) {
  try {
    const kept = Number(storage?.getItem(KEY));
    return MEASURE_CHOICES.includes(kept) ? kept : null;
  } catch { return null; }
}

export function keepMeasures(count, storage = deviceStorage()) {
  try { if (count) storage?.setItem(KEY, String(count)); else storage?.removeItem(KEY); } catch { /* not kept */ }
}
