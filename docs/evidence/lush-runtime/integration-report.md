# Approved lush aquarium runtime integration

Base: `6dfd62d` on `codex/bright-freshwater-reference`.

The approved 1920 × 1080 Blender view was rendered without the posed review fish or still-frame particles, then stored as a lossless WebP environment plate. Its decoded pixels match the source render exactly. The existing live instanced Hero Fish school runs in front of it, with restrained freshwater color groups. The runtime also adds 22 faint, slowly drifting points and a 0.6% broad light variation. No external assets or dependencies were added.

## Evidence

- `desktop-frame.png`: actual 1920 × 1080 Windows desktop and wallpaper host.
- `desktop-45s.mp4`: actual desktop recording, 44.9667 seconds, 1920 × 1080.
- `video-contact-sheet.jpg`: samples at approximately 3, 15, 30, and 43 seconds.

The capture contains 906 recorded frames (20.15 FPS average capture cadence). The host's WebView reported 58.6–60.0 FPS in nine five-second samples during the capture, averaging 59.78 FPS; the recorder's cadence is distinct from the application's FPS. The host reported five draw calls, 47,962 triangles, and ten fish. The fish move and remain readable; visual inspection of the capture found no obvious particle storm, heavy fog, caustic loop, or swimming-pool lighting.

## Verification

- `build.ps1 -Target All`: passed, including habitat tests, native fish logic, host policy, WebView2 probe, and Windows host build.
- `git diff --check`: passed.
- Pause probe: `paused=true` in the host log. The existing engine cancels its scheduled animation frame on pause and resumes it afterward; the probe's FPS field is the last measured value, not a paused rendering rate.

## Limitation

The approved planted environment is a static plate at its approved camera. It retains the exact approved vegetation, substrate, wood, and lighting appearance at 1920 × 1080, but the plants have no 3D parallax or animated tips. The fish and restrained water effects remain live. This avoids changing the approved composition and keeps the runtime within its measured frame budget.
