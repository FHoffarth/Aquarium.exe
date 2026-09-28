# Underwater depth and background integration

Base: `1a8e2dd` on `codex/bright-freshwater-reference`. This is a bounded grade of the approved environment plate. The geometry, vegetation layout, substrate, wood, camera, lighting, fish, particles, and runtime render architecture remain unchanged.

The saved Blender scene supplies a half-resolution camera depth map and a mask for its existing blue water background. A reproducible offline grade leaves near pixels unchanged, blends distant vegetation by at most 8.5% toward dim water to reduce contrast and saturation, and darkens only the background by roughly 9–15% with very broad variation of a few RGB levels. The result is lossless WebP at the existing 1920 × 1080 texture size. No new runtime draw call, asset, or dependency was added.

## Real desktop comparison

- `desktop-before-after.png`: earlier approved runtime on the left, this candidate on the right. Fish positions differ because both frames are live captures.
- `runtime-before-after-40s.mp4`: 40-second side-by-side comparison of the prior and new real Windows desktop recordings (left = before, right = after).
- `desktop-after.png`: full-resolution current Windows desktop frame.
- `desktop-40s.mp4`: 40-second full-resolution current desktop capture.

The grade changes no camera-depth pixels closer than 17.2 scene units; average background-channel change is 12.16/255. Visual review found the foreground planting and fish readable, with the central background darker and less flat. The correction introduces no discernible particle, fog, or caustic effect.

## Verification

- `build.ps1 -Target All`: passed; 72 habitat tests and the native fish logic, host policy, WebView2 probe, and host build passed.
- New 40-second capture: eight host samples at 59.8–60.0 FPS, mean 59.975 FPS, versus 58.6–60.0 FPS during the prior capture. Both had five draw calls and 47,962 triangles. The desktop recorder averaged 20.725 captured frames per second; that is separate from the host's WebView FPS.
- `git diff --check`: passed.

Reproduce the plate from the approved saved `.blend` by running `export_lush_runtime_plate.py`, then `export_lush_depth.py` with Blender, followed by `grade_lush_water_depth.py` and `build_manifest.py` with Python. The two generated depth arrays and intermediate PNG remain in ignored `art/work/lush-reference/`.
