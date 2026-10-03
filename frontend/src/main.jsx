import React from 'react';
import { createRoot } from 'react-dom/client';
import { UploadWorkspace } from './UploadWorkspace.jsx';
import { createWorkspaceBridge } from './legacy-workspace.js';
import './styles.css';

const workspace = createWorkspaceBridge();
// Shared adapter during the incremental migration; removed with the remaining views.
window.scoremasterWorkspace = workspace;
createRoot(document.getElementById('upload-root')).render(<UploadWorkspace workspace={workspace} />);
