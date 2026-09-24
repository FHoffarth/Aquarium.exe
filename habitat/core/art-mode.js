export const ART_MODES = Object.freeze(['slice-b', 'slice-a', 'procedural']);
export const DEFAULT_ART_MODE = 'slice-b';

// The Windows host always navigates to index.html without a query, so the
// default is the mode under review (Slice B, the Hero Frame translation);
// `?art=slice-a` and `?art=procedural` remain for comparison.
export function readArtMode(locationLike) {
  const requested = new URLSearchParams(locationLike?.search ?? '').get('art');
  return ART_MODES.includes(requested) ? requested : DEFAULT_ART_MODE;
}
