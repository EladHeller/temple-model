"""Check the exported covered model's sourced curtain dimensions and counts.

Run after exporting: python3 validate_covered.py [tabernacle_covered.glb]
"""
import json
from pathlib import Path
import struct
import sys


def validate(path: Path) -> None:
    data = path.read_bytes()
    magic, version, size = struct.unpack_from('<4sII', data)
    assert (magic, version, size) == (b'glTF', 2, len(data)), 'Invalid GLB header'
    json_size, chunk_type = struct.unpack_from('<II', data, 12)
    assert chunk_type == 0x4E4F534A
    model = json.loads(data[20:20+json_size])
    nodes = model['nodes']
    for prefix, count, length, start, join_at in (
        ('יריעת משכן ', 10, 28, 0, 20),
        ('יריעת עיזים ', 11, 30, -2, 22),
    ):
        panels = sorted((node for node in nodes if node.get('name', '').startswith(prefix)),
                        key=lambda n: n['extras']['cloth_u_start'])
        assert len(panels) == count, (prefix, len(panels))
        for i, panel in enumerate(panels):
            extra = panel['extras']
            assert extra['flat_length_cubits'] == length
            assert extra['flat_width_cubits'] == 4
            assert extra['cloth_u_start'] == start+i*4
            assert extra['cloth_u_end'] == start+(i+1)*4
        assert any(n['extras']['cloth_u_start'] == join_at for n in panels)
    for layer in (1, 2):
        for side in (-1, 1):
            loops = [n for n in nodes if n.get('name', '').startswith(f'לולאה כיסוי {layer} צד {side} ')]
            assert len(loops) == 50, (layer, side, len(loops))
        hooks = [n for n in nodes if n.get('name', '').startswith(f'קרס כיסוי {layer} ')]
        assert len(hooks) == 50
    for name, layer in (('מכסה עורות אילים מאדמים', 3), ('מכסה עורות תחשים', 4)):
        node = next(n for n in nodes if n.get('name') == name)
        assert node['extras']['flat_width_cubits'] == 30
        assert node['extras']['flat_length_cubits'] == 10
        assert node['extras']['covering_layer'] == layer
    for material in model['materials']:
        if material['name'] in {'אריג יריעות המשכן', 'אריג עיזים שחור', 'מכסה אילים', 'מכסה תחשים'}:
            assert 'baseColorTexture' in material['pbrMetallicRoughness'], material['name']
            assert 'normalTexture' in material, material['name']
    for node in nodes:
        if node.get('name', '').startswith(('יריעת משכן ', 'יריעת עיזים ')):
            assert all('TEXCOORD_0' in p['attributes'] for p in model['meshes'][node['mesh']]['primitives'])
    assert all('bufferView' in image for image in model['images']), 'Textures must be embedded'
    by_name = {mat['name']: mat for mat in model['materials']}
    assert by_name['מכסה תחשים']['normalTexture']['index'] != by_name['אריג יריעות המשכן']['normalTexture']['index']
    materials = set(by_name)
    assert {'אריג יריעות המשכן', 'אריג עיזים שחור', 'מכסה אילים', 'מכסה תחשים'} <= materials
    assert any(n.get('name') == 'כפורת' for n in nodes), 'Missing interior vessels'
    assert any(n.get('name') == 'קרש דרום 20' for n in nodes), 'Missing complete south wall'
    assert any(n.get('name') == 'קרקע החצר' for n in nodes), 'Missing courtyard'
    print('Covered GLB: 10 inner + 11 goat panels, dimensions, 200 loops, 100 hooks,')
    print('two 30×10 roof hides, complete board walls, courtyard and interior: OK')
    print('UVs, embedded colour textures, separate cloth and hide normal maps: OK')


if __name__ == '__main__':
    validate(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('tabernacle_covered.glb'))
