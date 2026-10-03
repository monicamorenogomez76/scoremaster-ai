// OpenSheetMusicDisplay is loaded by index.html; a missing engine is reported, not thrown silently.
export function openSheetMusicDisplay(target, options) {
  const Display = window.opensheetmusicdisplay?.OpenSheetMusicDisplay;
  if (!Display) throw new Error('El motor de notación no está disponible. Comprueba la conexión a Internet.');
  return new Display(target, options);
}

export const nextFrame = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));

export async function toggleFullscreen(element) {
  if (document.fullscreenElement) await document.exitFullscreen();
  else await element.requestFullscreen();
}
