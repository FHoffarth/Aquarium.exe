export const ART_MODES = Object.freeze(['slice-a', 'procedural']);
export const DEFAULT_ART_MODE = 'slice-a';

// The Windows host always navigates to index.html without a query, so the
// default is the mode under review; `?art=procedural` is the A/B baseline.
export function readArtMode(locationLike) {
  const requested = new URLSearchParams(locationLike?.search ?? '').get('art');
  return ART_MODES.includes(requested) ? requested : DEFAULT_ART_MODE;
}
