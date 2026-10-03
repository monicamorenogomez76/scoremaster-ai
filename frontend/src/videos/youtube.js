const VIDEO_ID = /^[A-Za-z0-9_-]{11}$/;
const YOUTUBE_HOSTS = ['youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com'];
export const MAX_QUERY = 200;

// Accepts only YouTube watch, short, embed and youtu.be links; anything else returns null.
export function parseYouTubeVideoId(value) {
  try {
    const url = new URL(value.trim());
    const host = url.hostname.toLowerCase();
    let videoId = '';
    if (host === 'youtu.be') videoId = url.pathname.slice(1).split('/')[0];
    if (YOUTUBE_HOSTS.includes(host)) {
      if (url.pathname === '/watch') videoId = url.searchParams.get('v') || '';
      else videoId = url.pathname.match(/^\/(?:embed|shorts)\/([A-Za-z0-9_-]{11})/)?.[1] || '';
    }
    return VIDEO_ID.test(videoId) ? videoId : null;
  } catch {
    return null;
  }
}

// Server-built fallback link; only YouTube's own results page is ever rendered as a link.
export const safeSearchUrl = value => (typeof value === 'string' && value.startsWith('https://www.youtube.com/results?') ? value : '');
export const isVideoId = value => VIDEO_ID.test(value);
export const embedUrl = videoId => 'https://www.youtube-nocookie.com/embed/' + videoId;

// Title and composer from MusicXML; the file name fills in what the score does not declare.
export function initialVideoQuery(title, composer, fileName = '') {
  const fileTitle = fileName.replace(/\.[^.]+$/, '').replace(/[-_]+/g, ' ').trim();
  const scoreTitle = title && title !== 'Untitled score' ? title : fileTitle;
  const titleWords = new Set(scoreTitle.toLowerCase().split(/\s+/));
  const fileDetails = fileTitle.split(/\s+/).filter(word => word && !titleWords.has(word.toLowerCase())).join(' ');
  return [scoreTitle, composer || fileDetails].filter(Boolean).join(' ').trim();
}
