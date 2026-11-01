"""Reproducible cloth and hide textures; their decorative layouts are artistic.

Uses only the Python standard library. GLB export embeds the resulting PNGs.
The four thread colours are sourced; bands and medallions are not prescribed.
"""
from pathlib import Path
import math
import struct
import zlib

SIZE = 512


def write_png(path, pixels):
    def chunk(kind, payload):
        return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload))
    rows = b''.join(b'\0' + pixels[y*SIZE*3:(y+1)*SIZE*3] for y in range(SIZE))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', SIZE, SIZE, 8, 2, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(rows, 9)) + chunk(b'IEND', b''))


def create_textures(directory):
    directory = Path(directory)
    directory.mkdir(exist_ok=True)
    blue, purple, red, linen = (35, 78, 140), (107, 38, 106), (165, 37, 43), (228, 212, 176)
    images = {name: bytearray() for name in ('woven', 'goat', 'ram', 'tahash', 'weave_normal', 'hide_normal')}
    for y in range(SIZE):
        for x in range(SIZE):
            u, v = x / SIZE, y / SIZE
            # Interlaced warp/weft threads, with deterministic small fibre variation.
            noise = ((x*37 ^ y*101 ^ x*y*13) % 17) - 8
            weave = (5 if (x//2 + y//2) % 2 else -5) + noise*.35
            if u < .16 or u >= .84:
                color = blue
            elif .23 <= u < .38:
                color = red
            elif .62 <= u < .77:
                color = purple
            else:
                color = linen
            diamond = abs(u-.5) + abs(v-.5)
            if diamond < .32:
                color = linen
            elif diamond < .335:
                color = red
            elif diamond < .355:
                color = blue
            elif diamond < .37:
                color = linen
            # Narrow woven guards and double borders mark individual sewn panels.
            if min(u, 1-u) < .018:
                color = linen if (y//5) % 2 else red
            if .185 < u < .196 or .804 < u < .815:
                color = red
            if .208 < u < .218 or .782 < u < .792:
                color = blue
            images['woven'].extend(max(0, min(255, round(c+weave))) for c in color)
            for name, base in (('goat', (48, 40, 33)), ('ram', (152, 36, 29))):
                fiber = weave if name == 'goat' else noise*.6
                seam = min(x, y, SIZE-x, SIZE-y) < 3
                images[name].extend(max(0, min(255, round(c+fiber-(16 if seam else 0)))) for c in base)
            # Rashi Exodus 25:5 describes many colours, not their exact palette.
            # Organic mottling suggests skin rather than the inner woven fabric.
            palette = ((39, 108, 125), (56, 78, 142), (113, 48, 122),
                       (158, 53, 61), (179, 119, 55), (88, 128, 95))
            tau = 2 * math.pi
            field = (math.sin(tau*(u+v) + 1.2*math.sin(tau*v))
                     + .7*math.cos(tau*(2*u-v)) + .3*math.sin(tau*(u-3*v)))
            position = (field+2) / 4 * len(palette)
            index = math.floor(position)
            blend = position-index
            blend = max(0, min(1, (blend-.30)/.40))
            blend = blend*blend*(3-2*blend)
            first, second = palette[index % len(palette)], palette[(index+1) % len(palette)]
            images['tahash'].extend(max(0, min(255, round(a*(1-blend)+b*blend+noise*.45)))
                                   for a,b in zip(first, second))
            grain_x = ((x*19 ^ y*47) % 11)-5
            grain_y = ((x*43 ^ y*23) % 11)-5
            images['hide_normal'].extend((128+grain_x, 128+grain_y, 254))
            images['weave_normal'].extend((121 if x % 4 < 2 else 135,
                                            121 if y % 4 < 2 else 135, 254))
    for name, data in images.items():
        write_png(directory / (name + '.png'), data)
    return directory


if __name__ == '__main__':
    create_textures(Path(__file__).with_name('textures'))
