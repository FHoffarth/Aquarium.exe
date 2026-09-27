"""Lay out unretouched reference and offline render, preserving both aspect ratios."""
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw, ImageFont
import sys

root = Path(__file__).resolve().parents[2]
out = root / 'docs/evidence/lush-reference'
reference = Image.open(sys.argv[1]).convert('RGB')
candidate = Image.open(out / 'offline-1920.png').convert('RGB')
assert candidate.size == (1920, 1080)
board = Image.new('RGB', (2400, 1040), '#111b20')
draw = ImageDraw.Draw(board)
font = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 28)
small = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 20)
for x, title, im in [(40,'SUPPLIED REFERENCE',reference),(1220,'OFFLINE CANDIDATE · 1920 × 1080',candidate)]:
    draw.text((x,30),title,font=font,fill='#ecf4f3')
    fitted = ImageOps.contain(im,(1140,880),Image.Resampling.LANCZOS)
    board.paste(fitted,(x+(1140-fitted.width)//2,95+(880-fitted.height)//2))
draw.text((40,995),'Both images shown in full, with original proportions. Offline art review — no runtime integration.',font=small,fill='#a5bdc1')
board.save(out/'reference-side-by-side.png')
print(out/'reference-side-by-side.png')
