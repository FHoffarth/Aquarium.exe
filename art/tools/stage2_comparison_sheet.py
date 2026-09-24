import pathlib
from PIL import Image, ImageDraw, ImageFont

W = pathlib.Path('C:/dev/aquarium-exe/art/work/stage2')
S1 = pathlib.Path('C:/dev/aquarium-exe/docs/evidence/natural-env-stage1')
E = pathlib.Path('C:/dev/aquarium-exe/docs/evidence/natural-env-stage2')
rows = [('NATURAL (Stage 2 photographed-leaf clusters)', E / 'NATURAL-full.png', E / 'NATURAL-close.png'),
        ('NATURAL, LeafSet002 stem masses off', E / 'NATURAL-nostems-full.png', None),
        ('REF (Pass 2 vegetation, same hardscape)', E / 'REF-full.png', E / 'REF-close.png')]
tw, th = 960, 540
sheet = Image.new('RGB', (tw * 2 + 30, (th + 40) * len(rows) + 10), (18, 20, 22))
draw = ImageDraw.Draw(sheet)
try:
    font = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 22)
except OSError:
    font = ImageFont.load_default()
for i, (label, full, close) in enumerate(rows):
    y = 10 + i * (th + 40)
    draw.text((10, y), label, fill=(230, 230, 230), font=font)
    sheet.paste(Image.open(full).convert('RGB').resize((tw, th), Image.LANCZOS), (10, y + 30))
    if close:
        sheet.paste(Image.open(close).convert('RGB').resize((tw, th), Image.LANCZOS), (tw + 20, y + 30))
sheet.save(E / 'comparison-natural-vs-pass2.jpg', quality=90)
print('sheet ok')
