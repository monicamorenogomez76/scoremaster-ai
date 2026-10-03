// Temporary adapter for the dashboard and notation pending their React migrations.
export function createWorkspaceBridge() {
  const loginScreen = document.getElementById('login-screen');
  const appShell = document.getElementById('app-shell');
  const sidebar = document.getElementById('sidebar');
  const pageTitle = document.getElementById('current-page-title');
  const viewTitles = {
    overview: 'Inicio',
    analyze: 'Analizar partitura',
    difficulty: 'Dificultad',
    band: 'Mi banda',
    rehearsal: 'Plan de ensayo',
    videos: 'Vídeos'
  };
  const bandProfileEditor = document.getElementById('band-profile-editor');
  const bandProfileRows = document.getElementById('band-profile-rows');
  const updateAnalysisButton = document.getElementById('update-analysis');
  const recalculateRehearsalButton = document.getElementById('recalculate-rehearsal');
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

  function showDemoWorkspace() {
    sessionStorage.setItem('scoremaster-demo-session', 'active');
    loginScreen.hidden = true;
    appShell.hidden = false;
    setActiveView('overview');
  }

  function showDemoLogin() {
    sessionStorage.removeItem('scoremaster-demo-session');
    appShell.hidden = true;
    loginScreen.hidden = false;
  }

  function setActiveView(viewName) {
    document.querySelectorAll('.app-view').forEach((view) => {
      view.classList.toggle('is-active', view.dataset.view === viewName);
    });
    document.querySelectorAll('.nav-item').forEach((item) => {
      if (item.dataset.viewTarget === viewName) item.setAttribute('aria-current', 'page');
      else item.removeAttribute('aria-current');
    });
    pageTitle.textContent = viewTitles[viewName] || viewTitles.overview;
    sidebar.classList.remove('is-open');
    document.getElementById('mobile-menu-button').setAttribute('aria-expanded', 'false');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  document.getElementById('enter-demo').addEventListener('click', showDemoWorkspace);
  document.getElementById('sign-out').addEventListener('click', showDemoLogin);
  document.querySelectorAll('.nav-item').forEach((item) => {
    item.addEventListener('click', () => setActiveView(item.dataset.viewTarget));
  });
  document.querySelectorAll('[data-open-view]').forEach((button) => {
    button.addEventListener('click', () => setActiveView(button.dataset.openView));
  });
  document.getElementById('open-priority').addEventListener('click', () => setActiveView('difficulty'));
  document.getElementById('mobile-menu-button').addEventListener('click', (event) => {
    const isOpen = sidebar.classList.toggle('is-open');
    event.currentTarget.setAttribute('aria-expanded', String(isOpen));
  });
  if (sessionStorage.getItem('scoremaster-demo-session') === 'active') showDemoWorkspace();
  const difficultyLabels = {
    low: 'Baja',
    moderate: 'Moderada',
    high: 'Alta',
    very_high: 'Muy alta'
  };
  const bandStatusLabels = {
    ok: 'Compatible',
    warning: 'Requiere revisar la plantilla',
    critical: 'Incompatibilidad importante'
  };
  const findingLabels = {
    SL003: 'Alta densidad rítmica',
    SL004: 'Intervalos amplios',
    SL002: 'Registro agudo',
    SL005: 'Pasaje prolongado sin descanso'
  };
  const familyLabelsEs = {
    woodwinds: 'Viento madera',
    brass: 'Viento metal',
    strings: 'Cuerda',
    percussion: 'Percusión',
    keyboard: 'Teclas',
    other: 'Otros'
  };
  const instrumentLabelsEs = {
    'Piccolo': 'Flautín', 'Flute': 'Flauta', 'Oboe': 'Oboe',
    'Clarinet': 'Clarinete', 'B♭ Clarinet': 'Clarinete en Si bemol',
    'Bb Clarinet': 'Clarinete en Si bemol', 'Alto Clarinet': 'Clarinete alto',
    'Bass Clarinet': 'Clarinete bajo', 'Bassoon': 'Fagot',
    'Alto Saxophone': 'Saxofón alto', 'Tenor Saxophone': 'Saxofón tenor',
    'Baritone Saxophone': 'Saxofón barítono', 'B♭ Trumpet': 'Trompeta en Si bemol',
    'Bb Trumpet': 'Trompeta en Si bemol', 'Horn in F': 'Trompa en Fa',
    'Trumpet': 'Trompeta', 'Trombone': 'Trombón', 'Euphonium': 'Bombardino',
    'Tuba': 'Tuba', 'Double Bass': 'Contrabajo', 'Timpani': 'Timbales',
    'Xylophone': 'Xilófono', 'Glockenspiel': 'Glockenspiel', 'Chimes': 'Campanas tubulares',
    'Concert Bass Drum': 'Bombo', 'Bass Drum': 'Bombo',
    'Concert Snare Drum': 'Caja', 'Snare Drum': 'Caja',
    'Crash Cymbal': 'Platos', 'Suspended Cymbal': 'Plato suspendido',
    'Tambourine': 'Pandereta', 'Triangle': 'Triángulo', 'Marimba': 'Marimba'
  };
  const bandProfileNames = {
    'Flautín': 'Piccolo', 'Flauta': 'Flute', 'Oboe': 'Oboe',
    'Clarinete': 'Clarinet', 'Clarinete en Si bemol': 'B♭ Clarinet',
    'Clarinete alto': 'Alto Clarinet', 'Clarinete bajo': 'Bass Clarinet',
    'Fagot': 'Bassoon', 'Saxofón alto': 'Alto Saxophone',
    'Saxofón tenor': 'Tenor Saxophone', 'Saxofón barítono': 'Baritone Saxophone',
    'Trompeta en Si bemol': 'B♭ Trumpet', 'Trompa en Fa': 'Horn in F',
    'Trombón': 'Trombone', 'Bombardino': 'Euphonium', 'Tuba': 'Tuba',
    'Contrabajo': 'Double Bass', 'Timbales': 'Timpani', 'Xilófono': 'Xylophone',
    'Glockenspiel': 'Glockenspiel', 'Campanas tubulares': 'Chimes',
    'Bombo': 'Concert Bass Drum', 'Caja': 'Concert Snare Drum',
    'Plato suspendido': 'Suspended Cymbal', 'Platos': 'Crash Cymbal',
    'Pandereta': 'Tambourine', 'Triángulo': 'Triangle', 'Marimba': 'Marimba'
  };
  const dimensionLabelsEs = {
    range: 'Tesitura', register: 'Registro extremo', intervals: 'Saltos',
    density: 'Densidad de ataques', endurance: 'Continuidad', tempo: 'Tempo'
  };
  const rehearsalReasons = {
    'High rhythmic density in the selected passage.': 'Alta densidad rítmica en este pasaje.',
    'Default rehearsal block.': 'Bloque general de ensayo.'
  };

  function displayInstrumentName(instrument, details = {}) {
    if (details.instrument_label_es) return details.instrument_label_es;
    const partMatch = instrument.match(/^(.*)\s+(\d+)$/);
    const baseName = partMatch ? partMatch[1] : instrument;
    const displayName = instrumentLabelsEs[baseName] || baseName;
    return partMatch ? displayName + ' ' + partMatch[2] : displayName;
  }

  function apiInstrumentName(instrument) {
    const partMatch = instrument.match(/^(.*)\s+(\d+)$/);
    const baseName = partMatch ? partMatch[1] : instrument;
    const apiName = bandProfileNames[baseName] || baseName;
    return partMatch ? apiName + ' ' + partMatch[2] : apiName;
  }

  function displayFamilyName(family, details = {}) {
    return details.label_es || familyLabelsEs[family] || family;
  }

  function appendText(parent, tagName, className, value) {
    const element = document.createElement(tagName);
    if (className) element.className = className;
    element.textContent = value;
    parent.append(element);
    return element;
  }

  function appendList(section, entries, emptyMessage) {
    const list = document.createElement('ul');
    list.className = 'result-list';
    if (entries.length === 0) {
      appendText(list, 'li', 'result-empty', emptyMessage);
    } else {
      entries.forEach((entry) => appendText(list, 'li', '', entry));
    }
    section.append(list);
  }

  function createSection(parent, title, wide = false) {
    const section = document.createElement('section');
    section.className = wide ? 'result-section result-section--wide' : 'result-section';
    appendText(section, 'h2', '', title);
    parent.append(section);
    return section;
  }

  function readBandProfile() {
    return Object.fromEntries(Array.from(bandProfileRows.querySelectorAll('input[data-instrument]')).map((input) => [
      apiInstrumentName(input.dataset.instrument),
      Math.max(0, Number.parseInt(input.value || '0', 10) || 0)
    ]));
  }

  function renderBandProfile(parts, previousProfile = {}) {
    bandProfileRows.replaceChildren();
    const instruments = Array.from(new Set(parts));
    instruments.forEach((instrument) => {
      const row = document.createElement('label');
      row.className = 'band-profile-row';
      appendText(row, 'span', '', displayInstrumentName(instrument));
      const count = document.createElement('input');
      count.type = 'number';
      count.min = '0';
      count.step = '1';
      count.value = String(previousProfile[apiInstrumentName(instrument)] ?? 1);
      count.dataset.instrument = instrument;
      count.setAttribute('aria-label', 'Músicos para ' + displayInstrumentName(instrument));
      row.append(count);
      bandProfileRows.append(row);
    });
    bandProfileEditor.hidden = instruments.length === 0;
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

  function renderDifficultyTree(section, difficulty, criticalPassages) {
    const familyEntries = Object.entries(difficulty.by_family || {});
    const instrumentEntries = difficulty.by_instrument || {};
    const shell = document.createElement('div');
    const navigation = document.createElement('nav');
    navigation.className = 'tree-nav';
    navigation.setAttribute('aria-label', 'Ruta de dificultad');
    const content = document.createElement('div');
    shell.append(navigation, content);
    section.append(shell);

    let selectedFamily = null;
    let selectedInstrument = null;

    function render() {
      navigation.replaceChildren();
      content.replaceChildren();

      const rootButton = document.createElement('button');
      rootButton.type = 'button';
      rootButton.textContent = 'Todas las familias';
      rootButton.setAttribute('aria-current', selectedFamily ? 'false' : 'page');
      rootButton.addEventListener('click', () => {
        selectedFamily = null;
        selectedInstrument = null;
        render();
      });
      navigation.append(rootButton);

      if (!selectedFamily) {
        const orderedFamilies = familyEntries.sort((left, right) =>
          (right[1].grade || 1) - (left[1].grade || 1) || right[1].score - left[1].score
        );
        if (orderedFamilies.length === 0) {
          appendText(content, 'p', 'result-empty', 'No se encontraron instrumentos en la partitura.');
          return;
        }
        const list = document.createElement('div');
        list.className = 'tree-node-list';
        orderedFamilies.forEach(([family, details]) => {
          const node = document.createElement('button');
          node.type = 'button';
          node.className = 'tree-node';
          const head = document.createElement('span');
          head.className = 'tree-node-head';
          appendText(head, 'span', '', displayFamilyName(family, details));
          appendText(head, 'strong', 'tree-grade', 'Grado ' + (details.grade || 1));
          const sub = document.createElement('span');
          sub.className = 'tree-node-support';
          appendText(sub, 'span', '', (details.instruments || []).length + ' instrumentos');
          appendText(sub, 'span', '', (criticalPassages.filter((passage) => passage.family === family).length) + ' pasajes');
          const bar = document.createElement('div');
          bar.className = 'family-bar';
          const fill = document.createElement('span');
          fill.style.width = Math.max(12, (details.grade || 1) * 20) + '%';
          bar.append(fill);
          node.append(head, bar, sub);
          node.addEventListener('click', () => {
            selectedFamily = family;
            selectedInstrument = null;
            render();
          });
          list.append(node);
        });
        content.append(list);
        return;
      }

      const familyDetails = difficulty.by_family[selectedFamily] || {};
      const familyButton = document.createElement('button');
      familyButton.type = 'button';
      familyButton.textContent = displayFamilyName(selectedFamily, familyDetails);
      familyButton.setAttribute('aria-current', selectedInstrument ? 'false' : 'page');
      familyButton.addEventListener('click', () => {
        selectedInstrument = null;
        render();
      });
      navigation.append(document.createTextNode('›'), familyButton);

      if (!selectedInstrument) {
        const instruments = (familyDetails.instruments || []).map((name) => [name, instrumentEntries[name] || {}]);
        instruments.sort((left, right) =>
          (right[1].grade || 1) - (left[1].grade || 1) || right[1].difficulty_score - left[1].difficulty_score
        );
        if (instruments.length === 0) {
          appendText(content, 'p', 'result-empty', 'No hay instrumentos clasificados en esta familia.');
          return;
        }
        const list = document.createElement('div');
        list.className = 'tree-node-list';
        instruments.forEach(([name, details]) => {
          const node = document.createElement('button');
          node.type = 'button';
          node.className = 'tree-node';
          const head = document.createElement('span');
          head.className = 'tree-node-head';
          appendText(head, 'span', '', displayInstrumentName(name, details));
          appendText(head, 'strong', 'tree-grade', 'Grado ' + (details.grade || 1));
          const count = criticalPassages.filter((passage) => passage.instrument === name).length;
          appendText(node, 'span', 'tree-node-support', count + (count === 1 ? ' pasaje crítico' : ' pasajes críticos'));
          node.prepend(head);
          node.addEventListener('click', () => {
            selectedInstrument = name;
            render();
          });
          list.append(node);
        });
        content.append(list);
        return;
      }

      const details = instrumentEntries[selectedInstrument] || {};
      appendText(navigation, 'span', '', '› ' + displayInstrumentName(selectedInstrument, details));
      appendText(content, 'h3', 'result-metric', displayInstrumentName(selectedInstrument, details));
      appendText(content, 'p', 'tree-grade tree-instrument-details', 'Grado ' + (details.grade || 1) + ' · índice ' + (details.difficulty_score ?? 0) + ' / 5');

      const dimensions = document.createElement('div');
      dimensions.className = 'tree-dimensions';
      Object.entries(details.dimensions || {}).forEach(([dimension, value]) => {
        const row = document.createElement('div');
        row.className = 'tree-dimension';
        appendText(row, 'span', '', dimensionLabelsEs[dimension] || dimension);
        const bar = document.createElement('div');
        bar.className = 'family-bar';
        const fill = document.createElement('span');
        fill.style.width = Math.max(0, Math.min(100, Number(value) * 20)) + '%';
        bar.append(fill);
        row.append(bar);
        appendText(row, 'strong', '', Number(value).toFixed(1));
        dimensions.append(row);
      });
      content.append(dimensions);

      appendText(content, 'h3', 'tree-passage-heading', 'Pasajes a revisar');
      const passages = criticalPassages.filter((passage) => passage.instrument === selectedInstrument);
      if (passages.length === 0) {
        appendText(content, 'p', 'result-empty', 'No se han detectado pasajes críticos para este instrumento.');
        return;
      }
      const passageList = document.createElement('ul');
      passageList.className = 'result-list';
      passages.forEach((passage) => {
        const item = document.createElement('li');
        appendText(item, 'strong', 'tree-passage-title', 'Compases ' + passage.measure_range);
        const actions = document.createElement('div');
        actions.className = 'passage-actions';
        (passage.findings || []).forEach((code) => {
          const tag = document.createElement('span');
          tag.className = 'pill';
          tag.textContent = findingLabels[code] || code;
          actions.append(tag);
        });
        const viewButton = document.createElement('button');
        viewButton.type = 'button';
        viewButton.className = 'passage-open';
        viewButton.textContent = 'Ver pasaje';
        viewButton.addEventListener('click', () => openNotationPassage(selectedInstrument, passage.measure_range));
        actions.append(viewButton);
        item.append(actions);
        passageList.append(item);
      });
      content.append(passageList);
    }

    render();
  }

  function renderAnalysis(data) {
    const difficulty = data.difficulty || {};
    const familyEntries = Object.entries(difficulty.by_family || {});
    const criticalPassages = difficulty.critical_passages || [];
    const overviewTitle = document.getElementById('overview-score-title');
    overviewTitle.textContent = data.title || 'Partitura sin título';
    document.getElementById('overview-composer').textContent = data.composer
      ? 'Compositor: ' + data.composer
      : 'Compositor no indicado en el MusicXML';
    document.getElementById('overview-empty').hidden = true;
    document.getElementById('overview-result').hidden = false;
    const overviewMetrics = document.getElementById('overview-metrics');
    overviewMetrics.replaceChildren();
    const dashboard = document.createElement('div');
    dashboard.className = 'dashboard-grid';

    const overallCard = document.createElement('div');
    overallCard.className = 'metric-card';
    appendText(overallCard, 'div', 'label', 'Grado de la obra');
    appendText(overallCard, 'div', 'value', 'Grado ' + (difficulty.grade || 1));
    appendText(overallCard, 'div', 'subvalue', 'Estimación provisional · percentil 80 por familia');
    dashboard.append(overallCard);

    const passagesCard = document.createElement('div');
    passagesCard.className = 'metric-card';
    appendText(passagesCard, 'div', 'label', 'Pasajes críticos');
    appendText(passagesCard, 'div', 'value', String(criticalPassages.length));
    appendText(passagesCard, 'div', 'subvalue', 'Agrupados por instrumento');
    dashboard.append(passagesCard);

    const familyCard = document.createElement('div');
    familyCard.className = 'metric-card';
    appendText(familyCard, 'div', 'label', 'Familias');
    appendText(familyCard, 'div', 'value', String(familyEntries.length));
    appendText(familyCard, 'div', 'subvalue', 'Secciones de la partitura');
    dashboard.append(familyCard);

    overviewMetrics.append(dashboard);
    if (familyEntries.length) {
      const chart = document.createElement('section'); chart.className = 'family-chart';
      chart.setAttribute('aria-label', 'Grado de dificultad por familia');
      appendText(chart, 'h2', '', 'Dónde concentrar el ensayo');
      appendText(chart, 'p', '', 'Grado de dificultad por familia · escala de 1 a 5');
      for (const [name, details] of familyEntries.slice().sort((a,b) => (b[1].grade || 1) - (a[1].grade || 1))) {
        const row = document.createElement('div'); row.className = 'chart-row';
        appendText(row, 'span', '', familyLabelsEs[name] || name);
        const track = document.createElement('div'); track.className = 'chart-track'; track.setAttribute('aria-hidden', 'true');
        const fill = document.createElement('div'); fill.className = 'chart-fill';
        const grade = Math.max(1, Math.min(5, Number(details.grade) || 1)); fill.style.width = grade / 5 * 100 + '%';
        track.append(fill); row.append(track); appendText(row, 'span', 'chart-value', 'Grado ' + grade);
        chart.append(row);
      }
      overviewMetrics.append(chart);
    }


    const priority = criticalPassages[0];
    const priorityBox = document.getElementById('overview-priority');
    priorityBox.hidden = !priority;
    if (priority) {
      const instrumentDetails = (difficulty.by_instrument || {})[priority.instrument] || {};
      document.getElementById('overview-priority-title').textContent =
        displayInstrumentName(priority.instrument, instrumentDetails) + ' · compases ' + priority.measure_range;
      const reasons = (priority.findings || []).map((code) => findingLabels[code] || code).join(' · ');
      document.getElementById('overview-priority-detail').textContent = reasons || 'Pasaje marcado para revisión.';
    }

    const difficultyContent = document.getElementById('difficulty-content');
    difficultyContent.replaceChildren();
    difficultyContent.classList.remove('empty-workspace');
    const explorerSection = createSection(difficultyContent, 'Dificultad por familias e instrumentos', true);
    renderDifficultyTree(explorerSection, difficulty, criticalPassages);

    const videosContent = document.getElementById('videos-content');
    videosContent.replaceChildren();
    videosContent.classList.remove('empty-workspace');
    const videoSection = createSection(videosContent, 'Vídeos relacionados con ' + (data.title || 'la obra'), true);
    renderYouTubeSearch(videoSection, data.title || '', data.composer || '');

    const bandFit = data.band_fit || {};
    const bandContent = document.getElementById('band-content');
    bandContent.replaceChildren();
    bandContent.classList.remove('empty-workspace');
    const bandSection = createSection(bandContent, 'Adaptación a la banda');
    appendText(
      bandSection,
      'p',
      'result-metric',
      String(bandFit.compatibility_percent ?? 0) + '%'
    );
    appendText(
      bandSection,
      'p',
      'result-supporting',
      bandStatusLabels[bandFit.status] || 'Estado no disponible'
    );
    const bandIssues = (bandFit.issues || []).map((issue) => {
      const instrument = displayInstrumentName(issue.instrument);
      if (issue.available === 0) {
        return instrument + ': falta en la plantilla; se necesita ' + issue.required + '.';
      }
      return instrument + ': hay ' + issue.available + ' músicos y se necesitan ' + issue.required + '.';
    });
    appendList(bandSection, bandIssues, 'La plantilla cubre los instrumentos requeridos.');

    const rehearsal = data.rehearsal_plan || {};
    const rehearsalContent = document.getElementById('rehearsal-content');
    rehearsalContent.replaceChildren();
    rehearsalContent.classList.remove('empty-workspace');
    const rehearsalSection = createSection(rehearsalContent, 'Bloques recomendados', true);
    appendText(
      rehearsalSection,
      'p',
      'result-supporting',
      'Duración total: ' + (rehearsal.total_minutes ?? 0) + ' minutos'
    );
    const segments = (rehearsal.segments || []).map((segment) => {
      const reason = rehearsalReasons[segment.reason] || segment.reason || 'Pasaje seleccionado para trabajar.';
      return displayInstrumentName(segment.instrument) + ' · compás ' + segment.measure_range + ' · ' + segment.minutes + ' min · ' + reason;
    });
    appendList(rehearsalSection, segments.slice(0, 10), 'No hay bloques de ensayo disponibles.');
    if (segments.length > 10) {
      appendText(rehearsalSection, 'p', 'result-supporting', (segments.length - 10) + ' bloques adicionales no mostrados.');
    }
  }

  let requestAnalysis = () => {};
  function analyzeFile(file, profile, navigate = true) { return requestAnalysis(file, profile, navigate); }

  async function resetScore() {
    selectionVersion++;
    currentScoreFile = null; notationSourcePromise = null;
    bandProfileRows.replaceChildren(); bandProfileEditor.hidden = true;
    for (const id of ['difficulty-content','band-content','rehearsal-content','videos-content']) {
      const target = document.getElementById(id);
      target.replaceChildren(); appendText(target, 'p', 'result-empty', 'Analiza una nueva partitura para ver los resultados.');
    }
    document.getElementById('overview-result').hidden = true;
    document.getElementById('overview-priority').hidden = true;
    document.getElementById('overview-empty').hidden = false;
    setActiveView('analyze');
    (await scoreViewPromise).clear(); await stopPassageAudio();
  }
  let selectionVersion = 0;

  updateAnalysisButton.addEventListener('click', () => analyzeFile(currentScoreFile, readBandProfile(), false));
  recalculateRehearsalButton.addEventListener('click', () => {
    if (!currentScoreFile) return setActiveView('analyze');
    return analyzeFile(currentScoreFile, readBandProfile(), false);
  });

  return {
    reset: resetScore,
    getFile: () => currentScoreFile,
    setFile(file, source = null) { currentScoreFile = file; notationSourcePromise = source ? Promise.resolve(source) : null; },
    loadSource: loadNotationSource,
    loadScore: () => scoreViewPromise.then(view => view.load()),
    readProfile: readBandProfile,
    apiInstrumentName,
    displayInstrumentName,
    getMinutes: () => document.getElementById('total-minutes').value || '60',
    setAnalysisHandler(handler) { requestAnalysis = handler; },
    async prepareAnalysis() { (await scoreViewPromise).clear(); await stopPassageAudio(); },
    showAnalysis(data, profile, navigate) {
      renderAnalysis(data); renderBandProfile(data.parts || [], profile); loadEmbeddedScore();
      if (navigate) setActiveView('analyze');
    },
    openPassage: openNotationPassage,
    getPassage: () => activeNotationPassage,
    filterPassage: filterMusicXmlPassage,
  };

}
