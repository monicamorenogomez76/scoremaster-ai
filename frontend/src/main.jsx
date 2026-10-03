import React from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App.jsx';
import { createWorkspaceBridge } from './legacy-workspace.js';
import './styles.css';

const workspace = createWorkspaceBridge();
// Shared adapter for the score viewers and video search until their React migration.
window.scoremasterWorkspace = workspace;
createRoot(document.getElementById('root')).render(<App workspace={workspace} />);
