import React from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App.jsx';
import { createScoreSession } from './score/score-session.js';
import '@fontsource-variable/bricolage-grotesque';
import '@fontsource-variable/outfit';
import './styles.css';
import { applyTextSize, applyTheme, loadTextSize, loadTheme } from './settings.js';
import { applyLanguage, loadLanguage } from './i18n.js';

// The language, text size and theme chosen on this device apply from the first paint.
applyLanguage(loadLanguage());
applyTextSize(loadTextSize());
applyTheme(loadTheme());

createRoot(document.getElementById('root')).render(<App session={createScoreSession()} />);
