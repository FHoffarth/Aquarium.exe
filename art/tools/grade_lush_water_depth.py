"""Apply restrained camera-depth water integration to the approved plate.

Requires the two half-resolution arrays from export_lush_depth.py and the
unmodified approved PNG from export_lush_runtime_plate.py. No geometry,
camera, fish, or lighting is edited.
"""

import pathlib

import numpy as np
from PIL import Image, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parents[2]
WORK = ROOT / 'art/work/lush-reference'
SOURCE = WORK / 'runtime-environment.png'
DESTINATION = ROOT / 'habitat/assets/lush/environment_albedo.webp'
PREVIEW = WORK / 'runtime-depth-preview.png'


def upsample(array, size, mode):
    return np.asarray(Image.fromarray(array, mode=mode).resize(
        size, Image.Resampling.BILINEAR), dtype=np.float32)


def main():
    image = Image.open(SOURCE).convert('RGB')
    if image.size != (1920, 1080):
        raise ValueError(f'approved plate has unexpected size: {image.size}')
    color = np.asarray(image, dtype=np.float32)
    depth_half = np.load(WORK / 'camera-depth-half.npy')
    background_half = np.load(WORK / 'background-mask-half.npy')
    if depth_half.shape != (540, 960) or background_half.shape != depth_half.shape:
        raise ValueError('depth arrays must be half-resolution for the approved camera')
    depth = upsample(np.nan_to_num(depth_half, posinf=22.0), image.size, 'F')
    background = upsample(background_half.astype(np.uint8) * 255, image.size, 'L') / 255.0
    background = np.asarray(Image.fromarray(np.uint8(background * 255), 'L').filter(
        ImageFilter.GaussianBlur(0.8)), dtype=np.float32) / 255.0

    # No correction in the near water; attenuation rises gradually with
    # actual scene distance. The blend toward dim water reduces the contrast
    # and saturation of distant vegetation by less than nine percent.
    distance = np.clip((depth - 17.2) / 4.2, 0.0, 1.0)
    distance = distance * distance * (3.0 - 2.0 * distance)
    far_plant = (1.0 - background) * 0.085 * distance
    water_color = np.array([44.0, 90.0, 96.0], dtype=np.float32)
    result = color * (1.0 - far_plant[..., None]) + water_color * far_plant[..., None]

    # The background remains an unobtrusive blue-green field, with a quiet
    # overhead-to-deep falloff and broad irregular variation of only a few
    # digital levels. This affects the background mesh, not nearby leaves.
    height, width = color.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    y = yy / (height - 1)
    x = xx / (width - 1)
    shade = 0.91 - 0.065 * y
    variation = (1.5 * np.sin(2.5 * np.pi * x + 1.7 * y)
                 + 1.0 * np.sin(1.4 * np.pi * y - 2.1 * x))
    dark_background = color * shade[..., None] + variation[..., None]
    result = result * (1.0 - background[..., None]) + dark_background * background[..., None]
    # Bilinear mask edges must not touch a foreground leaf, even by one level.
    result[depth < 17.2] = color[depth < 17.2]
    output = np.uint8(np.clip(np.rint(result), 0, 255))
    preview = Image.fromarray(output, 'RGB')
    preview.save(PREVIEW)
    preview.save(DESTINATION, format='WEBP', lossless=True, method=6)
    change = np.abs(output.astype(np.int16) - color.astype(np.int16))
    near = depth < 17.2
    print(f'Wrote {DESTINATION} and {PREVIEW}')
    print(f'Average absolute channel change: {change.mean():.2f}/255; '
          f'near-pixel change: {change[near].mean():.2f}/255; '
          f'background-pixel change: {change[background > 0.9].mean():.2f}/255')


if __name__ == '__main__':
    main()
