"""Compare two offline aquarium renders at equal scale."""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


root = Path(__file__).resolve().parents[2]
evidence = root / "docs/evidence/lush-reference"
parser = argparse.ArgumentParser()
parser.add_argument("--left", default="offline-1920.png")
parser.add_argument("--right", default="dusk-1920.png")
parser.add_argument("--left-label", default="BRIGHT BASELINE")
parser.add_argument("--right-label", default="DARKER AQUARIUM LIGHT")
parser.add_argument("--out", default="bright-vs-dusk.png")
args = parser.parse_args()
font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 28)
board = Image.new("RGB", (2400, 760), "#111b20")
draw = ImageDraw.Draw(board)

for x, label, filename in (
    (40, args.left_label, args.left),
    (1220, args.right_label, args.right),
):
    frame = Image.open(evidence / filename).convert("RGB")
    assert frame.size == (1920, 1080)
    draw.text((x, 20), label, font=font, fill="#ecf4f3")
    board.paste(frame.resize((1140, 641), Image.Resampling.LANCZOS), (x, 70))

output = evidence / args.out
board.save(output)
print(output)
