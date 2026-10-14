import React from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App.jsx';
import { createScoreSession } from './score/score-session.js';
import '@fontsource-variable/inter';
import './styles.css';
import { applyTextSize, applyTheme, loadTextSize, loadTheme } from './settings.js';

// The text size and the theme chosen on this device apply from the first paint.
applyTextSize(loadTextSize());
applyTheme(loadTheme());

createRoot(document.getElementById('root')).render(<App session={createScoreSession()} />);
