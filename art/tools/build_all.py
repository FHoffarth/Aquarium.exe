"""Rebuild every runtime art asset (Slices A, B and C) from the approved sources, in order.

  python art/tools/build_all.py            (sources must already be fetched)
  python art/tools/fetch_sources.py        (first time / fresh clone; Slices A and B)
  python art/tools/fetch_stage1_sources.py and fetch_stage2_sources.py   (Slice C sources)

Blender 5.2 LTS is required (dev tooling only; nothing Blender-related ships).
Set BLENDER to its executable if it is not at the default path below.
"""

import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOLS = ROOT / 'art' / 'tools'
BLENDER = os.environ.get('BLENDER', r'C:\dev\tools\blender-5.2.2-windows-x64\blender.exe')


def run(command, label):
    print(f'== {label}', flush=True)
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if line.startswith(('[slice-a]', '[slice-b]', '[slice-c]', '[cards]', 'manifest:')):
            print('  ' + line)
    if result.returncode != 0 or 'Traceback' in result.stdout + result.stderr:
        print(result.stdout[-4000:], result.stderr[-4000:], sep='\n')
        raise SystemExit(f'{label} failed')


def main():
    blender = [BLENDER, '-b', '--factory-startup', '-P']
    run(blender + [str(TOOLS / 'render_cards.py')], 'render vegetation cards (Blender)')
    run(blender + [str(TOOLS / 'build_slice_a.py')], 'build geometry + bake occlusion (Blender)')
    run([sys.executable, str(TOOLS / 'prepare_textures.py')], 'prepare textures')
    run(blender + [str(TOOLS / 'build_slice_b.py')], 'build Slice B geometry + cards (Blender)')
    run([sys.executable, str(TOOLS / 'prepare_textures_slice_b.py')], 'prepare Slice B textures')
    run([sys.executable, str(TOOLS / 'leaf_atlas_profiles.py')], 'extract LeafSet022 leaf outlines')
    run(blender + [str(TOOLS / 'build_slice_c.py')], 'build Slice C geometry (Blender)')
    run([sys.executable, str(TOOLS / 'prepare_textures_slice_c.py')], 'prepare Slice C textures')
    run([sys.executable, str(TOOLS / 'build_manifest.py')], 'write manifest')


if __name__ == '__main__':
    main()
