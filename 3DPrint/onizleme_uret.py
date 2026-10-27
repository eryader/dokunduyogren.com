"""
Web sayfasi (3DPrint/index.html) icin her STL'nin tek basina onizlemesini uretir.

Calistirma:
  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
      --python onizleme_uret.py

Cikti: onizleme/<stl_adi>.jpg (1200x800).
Gorunum geometri-seti/generate_set.py'deki render() ile ayni (workbench, turuncu parca).
"""
import bpy
import math
import os
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
# ruler-01 yan yatik disa aktarilmis (kalinlik x, boy y, en z; kabartmalar +x yuzunde):
# onizlemede kabartmali yuz yukari bakacak sekilde duz yatirilir (x->z, y->x, z->y)
FLAT_ON_X = Matrix(((0, 1, 0), (0, 0, 1), (1, 0, 0))).to_4x4()
STLS = [
    ('geometri-seti/stl/cetvel_20cm.stl', None),
    ('geometri-seti/stl/gonye_45.stl', None),
    ('geometri-seti/stl/gonye_30_60.stl', None),
    ('geometri-seti/stl/iletki_180.stl', None),
    ('ruler-01/tactile_ruler_beefier.stl', FLAT_ON_X),
]
RES = (1200, 800)
TILT = 28.0
PAD = 1.12              # parca etrafindaki bosluk orani


def setup_scene():
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x, scene.render.resolution_y = RES
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = 'JPEG'
    scene.render.image_settings.quality = 85
    sh = scene.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'OBJECT'
    sh.show_cavity = True
    sh.cavity_type = 'BOTH'
    sh.show_shadows = True
    sh.background_type = 'VIEWPORT'
    sh.background_color = (0.93, 0.91, 0.87)
    cam = bpy.data.objects.new('kamera', bpy.data.cameras.new('kamera'))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.type = 'ORTHO'
    cam.data.clip_end = 5000
    return scene, cam


def render(scene, cam, obj, path):
    xs = [(obj.matrix_world @ v.co).x for v in obj.data.vertices]
    ys = [(obj.matrix_world @ v.co).y for v in obj.data.vertices]
    zs = [(obj.matrix_world @ v.co).z for v in obj.data.vertices]
    w, d = max(xs) - min(xs), max(ys) - min(ys)
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    t = math.radians(TILT)
    aspect = RES[0] / RES[1]
    cam.data.ortho_scale = max(w, d * math.cos(t) * aspect) * PAD
    cam.location = (cx, cy - 600 * math.sin(t), 600 * math.cos(t))
    cam.rotation_euler = (t, 0, 0)
    for o in scene.objects:
        if o.type == 'MESH':
            o.hide_render = o is not obj
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('ONIZLEME %-28s %6.1f x %6.1f x %4.1f mm' % (os.path.basename(path), w, d, max(zs) - min(zs)))


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene, cam = setup_scene()
    out = os.path.join(HERE, 'onizleme')
    os.makedirs(out, exist_ok=True)
    for rel, orient in STLS:
        bpy.ops.wm.stl_import(filepath=os.path.join(HERE, rel))
        obj = bpy.context.selected_objects[0]
        if orient is not None:
            obj.matrix_world = orient
        obj.color = (0.95, 0.45, 0.12, 1.0)
        name = os.path.splitext(os.path.basename(rel))[0]
        render(scene, cam, obj, os.path.join(out, name + '.jpg'))


main()
