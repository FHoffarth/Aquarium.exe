"""Compare the bright and darker offline aquarium renders at equal scale."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


root = Path(__file__).resolve().parents[2]
evidence = root / "docs/evidence/lush-reference"
font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 28)
board = Image.new("RGB", (2400, 760), "#111b20")
draw = ImageDraw.Draw(board)

for x, label, filename in (
    (40, "BRIGHT BASELINE", "offline-1920.png"),
    (1220, "DARKER AQUARIUM LIGHT", "dusk-1920.png"),
):
    frame = Image.open(evidence / filename).convert("RGB")
    assert frame.size == (1920, 1080)
    draw.text((x, 20), label, font=font, fill="#ecf4f3")
    board.paste(frame.resize((1140, 641), Image.Resampling.LANCZOS), (x, 70))

output = evidence / "bright-vs-dusk.png"
board.save(output)
print(output)
