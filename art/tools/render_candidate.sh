set -e
cd /c/dev/aquarium-exe
BL=/c/dev/tools/blender-5.2.2-windows-x64/blender.exe
O=C:/dev/aquarium-exe/art/work/candidate
FISH=${FISH:-C:/Users/Flo/AppData/Local/Temp/claude/C--dev-aquarium-exe/d373467c-aecd-48f8-b42d-bd90fa75c502/scratchpad/fish1b}
common="--variant B --mode final --scale 100 --density 1.0 --samples 64 --rocks scanned --bark willow --plants candidate"
$BL -b --factory-startup -P art/tools/compose_hero_frame.py -- $common --out $O/CANDIDATE-full-raw.png > $O/full.log 2>&1; grep -h rendered $O/full.log
$BL -b --factory-startup -P art/tools/compose_hero_frame.py -- $common --camera close --out $O/CANDIDATE-close-raw.png > $O/close.log 2>&1; grep -h rendered $O/close.log
$BL -b --factory-startup -P art/tools/compose_hero_frame.py -- $common --hero-fish $FISH --out $O/CANDIDATE-fish-raw.png > $O/fish.log 2>&1; grep -h rendered $O/fish.log
echo ALLDONE
