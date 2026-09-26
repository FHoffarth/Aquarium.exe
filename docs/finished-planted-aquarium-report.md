# Finished planted aquarium candidate

Branch: `codex/finished-planted-aquarium` from `b7387a9` (`claude/natural-env-runtime-slice-c`). Not merged.

## Visual result

The Slice C scanned rocks, driftwood, photographed broad leaves, Hero Fish school, camera and underwater light remain. One original vertex-coloured growth mesh adds distinct silhouettes: tall flowing ribbons, fine branching and fan-shaped stems, and short irregular foreground blades. Masses cross depth layers behind and beside the hardscape, rise at both frame edges, and taper toward an open swimming area. A few low clumps break up the former empty centre floor. The A/B/C LeafSet-only additions were not promoted.

Compared with polished Slice C, the hardscape now sits in a planted bank rather than an exposed pile, and the right side has a planted edge. The fish remain small against the open dark water. The vegetation is intentionally stylized; the left icon columns still cover part of the planted bank on this machine.

| Real host at 1920×1080 | Polished Slice C | Candidate |
|---|---:|---:|
| Rendered triangles | 90,432 | 114,076 |
| Draw calls | 12 | 13 |
| Sustained diagnostic FPS | 60.0 | 60.0 |
| Attributed GPU | 76.4% (earlier short sample) | 73.5% mean (30 s) |
| Paused attributed GPU | 0% (original Slice C check) | 0% (12 s) |

The GPU samples were taken at different times and are guardrails, not a controlled before/after benchmark. The candidate's 30-second sample was `CONCLUSIVE`: one Aquarium root, active session, no attachment failure, and 72.1–74.8% sampled attributed GPU. Steady five-second diagnostic windows reported 60.0 FPS; the host probe found Explorer `SysListView32` at the cursor, with the Aquarium renderer excluded from hit testing. The paused sample was also `CONCLUSIVE`: 0% CPU and 0% attributed GPU, with `paused=true` and `fps=0.0`.

## Evidence

- `docs/evidence/finished-planted-aquarium/desktop-clean-1920.png`: clean real Windows desktop, 1920×1080.
- `docs/evidence/finished-planted-aquarium/desktop-fish-1920.png`: second real desktop frame with the school across the swim area.
- `docs/evidence/finished-planted-aquarium/running-30s.json`: host, FPS diagnostics, CPU and GPU samples.
- `docs/evidence/finished-planted-aquarium/paused-12s.json`: paused idle sample.

## Verification

`build.ps1 -Target All` passed: 70 Node tests, native fish-logic and host-policy tests, WebView2 Runtime probe, and the x64 `/W4 /WX` host build. The generated GLB is recorded with SHA-256 in the asset manifest; asset budget and integrity tests pass. No native host, simulation, frame pacing, fish or input code changed.

The candidate remains on its own branch for final visual approval.
