import React, { useCallback, useEffect, useRef, useState } from 'react';
import { apiFetch } from '../api.js';
import { MAX_QUERY, embedUrl, initialVideoQuery, isVideoId, parseYouTubeVideoId, safeSearchUrl, searchStatus } from './youtube.js';

// Searches through the server (the YouTube key never reaches the browser) and embeds the
// privacy-enhanced player. Without results, a manual link can be played instead.
export function VideoSearch({ title, composer, fileName }) {
  const [query, setQuery] = useState(() => initialVideoQuery(title, composer, fileName));
  const [search, setSearch] = useState({ status: 'Buscando coincidencias…', videos: [], searchUrl: '', searched: '' });
  const [selected, setSelected] = useState(null);
  const [link, setLink] = useState('');
  const manual = useRef(null), request = useRef(0);

  const run = useCallback(async value => {
    const normalized = value.trim().slice(0, MAX_QUERY);
    if (!normalized) return;
    const token = ++request.current;
    setQuery(normalized); setSelected(null);
    setSearch({ status: 'Buscando “' + normalized + '”…', videos: [], searchUrl: '', searched: normalized });
    try {
      const response = await apiFetch('/youtube/search?query=' + encodeURIComponent(normalized));
      if (!response.ok) throw new Error('No se pudo completar la búsqueda de YouTube.');
      const result = await response.json();
      if (token !== request.current) return;
      const videos = (result.videos || []).filter(video => isVideoId(video.video_id));
      setSearch({ status: searchStatus(result, videos.length), videos, searchUrl: safeSearchUrl(result.search_url), searched: normalized });
      if (videos.length) setSelected({ id: videos[0].video_id, title: videos[0].title });
    } catch (error) {
      if (token === request.current) setSearch(previous => ({ ...previous, status: error.message || 'Búsqueda de vídeo no disponible.' }));
    }
  }, []);

  useEffect(() => {
    run(initialVideoQuery(title, composer, fileName));
    return () => { request.current++; };
  }, [run, title, composer, fileName]);

  const playLink = () => {
    const videoId = parseYouTubeVideoId(link);
    manual.current.setCustomValidity(videoId ? '' : 'Introduce un enlace válido de YouTube.');
    if (!videoId) { manual.current.reportValidity(); return; }
    setSelected({ id: videoId, title: 'Vídeo elegido manualmente' });
  };

  return <>
    <form className="video-search-form" onSubmit={event => { event.preventDefault(); run(query); }}>
      <input type="search" maxLength={MAX_QUERY} value={query} placeholder="Buscar otra versión u obra"
        aria-label="Buscar vídeos por obra o compositor" onChange={event => setQuery(event.target.value)} />
      <button type="submit">Buscar</button>
    </form>
    <p className="result-supporting" role="status">{search.status}</p>
    <h3 className="video-selected-title">{selected?.title || ''}</h3>
    {selected && <div className="video-player">
      <iframe key={selected.id} src={embedUrl(selected.id)} title="Vídeo de YouTube seleccionado" loading="lazy"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        allowFullScreen referrerPolicy="strict-origin-when-cross-origin" />
    </div>}
    <div className="video-results">{search.videos.map(video => {
      const active = selected?.id === video.video_id;
      return <button key={video.video_id} type="button" className={'video-result' + (active ? ' is-selected' : '')} aria-pressed={active}
        onClick={() => setSelected({ id: video.video_id, title: video.title })}>
        <img src={video.thumbnail} alt="" loading="lazy" />
        <span className="video-result-copy"><strong>{video.title}</strong><span>{video.channel}</span></span>
      </button>;
    })}</div>
    <div className="video-search-fallback">
      {search.searchUrl && search.videos.length === 0 && <a className="video-search-link" href={search.searchUrl} target="_blank" rel="noopener noreferrer">
        Abrir búsqueda de “{search.searched}” en YouTube</a>}
      <div className="video-manual">
        <input ref={manual} type="url" value={link} placeholder="Pega aquí un enlace de YouTube para reproducirlo"
          aria-label="Enlace de vídeo de YouTube" onChange={event => { setLink(event.target.value); event.target.setCustomValidity(''); }} />
        <button type="button" className="video-load" onClick={playLink}>Reproducir enlace</button>
      </div>
    </div>
  </>;
}
