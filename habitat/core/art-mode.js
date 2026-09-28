export const ART_MODES = Object.freeze(['lush', 'lush-live', 'lush-live-slice', 'slice-c', 'slice-b', 'slice-a', 'procedural']);
export const DEFAULT_ART_MODE = 'lush';

// The Windows host always navigates to index.html without a query, so the
// default is the mode under review (Slice C, the Natural Environment
// vocabulary); `?art=slice-b`, `?art=slice-a` and `?art=procedural` remain
// for comparison.
export function readArtMode(locationLike) {
  const requested = new URLSearchParams(locationLike?.search ?? '').get('art');
  return ART_MODES.includes(requested) ? requested : DEFAULT_ART_MODE;
}
