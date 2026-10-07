import React from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App.jsx';
import { createScoreSession } from './score/score-session.js';
import '@fontsource-variable/inter';
import './styles.css';
import { applyTextSize, loadTextSize } from './settings.js';

// The text size chosen on this device applies from the first paint.
applyTextSize(loadTextSize());

createRoot(document.getElementById('root')).render(<App session={createScoreSession()} />);
