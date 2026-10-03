import React from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App.jsx';
import { createScoreSession } from './score/score-session.js';
import './styles.css';

createRoot(document.getElementById('root')).render(<App session={createScoreSession()} />);
