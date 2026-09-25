"""Natural Environment Candidate: comparison and blur/silhouette sheets.

  python art/tools/candidate_sheets.py

Inputs: graded candidate frames in docs/evidence/natural-env-candidate/,
references in art/work/candidate/ref/ (Pass 2 hero frame, runtime Slice B
capture from claude/aquascape-runtime-slice-b).
"""
import pathlib

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[2]
E = ROOT / 'docs' / 'evidence' / 'natural-env-candidate'
REF = ROOT / 'art' / 'work' / 'candidate' / 'ref'
TW, TH = 960, 540
try:
    FONT = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 22)
except OSError:
    FONT = ImageFont.load_default()


def blurred(image):
    small = image.resize((image.width // 16, image.height // 16), Image.LANCZOS)
    return small.filter(ImageFilter.GaussianBlur(2)).resize(image.size, Image.BICUBIC)


def sheet(cells, columns, out):
    rows = (len(cells) + columns - 1) // columns
    canvas = Image.new('RGB', (columns * (TW + 10) + 10, rows * (TH + 40) + 10), (18, 20, 22))
    draw = ImageDraw.Draw(canvas)
    for i, (label, image) in enumerate(cells):
        x, y = 10 + (i % columns) * (TW + 10), 10 + (i // columns) * (TH + 40)
        draw.text((x, y), label, fill=(230, 230, 230), font=FONT)
        canvas.paste(image.convert('RGB').resize((TW, TH), Image.LANCZOS), (x, y + 30))
    canvas.save(out, quality=90)
    print('wrote', out.name)


def main():
    candidate = Image.open(E / 'CANDIDATE-full.png')
    runtime = Image.open(REF / 'runtime-slice-b.png')
    pass2 = Image.open(REF / 'pass2.png')
    sheet([('CANDIDATE (validated vocabulary, open water)', candidate),
           ('Runtime Slice B (current default, real host capture)', runtime),
           ('Pass 2 hero frame (offline reference)', pass2),
           ('CANDIDATE with Hero Fish 1B (desktop scale 0.75)', Image.open(E / 'CANDIDATE-fish.png'))],
          2, E / 'comparison-candidate-vs-runtime-pass2.jpg')
    sheet([('CANDIDATE - blur/silhouette', blurred(candidate)),
           ('Runtime Slice B - blur/silhouette', blurred(runtime)),
           ('CANDIDATE with fish - blur/silhouette', blurred(Image.open(E / 'CANDIDATE-fish.png'))),
           ('Pass 2 - blur/silhouette', blurred(pass2))],
          2, E / 'blur-silhouette-check.jpg')


if __name__ == '__main__':
    main()
