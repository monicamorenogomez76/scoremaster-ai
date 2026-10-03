import { displayInstrumentName } from './labels.js';

// Temporary adapter for the score viewers, passage audio and video search pending their React migration.
export function createWorkspaceBridge() {
  let currentScoreFile = null;
  let notationSourcePromise = null;
  let activeNotationPassage = null;
  const audioModule = import(/* @vite-ignore */ '/static/playback.js?v=5');
  const guideModule = import(/* @vite-ignore */ '/static/playback-guide.js');
  const scoreViewPromise = import(/* @vite-ignore */ '/static/score-view.js?v=5').then(({ createScoreView }) =>
    createScoreView({ getSource: loadNotationSource, getFile: () => currentScoreFile, filter: filterMusicXmlPassage }));
  function loadEmbeddedScore() {
    const file = currentScoreFile, version = selectionVersion;
    scoreViewPromise.then((view) => { if (file && file === currentScoreFile && version === selectionVersion) return view.load(); }).catch(() => {
      const status = document.getElementById('full-score-status');
      status.textContent = 'No se pudo cargar el visor. Puedes volver a intentarlo recargando la página.';
      status.setAttribute('aria-busy', 'false');
    });
  }
  const audioStatus = document.getElementById('playback-status');
  let passageLoadVersion = 0;
  const passageSeek = document.getElementById('passage-seek');
  const passageClock = seconds => Math.floor(seconds / 60) + ':' + String(Math.floor(seconds % 60)).padStart(2, '0');
  function setPassagePlayIcon(playing) {
    const button = document.getElementById('passage-play');
    if (button.getAttribute('aria-label') === (playing ? 'Pausar' : 'Reproducir')) return;
    button.innerHTML = playing ? '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 5h4v14H7zm6 0h4v14h-4z"/></svg>' : '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 4v16l13-8z"/></svg>';
    button.setAttribute('aria-label', playing ? 'Pausar' : 'Reproducir');
    button.title = playing ? 'Pausar' : 'Reproducir';
  }
  async function stopPassageAudio() {
    passageLoadVersion++;
    (await audioModule).stopPlayback();
    document.getElementById('passage-play').disabled = false;
    audioStatus.setAttribute('aria-busy', 'false');
    audioStatus.textContent = '';
    document.getElementById('passage-position').textContent = '';
    activeNotationPassage?.renderer?.cursor?.hide();
    if (activeNotationPassage) { activeNotationPassage.transport = null; activeNotationPassage.playing = false; activeNotationPassage.currentMeasure = undefined; }
    setPassagePlayIcon(false);
    passageSeek.disabled = true; passageSeek.value = 0;
    document.getElementById('passage-time').textContent = '0:00 / 0:00';
  }
  document.getElementById('passage-play').addEventListener('click', async () => {
    if (!currentScoreFile || !activeNotationPassage) return;
    if (activeNotationPassage.transport) {
      if (activeNotationPassage.playing) activeNotationPassage.transport.pause();
      else await activeNotationPassage.transport.play();
      return;
    }
    const version = ++passageLoadVersion;
    const button = document.getElementById('passage-play');
    button.disabled = true; audioStatus.setAttribute('aria-busy', 'true');
    audioStatus.textContent = 'Cargando sonidos del pasaje…';
    try {
      const passage = activeNotationPassage;
      const transport = await (await audioModule).preparePlayback(currentScoreFile, passage,
        (message) => { if (version === passageLoadVersion) { audioStatus.textContent = message; audioStatus.setAttribute('aria-busy', String(/Preparando|Cargando/.test(message))); } });
      if (!transport || version !== passageLoadVersion) return;
      passage.transport = transport;
      transport.setSpeed(Number(document.getElementById('passage-speed').value));
      transport.setVolume(Number(document.getElementById('passage-volume').value) / 100);
      passageSeek.max = transport.duration; passageSeek.disabled = false;
      const { highlightMeasure } = await guideModule;
      let lastMeasure;
      transport.subscribe(state => {
        if (version !== passageLoadVersion) return;
        passage.playing = state.playing; setPassagePlayIcon(state.playing);
        passageSeek.value = state.position;
        document.getElementById('passage-time').textContent = passageClock(state.position) + ' / ' + passageClock(state.duration);
        if (state.currentMeasure === lastMeasure) return;
        lastMeasure = state.currentMeasure; passage.currentMeasure = state.currentMeasure;
        document.getElementById('passage-position').textContent = 'Compás ' + state.currentMeasure + ' de ' + passage.firstMeasure + '–' + passage.lastMeasure;
        highlightMeasure(passage.renderer, state.currentMeasure, document.getElementById('notation-score'));
      });
      await transport.play();
    } catch (error) {
      if (version !== passageLoadVersion) return;
      audioStatus.textContent = error.message || 'No se pudo cargar el sonido. Comprueba la conexión a Internet.';
    } finally {
      if (version === passageLoadVersion) { button.disabled = false; audioStatus.setAttribute('aria-busy', 'false'); }
    }
  });
  document.getElementById('passage-stop').addEventListener('click', stopPassageAudio);
  passageSeek.addEventListener('change', () => activeNotationPassage?.transport?.seek(Number(passageSeek.value)));
  document.getElementById('passage-speed').addEventListener('change', event => activeNotationPassage?.transport?.setSpeed(Number(event.target.value)));
  document.getElementById('passage-volume').addEventListener('input', event => activeNotationPassage?.transport?.setVolume(Number(event.target.value) / 100));
  document.getElementById('passage-fullscreen').addEventListener('click', async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.getElementById('passage-view').requestFullscreen();
      await renderNotationPage();
    } catch (_) { audioStatus.textContent = 'La pantalla completa no está disponible en este navegador.'; }
  });
  document.getElementById('notation-fit').addEventListener('click', () => {
    if (activeNotationPassage) { activeNotationPassage.zoom = 1; renderNotationPage(); }
  });
  document.getElementById('notation-dialog').addEventListener('close', async () => {
    await stopPassageAudio();
    if (document.fullscreenElement === document.getElementById('passage-view')) await document.exitFullscreen();
  });

  function appendText(parent, tagName, className, value) {
    const element = document.createElement(tagName);
    if (className) element.className = className;
    element.textContent = value;
    parent.append(element);
    return element;
  }

  function parseMeasureRange(value) {
    const values = String(value).split('-').map((part) => Number.parseInt(part, 10));
    if (!values.length || values.some((number) => !Number.isFinite(number))) {
      throw new Error('El rango de compases del pasaje no es válido.');
    }
    return [values[0], values[1] || values[0]];
  }

  function filterMusicXmlPassage(source, instrumentName, measureRange) {
    const [firstMeasure, lastMeasure] = parseMeasureRange(measureRange);
    const partMatch = instrumentName && instrumentName.match(/^(.*)\s+(\d+)$/);
    const sourceInstrumentName = partMatch ? partMatch[1] : instrumentName;
    let selectedStaffNumber = partMatch ? Number(partMatch[2]) : null;
    const documentXml = new DOMParser().parseFromString(source, 'application/xml');
    if (documentXml.querySelector('parsererror')) {
      throw new Error('No se pudo interpretar el MusicXML original.');
    }
    const descendants = (parent, name) => Array.from(parent.getElementsByTagName('*'))
      .filter((element) => element.localName === name);
    const directChild = (parent, name) => Array.from(parent.children)
      .find((element) => element.localName === name);
    const scoreParts = descendants(documentXml, 'score-part');
    const matchingParts = instrumentName === null ? scoreParts : scoreParts.filter((part) => {
      const name = directChild(part, 'part-name');
      return name && name.textContent.trim() === sourceInstrumentName;
    });
    if (matchingParts.length > 1 && selectedStaffNumber) {
      const selectedPart = matchingParts[selectedStaffNumber - 1];
      matchingParts.forEach((part) => {
        if (part !== selectedPart) part.parentNode.removeChild(part);
      });
      selectedStaffNumber = null;
    }
    const selectedIds = new Set(matchingParts.map((part) => part.getAttribute('id')));
    if (selectedIds.size === 0) {
      throw new Error('No se encontró el instrumento dentro del MusicXML.');
    }

    scoreParts.forEach((part) => {
      if (!selectedIds.has(part.getAttribute('id'))) part.parentNode.removeChild(part);
    });
    const scorePartsData = descendants(documentXml, 'part');
    let retainedMeasures = 0;
    scorePartsData.forEach((part) => {
      if (!selectedIds.has(part.getAttribute('id'))) {
        part.parentNode.removeChild(part);
        return;
      }
      const scorePartName = scoreParts.find((entry) => entry.getAttribute('id') === part.getAttribute('id'));
      const nameElement = scorePartName && directChild(scorePartName, 'part-name');
      if (nameElement && instrumentName !== null) nameElement.textContent = instrumentName;
      let previousAttributes = null;
      let firstRetained = true;
      Array.from(part.children).filter((element) => element.localName === 'measure').forEach((measure) => {
        const measureNumber = Number.parseInt(measure.getAttribute('number'), 10);
        const attributes = directChild(measure, 'attributes');
        if (attributes) {
          if (!previousAttributes) previousAttributes = attributes.cloneNode(true);
          else Array.from(attributes.children).forEach((element) => {
            const inherited = Array.from(previousAttributes.children).find((candidate) =>
              candidate.localName === element.localName &&
              candidate.getAttribute('number') === element.getAttribute('number'));
            if (inherited) previousAttributes.replaceChild(element.cloneNode(true), inherited);
            else previousAttributes.append(element.cloneNode(true));
          });
        }
        if (measureNumber < firstMeasure || measureNumber > lastMeasure) {
          part.removeChild(measure);
          return;
        }
        if (firstRetained && previousAttributes) {
          const print = directChild(measure, 'print');
          if (attributes) measure.replaceChild(previousAttributes.cloneNode(true), attributes);
          else measure.insertBefore(previousAttributes.cloneNode(true), print ? print.nextSibling : measure.firstChild);
        }
        if (selectedStaffNumber) {
          const currentAttributes = directChild(measure, 'attributes');
          if (currentAttributes) {
            Array.from(currentAttributes.children).forEach((element) => {
              if (element.localName === 'staves') element.textContent = '1';
              if (['clef', 'staff-details', 'key', 'transpose'].includes(element.localName) && element.hasAttribute('number')) {
                if (Number(element.getAttribute('number')) !== selectedStaffNumber) {
                  currentAttributes.removeChild(element);
                } else {
                  element.setAttribute('number', '1');
                }
              }
            });
          }
          Array.from(measure.children).forEach((element) => {
            if (!['note', 'direction'].includes(element.localName)) return;
            const staff = directChild(element, 'staff');
            const eventStaff = Number(staff ? staff.textContent : '1');
            if (eventStaff !== selectedStaffNumber) {
              measure.removeChild(element);
            } else if (staff) {
              staff.textContent = '1';
            }
          });
        }
        firstRetained = false;
        retainedMeasures += 1;
      });
    });
    if (retainedMeasures === 0) {
      throw new Error('El rango solicitado no contiene compases renderizables.');
    }
    return new XMLSerializer().serializeToString(documentXml);
  }

  async function loadNotationSource() {
    if (!currentScoreFile) throw new Error('Vuelve a subir la partitura para abrir este pasaje.');
    if (!notationSourcePromise) {
      const payload = new FormData();
      payload.append('file', currentScoreFile);
      notationSourcePromise = fetch('/notation-source', { method: 'POST', body: payload })
        .then(async (response) => {
          if (!response.ok) throw new Error('No se pudo recuperar la partitura original.');
          return response.text();
        });
    }
    return notationSourcePromise;
  }

  async function openNotationPassage(instrument, measureRange) {
    (await scoreViewPromise).stop();
    await stopPassageAudio();
    document.getElementById('passage-play').hidden = false;
    document.getElementById('passage-stop').hidden = false;
    const dialog = document.getElementById('notation-dialog');
    const [firstMeasure, lastMeasure] = parseMeasureRange(measureRange);
    activeNotationPassage = { instrument, firstMeasure, lastMeasure, pageStart: firstMeasure, zoom: 1 };
    document.getElementById('notation-title').textContent = displayInstrumentName(instrument) + ' · compases ' + measureRange;
    if (!dialog.open) dialog.showModal();
    try {
      activeNotationPassage.source = await loadNotationSource();
      await renderNotationPage();
    } catch (error) {
      document.getElementById('notation-status').textContent = error.message || 'No se pudo representar este pasaje.';
    }
  }

  async function renderNotationPage() {
    const state = activeNotationPassage;
    const status = document.getElementById('notation-status');
    const container = document.getElementById('notation-score');
    const endMeasure = state.lastMeasure;
    const pageLabel = document.getElementById('notation-page-label');
    const previousButton = document.getElementById('notation-prev');
    const nextButton = document.getElementById('notation-next');
    previousButton.hidden = true;
    nextButton.hidden = true;
    pageLabel.textContent = 'Pasaje completo · compases ' + state.firstMeasure + '–' + endMeasure + ' · ' + (endMeasure - state.firstMeasure + 1) + ' compases · desplázate para revisarlos';
    status.textContent = 'Cargando el pasaje completo…';
    await new Promise(resolve => requestAnimationFrame(() => setTimeout(resolve, 0)));
    if (state !== activeNotationPassage || !document.getElementById('notation-dialog').open) return;
    container.replaceChildren();

    const display = window.opensheetmusicdisplay;
    if (!display || !display.OpenSheetMusicDisplay) {
      throw new Error('El motor de notación no está disponible. Comprueba la conexión a Internet.');
    }
    const passageXml = filterMusicXmlPassage(
      state.source,
      state.instrument,
      state.pageStart + '-' + endMeasure
    );
    const renderer = new display.OpenSheetMusicDisplay(container, {
      autoResize: true,
      backend: 'svg',
      drawTitle: false,
      drawPartNames: true,
      drawMeasureNumbers: true,
      cursorsOptions: [{ type: 3, color: '#6366f1', alpha: .25, follow: false }]
    });
    await renderer.load(passageXml);
    if (state !== activeNotationPassage || !document.getElementById('notation-dialog').open) return;
    renderer.render();
    state.renderer = renderer;
    const svg = container.querySelector('svg');
    if (svg) {
      svg.style.width = (state.zoom * 100) + '%';
      svg.style.maxWidth = 'none';
      renderer.playbackScale = svg.getBoundingClientRect().width / Number.parseFloat(svg.getAttribute('width'));
    }
    document.getElementById('notation-zoom-label').textContent = Math.round(state.zoom * 100) + '%';
    container.scrollTop = 0;
    container.scrollLeft = 0;
    if (state.currentMeasure !== undefined && state.transport) {
      (await guideModule).highlightMeasure(renderer, state.currentMeasure, container);
    }
    status.textContent = 'Notación original · tonalidad escrita del MusicXML · ' +
      (state.instrument === null ? 'Todas las voces' : displayInstrumentName(state.instrument)) + ' · audio en sonido real (instrumentos transpositores)';
  }

  document.getElementById('notation-zoom-out').addEventListener('click', () => {
    if (!activeNotationPassage) return;
    activeNotationPassage.zoom = Math.max(0.75, activeNotationPassage.zoom - 0.1);
    renderNotationPage().catch((error) => {
      document.getElementById('notation-status').textContent = error.message;
    });
  });
  document.getElementById('notation-zoom-in').addEventListener('click', () => {
    if (!activeNotationPassage) return;
    activeNotationPassage.zoom = Math.min(1.5, activeNotationPassage.zoom + 0.1);
    renderNotationPage().catch((error) => {
      document.getElementById('notation-status').textContent = error.message;
    });
  });
  document.getElementById('notation-close').addEventListener('click', () => {
    document.getElementById('notation-dialog').close();
  });

  function renderYouTubePlayer(container, videoId) {
    if (!/^[A-Za-z0-9_-]{11}$/.test(videoId)) return false;
    const frame = document.createElement('iframe');
    frame.src = 'https://www.youtube-nocookie.com/embed/' + videoId;
    frame.title = 'Vídeo de YouTube seleccionado';
    frame.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';
    frame.allowFullscreen = true;
    frame.loading = 'lazy';
    frame.referrerPolicy = 'strict-origin-when-cross-origin';
    container.replaceChildren(frame);
    return true;
  }

  function parseYouTubeVideoId(value) {
    try {
      const url = new URL(value.trim());
      const host = url.hostname.toLowerCase();
      let videoId = '';
      if (host === 'youtu.be') videoId = url.pathname.slice(1).split('/')[0];
      if (['youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com'].includes(host)) {
        if (url.pathname === '/watch') videoId = url.searchParams.get('v') || '';
        else videoId = url.pathname.match(/^\/(?:embed|shorts)\/([A-Za-z0-9_-]{11})/)?.[1] || '';
      }
      return /^[A-Za-z0-9_-]{11}$/.test(videoId) ? videoId : null;
    } catch (_error) {
      return null;
    }
  }

  async function renderYouTubeSearch(section, title, composer) {
    const fileTitle = currentScoreFile
      ? currentScoreFile.name.replace(/\.[^.]+$/, '').replace(/[-_]+/g, ' ').trim()
      : '';
    const scoreTitle = title && title !== 'Untitled score' ? title : fileTitle;
    const titleWords = new Set(scoreTitle.toLowerCase().split(/\s+/));
    const filenameDetails = fileTitle
      .split(/\s+/)
      .filter((word) => word && !titleWords.has(word.toLowerCase()))
      .join(' ');
    const queryTerms = [scoreTitle, composer || filenameDetails];
    const initialQuery = queryTerms.filter(Boolean).join(' ').trim();
    const searchForm = document.createElement('form');
    searchForm.className = 'video-search-form';
    const searchInput = document.createElement('input');
    searchInput.type = 'search';
    searchInput.maxLength = 200;
    searchInput.value = initialQuery;
    searchInput.placeholder = 'Buscar otra versión u obra';
    searchInput.setAttribute('aria-label', 'Buscar vídeos por obra o compositor');
    const searchButton = document.createElement('button');
    searchButton.type = 'submit';
    searchButton.textContent = 'Buscar';
    searchForm.append(searchInput, searchButton);
    section.append(searchForm);

    const status = appendText(section, 'p', 'result-supporting', 'Buscando coincidencias…');
    const selectedTitle = appendText(section, 'h3', 'video-selected-title', '');
    const player = document.createElement('div');
    player.className = 'video-player';
    player.hidden = true;
    section.append(player);
    const results = document.createElement('div');
    results.className = 'video-results';
    section.append(results);
    const fallback = document.createElement('div');
    fallback.className = 'video-search-fallback';
    section.append(fallback);

    function selectVideo(video, buttons) {
      player.hidden = false;
      renderYouTubePlayer(player, video.video_id);
      selectedTitle.textContent = video.title;
      buttons.forEach((button) => {
        const selected = button.dataset.videoId === video.video_id;
        button.classList.toggle('is-selected', selected);
        button.setAttribute('aria-pressed', String(selected));
      });
    }

    async function search(query) {
      const normalizedQuery = query.trim().slice(0, 200);
      if (!normalizedQuery) return;
      searchInput.value = normalizedQuery;
      status.textContent = 'Buscando “' + normalizedQuery + '”…';
      selectedTitle.textContent = '';
      player.hidden = true;
      player.replaceChildren();
      results.replaceChildren();
      fallback.replaceChildren();

      try {
        const response = await fetch('/youtube/search?query=' + encodeURIComponent(normalizedQuery));
        if (!response.ok) throw new Error('No se pudo completar la búsqueda de YouTube.');
        const result = await response.json();
        if (result.videos.length) {
          status.textContent = 'Reproduciendo la mejor coincidencia. Elige otra versión para cambiarla.';
          const buttons = result.videos.map((video) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'video-result';
            button.dataset.videoId = video.video_id;
            button.setAttribute('aria-pressed', 'false');
            const thumbnail = document.createElement('img');
            thumbnail.src = video.thumbnail;
            thumbnail.alt = '';
            thumbnail.loading = 'lazy';
            const copy = document.createElement('span');
            copy.className = 'video-result-copy';
            appendText(copy, 'strong', '', video.title);
            appendText(copy, 'span', '', video.channel);
            button.append(thumbnail, copy);
            button.addEventListener('click', () => selectVideo(video, buttons));
            results.append(button);
            return button;
          });
          selectVideo(result.videos[0], buttons);
        } else {
          status.textContent = 'No hay coincidencias integradas. Busca en YouTube o pega aquí un enlace.';
          const link = document.createElement('a');
          link.className = 'video-search-link';
          link.href = result.search_url;
          link.target = '_blank';
          link.rel = 'noopener noreferrer';
          link.textContent = 'Abrir búsqueda de “' + normalizedQuery + '” en YouTube';
          fallback.append(link, manual);
        }
      } catch (error) {
        status.textContent = error.message || 'Búsqueda de vídeo no disponible.';
      }
    }

    searchForm.addEventListener('submit', (event) => {
      event.preventDefault();
      search(searchInput.value);
    });

    const manual = document.createElement('div');
    manual.className = 'video-manual';
    const manualInput = document.createElement('input');
    manualInput.type = 'url';
    manualInput.placeholder = 'Pega aquí un enlace de YouTube para reproducirlo';
    manualInput.setAttribute('aria-label', 'Enlace de vídeo de YouTube');
    const manualButton = document.createElement('button');
    manualButton.type = 'button';
    manualButton.className = 'video-load';
    manualButton.textContent = 'Reproducir enlace';
    manualButton.addEventListener('click', () => {
      const videoId = parseYouTubeVideoId(manualInput.value);
      if (!videoId) {
        manualInput.setCustomValidity('Introduce un enlace válido de YouTube.');
        manualInput.reportValidity();
        return;
      }
      manualInput.setCustomValidity('');
      player.hidden = false;
      renderYouTubePlayer(player, videoId);
      selectedTitle.textContent = 'Vídeo elegido manualmente';
    });
    manual.append(manualInput, manualButton);
    fallback.append(manual);
    search(initialQuery);
  }

  async function resetScore() {
    selectionVersion++;
    currentScoreFile = null; notationSourcePromise = null;
    (await scoreViewPromise).clear(); await stopPassageAudio();
  }
  let selectionVersion = 0;

  return {
    reset: resetScore,
    getFile: () => currentScoreFile,
    setFile(file, source = null) { currentScoreFile = file; notationSourcePromise = source ? Promise.resolve(source) : null; },
    loadSource: loadNotationSource,
    loadScore: () => scoreViewPromise.then(view => view.load()),
    async prepareAnalysis() { (await scoreViewPromise).clear(); await stopPassageAudio(); },
    showScore: loadEmbeddedScore,
    renderVideos: renderYouTubeSearch,
    openPassage: openNotationPassage,
    getPassage: () => activeNotationPassage,
    filterPassage: filterMusicXmlPassage,
  };

}
