set -e
cd /c/dev/aquarium-exe
BL=/c/dev/tools/blender-5.2.2-windows-x64/blender.exe
O=C:/dev/aquarium-exe/art/work/stage2
common="--variant B --mode final --scale 100 --density 1.0 --samples 64 --rocks scanned --bark willow --plants natural"
$BL -b --factory-startup -P art/tools/compose_hero_frame.py -- $common --out $O/NATURAL-full-raw.png > $O/NATURAL-full.log 2>&1; grep -h rendered $O/NATURAL-full.log
$BL -b --factory-startup -P art/tools/compose_hero_frame.py -- $common --camera close --out $O/NATURAL-close-raw.png > $O/NATURAL-close.log 2>&1; grep -h rendered $O/NATURAL-close.log
$BL -b --factory-startup -P art/tools/compose_hero_frame.py -- $common --stems off --out $O/NATURAL-nostems-full-raw.png > $O/NATURAL-nostems.log 2>&1; grep -h rendered $O/NATURAL-nostems.log
echo ALLDONE
