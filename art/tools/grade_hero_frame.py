"""Post grade for the hero frame: darker lower corners and edges (vignette),
a gentle cool shadow / warm highlight split, and a blur test sheet.

  python art/tools/grade_hero_frame.py <raw.png> <graded.png> [--blur <blur.png>]
"""
import sys

import numpy as np
from PIL import Image, ImageFilter


def grade(src, dst):
    image = np.asarray(Image.open(src).convert('RGB')).astype(np.float32) / 255.0
    h, w, _ = image.shape
    y, x = np.mgrid[0:h, 0:w]
    u, v = (x / w - 0.42) / 0.75, (y / h - 0.42) / 0.62
    vignette = 1.0 - 0.45 * np.clip(u * u + v * v - 0.25, 0, 1) ** 1.1
    bottom = 1.0 - 0.18 * np.clip((y / h - 0.72) / 0.28, 0, 1) ** 1.5
    image *= (vignette * bottom)[..., None]
    luminance = image.mean(axis=2, keepdims=True)
    cool = np.array([0.97, 1.0, 1.03])
    warm = np.array([1.03, 1.0, 0.95])
    t = np.clip(luminance * 2.2, 0, 1)
    image *= cool * (1 - t) + warm * t
    Image.fromarray((np.clip(image, 0, 1) * 255 + 0.5).astype(np.uint8)).save(dst)


def blur_test(src, dst):
    image = Image.open(src).convert('RGB')
    small = image.resize((image.width // 16, image.height // 16), Image.LANCZOS)
    small = small.filter(ImageFilter.GaussianBlur(2))
    small.resize(image.size, Image.BICUBIC).save(dst)


if __name__ == '__main__':
    grade(sys.argv[1], sys.argv[2])
    if '--blur' in sys.argv:
        blur_test(sys.argv[2], sys.argv[sys.argv.index('--blur') + 1])
