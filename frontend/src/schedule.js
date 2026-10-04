// Clock times of rehearsal blocks from the start time, and their share of the timeline.
const DEFAULT_START = '19:00';
const MINUTES_PER_DAY = 24 * 60;

const toMinutes = value => {
  const match = /^([01]?\d|2[0-3]):([0-5]\d)$/.exec(String(value || '').trim());
  return match ? Number(match[1]) * 60 + Number(match[2]) : toMinutes(DEFAULT_START);
};
const clock = minutes => {
  const wrapped = ((minutes % MINUTES_PER_DAY) + MINUTES_PER_DAY) % MINUTES_PER_DAY;
  return String(Math.floor(wrapped / 60)).padStart(2, '0') + ':' + String(wrapped % 60).padStart(2, '0');
};

export function rehearsalSchedule(blocks, start = DEFAULT_START) {
  const total = blocks.reduce((sum, block) => sum + (block.minutes || 0), 0) || 1;
  let elapsed = 0;
  return blocks.map(block => {
    const begin = toMinutes(start) + elapsed;
    const item = { ...block, start: clock(begin), end: clock(begin + (block.minutes || 0)),
      offset: elapsed / total, share: (block.minutes || 0) / total };
    elapsed += block.minutes || 0;
    return item;
  });
}
