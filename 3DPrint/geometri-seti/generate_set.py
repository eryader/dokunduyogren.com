"""
Dokunsal geometri seti (gorme engelli ogrenciler icin) - parametrik STL ureteci.

Calistirma:
  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
      --python generate_set.py -- [cikti_klasoru]

Parcalar (Ender 3 S1, 220x220 tabla icin boyutlandirildi):
  cetvel_20cm      : 20 cm cetvel, her cm nokta, her 5 cm buyuk nokta, 0/10/20 cizgi,
                     5-10-15-20 Braille rakam, set halkasi icin aski deligi
  gonye_45         : 45-45-90 gonye, iki dik kenar 15 cm, uc kenarda cm olcegi
  gonye_30_60      : 30-60-90 gonye, 10 / 17.3 / 20 cm kenarlar, uc kenarda cm olcegi
  iletki_180       : 10 cm yaricapli iletki, her 10 derece nokta, 30'un katlari buyuk
                     nokta, 90 derece cizgi, merkez centigi, tabanda cm olcegi

Dokunsal kodlama (butun parcalarda ayni):
  kucuk nokta = 1 cm / 10 derece, buyuk nokta = 5 cm / 30 derece,
  cizgi = 10 cm / 90 derece (ve cetvelde sifir), Braille = sayi isareti + rakam
Her olcek isaretinin hizasinda kenarda yarim daire centik var: cizerken kalem ucu
centige takilir, ogrenci kac cm ilerledigini sayabilir (ruler-01'deki centik olcusu).
Braille etiketler, olcek kenari okuyucuya en yakin olacak sekilde tutuldugunda
soldan saga okunur.
"""
import bpy
import bmesh
import math
import os
import sys
from mathutils import Vector

# ---------------------------------------------------------------------------
# Olculer (mm)
# ---------------------------------------------------------------------------
T = 3.0                 # plaka kalinligi
TICK_OFF = 4.5          # olcek noktalarinin kenardan uzakligi
DOT_S = (0.9, 0.8)      # kucuk nokta (yaricap, yukseklik)
DOT_L = (1.6, 1.0)      # buyuk nokta
BAR = (0.7, 0.9)        # cizgi (yari genislik, yukseklik)
BAR_SPAN = (2.0, 8.0)   # cizginin kenardan baslangic / bitis uzakligi
BR_DOT = (0.75, 0.6)    # Braille noktasi (yaricap, yukseklik)
BR_PITCH = 2.5          # hucre ici nokta araligi
BR_CELL = 6.0           # hucre baslangiclari arasi
BR_OFF = 14.5           # Braille etiket merkezinin kenardan uzakligi
END_CLEAR = 15.0        # gonyede olcek, karsi sivri koseden bu kadar once biter
                        # (iki kenarin olcegi koseye yakin karismasin)
NOTCH_R = 0.5           # kenar centigi yaricapi (1.0 genis, 0.5 derin; ruler-01 ile ayni)
MARGIN = 0.8            # kabartma ile parca kenari arasindaki en az bosluk
GAP = 0.5               # iki kabartma arasindaki en az bosluk
SINK = 0.3              # kabartmalarin plakaya gomulme payi (boolean birlesim icin)
BED = 220.0             # tabla boyutu (kontrol icin)

BRAILLE_DIGITS = {
    '1': (1,), '2': (1, 2), '3': (1, 4), '4': (1, 4, 5), '5': (1, 5),
    '6': (1, 2, 4), '7': (1, 2, 4, 5), '8': (1, 2, 5), '9': (2, 4), '0': (2, 4, 5),
}
BRAILLE_NUM_SIGN = (3, 4, 5, 6)


# ---------------------------------------------------------------------------
# 2B geometri
# ---------------------------------------------------------------------------
def v2(x, y):
    return Vector((x, y))


def cross(a, b):
    return a.x * b.y - a.y * b.x


def area(poly):
    return 0.5 * sum(cross(p, q) for p, q in zip(poly, poly[1:] + poly[:1]))


def clean(poly, eps=1e-6):
    pts = []
    for p in poly:
        if not pts or (p - pts[-1]).length > eps:
            pts.append(p)
    if len(pts) > 1 and (pts[0] - pts[-1]).length <= eps:
        pts.pop()
    out = []
    n = len(pts)
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        if abs(cross(b - a, c - b)) > 1e-9:
            out.append(b)
    return out


def ccw(poly):
    return poly if area(poly) > 0 else poly[::-1]


def left_normal(u):
    return v2(-u.y, u.x)


def clip(poly, p, n, d):
    """Yari duzlem {x : (x-p).n >= d} ile kirp (Sutherland-Hodgman)."""
    out = []
    m = len(poly)
    for i in range(m):
        a, b = poly[i], poly[(i + 1) % m]
        da, db = (a - p).dot(n) - d, (b - p).dot(n) - d
        if da >= 0:
            out.append(a)
        if (da >= 0) != (db >= 0):
            out.append(a + (b - a) * (da / (da - db)))
    return out


def inset(poly, d):
    """Dis bukey cokgeni d kadar iceri ofsetle."""
    poly = ccw(clean(poly))
    out = list(poly)
    m = len(poly)
    for i in range(m):
        a, b = poly[i], poly[(i + 1) % m]
        out = clip(out, a, left_normal((b - a).normalized()), d)
    return clean(out)


def rounded(poly, r, step=math.radians(5)):
    """Dis bukey cokgenin koselerini r yaricapla yuvarla (iceri ofset + disari ofset)."""
    core = inset(poly, r)
    out = []
    m = len(core)
    for i in range(m):
        a, b, c = core[i - 1], core[i], core[(i + 1) % m]
        n1 = -left_normal((b - a).normalized())
        n2 = -left_normal((c - b).normalized())
        a1 = math.atan2(n1.y, n1.x)
        a2 = math.atan2(n2.y, n2.x)
        while a2 < a1:
            a2 += 2 * math.pi
        sweep = a2 - a1
        if sweep < step:
            out.append(b + (n1 + n2).normalized() * (r / math.cos(sweep / 2)))
        else:
            k = math.ceil(sweep / step)
            for j in range(k + 1):
                t = a1 + sweep * j / k
                out.append(b + v2(math.cos(t), math.sin(t)) * r)
    return clean(out)


def rect(w, h):
    return [v2(0, 0), v2(w, 0), v2(w, h), v2(0, h)]


def circle(c, r, n=48):
    return [c + v2(math.cos(2 * math.pi * k / n), math.sin(2 * math.pi * k / n)) * r for k in range(n)]


def arc_poly(r, deg0, deg1, step=1.0):
    """Merkez (0,0); deg0 -> deg1 yayi + kapatan kiris (CCW)."""
    k = max(2, math.ceil((deg1 - deg0) / step))
    return [v2(math.cos(t), math.sin(t)) * r
            for t in (math.radians(deg0 + (deg1 - deg0) * j / k) for j in range(k + 1))]


def inside(p, poly):
    c = False
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if (a.y > p.y) != (b.y > p.y):
            if p.x < a.x + (p.y - a.y) * (b.x - a.x) / (b.y - a.y):
                c = not c
    return c


def seg_dist(p, a, b):
    ab = b - a
    L2 = ab.length_squared
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, (p - a).dot(ab) / L2))
    return (p - (a + ab * t)).length


def loop_dist(p, poly):
    return min(seg_dist(p, poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly)))


def samples(p0, p1, step=0.5):
    n = max(1, math.ceil((p1 - p0).length / step))
    return [p0.lerp(p1, i / n) for i in range(n + 1)]


# ---------------------------------------------------------------------------
# Parca: dis hat + delikler + kabartmalar
# ---------------------------------------------------------------------------
class Piece:
    def __init__(self, name, outer, holes):
        self.name = name
        self.outer = ccw(outer)
        self.holes = [ccw(h) for h in holes]
        self.bumps = []      # (p0, p1, r, h)
        self.notches = []    # kenar uzerindeki centik merkezleri
        self.skipped = []

    def _fits(self, p0, p1, r):
        loops = [self.outer] + self.holes
        for p in samples(p0, p1):
            if not inside(p, self.outer) or any(inside(p, h) for h in self.holes):
                return False
            if min(loop_dist(p, lp) for lp in loops) < r + MARGIN:
                return False
        for q0, q1, rq, _ in self.bumps:
            if min(seg_dist(p, q0, q1) for p in samples(p0, p1)) < r + rq + GAP:
                return False
        return True

    def add_group(self, items, label):
        """Hepsi sigarsa ekle, biri bile sigmazsa hicbirini ekleme."""
        start = len(self.bumps)
        for p0, p1, r, h in items:
            p1 = p0 if p1 is None else p1
            if not self._fits(p0, p1, r):
                del self.bumps[start:]
                return False
            self.bumps.append((p0, p1, r, h))
        return True

    def add(self, p0, p1, size, label):
        if self.add_group([(p0, p1, size[0], size[1])], label):
            return True
        self.skipped.append(label)
        return False

    def add_braille(self, text, place, label, nudge=6.0):
        """place(x, y) -> dunya noktasi; x okuma yonu, y yukari. Sigmazsa okuma yonunde kaydir."""
        dots = braille_layout(text)
        for k in range(int(nudge * 2) + 1):
            dx = (k + 1) // 2 * 0.5 * (-1 if k % 2 else 1)
            items = [(place(x + dx, y), None, BR_DOT[0], BR_DOT[1]) for x, y in dots]
            if self.add_group(items, label):
                return
        self.skipped.append(label)


def braille_layout(number_text):
    cells = [BRAILLE_NUM_SIGN] + [BRAILLE_DIGITS[c] for c in number_text]
    width = (len(cells) - 1) * BR_CELL + BR_PITCH
    dots = []
    for ci, cell in enumerate(cells):
        x0 = -width / 2 + ci * BR_CELL
        for d in cell:
            col = 0 if d <= 3 else 1
            row = (d - 1) % 3
            dots.append((x0 + col * BR_PITCH, (1 - row) * BR_PITCH))
    return dots


def linear_scale(pc, origin, mdir, inward, kmin, kmax, read, labels=True):
    """origin'den mdir yonunde her 10 mm'de bir isaret; Braille 5'in katlarinda."""
    for k in range(kmin, kmax + 1):
        base = origin + mdir * (10.0 * k)
        tag = '%s %d cm' % (pc.name, k)
        if k % 10 == 0:
            placed = pc.add(base + inward * BAR_SPAN[0], base + inward * BAR_SPAN[1], BAR, tag)
        elif k % 5 == 0:
            placed = pc.add(base + inward * TICK_OFF, None, DOT_L, tag)
        else:
            placed = pc.add(base + inward * TICK_OFF, None, DOT_S, tag)
        if placed:
            pc.notches.append(base)
        if labels and k > 0 and k % 5 == 0:
            c = base + inward * BR_OFF
            pc.add_braille(str(k), lambda x, y, c=c: c + read * x + inward * y, tag + ' braille')


# ---------------------------------------------------------------------------
# Parcalar
# ---------------------------------------------------------------------------
def make_ruler(cm=20, width=30.0, margin=8.0):
    L = cm * 10 + 2 * margin
    outer = rounded(rect(L, width), 3.0)
    holes = [circle(v2(margin + 1.0, width - 7.5), 2.5)]   # set halkasi icin
    pc = Piece('cetvel_%dcm' % cm, outer, holes)
    linear_scale(pc, v2(margin, 0), v2(1, 0), v2(0, 1), 0, cm, v2(1, 0))
    return pc


def make_set_square(name, verts, right_idx, hyp_zero_idx, band=20.0):
    sharp = verts               # CCW
    outer = rounded(sharp, 1.0)
    inner = rounded(inset(sharp, band), 4.0)
    pc = Piece(name, outer, [inner])
    n = len(sharp)
    for i in range(n):
        ia, ib = i, (i + 1) % n
        a, b = sharp[ia], sharp[ib]
        L = (b - a).length
        u = (b - a) / L
        zero = right_idx if right_idx in (ia, ib) else hyp_zero_idx
        if zero == ia:
            origin, mdir = a, u
        else:
            origin, mdir = b, -u
        linear_scale(pc, origin, mdir, left_normal(u), 1, int((L - END_CLEAR) // 10), u)
    return pc


def make_protractor(R=100.0, band=20.0, base=20.0, notch=1.5):
    outer = rounded(arc_poly(R, 0, 180), 1.5)
    # taban kenarinin ortasina merkez centigi
    for i in range(len(outer)):
        a, b = outer[i], outer[(i + 1) % len(outer)]
        if abs(a.y) < 1e-6 and abs(b.y) < 1e-6 and a.x < 0 < b.x:
            k = 12
            cut = [v2(math.cos(math.pi * (1 - j / k)), math.sin(math.pi * (1 - j / k))) * notch
                   for j in range(k + 1)]
            outer = outer[:i + 1] + cut + outer[i + 1:]
            break
    ri = R - band
    a0 = math.degrees(math.asin(base / ri))
    inner = rounded(arc_poly(ri, a0, 180 - a0), 4.0)
    pc = Piece('iletki_180', outer, [inner])

    for deg in range(10, 180, 10):
        u = v2(math.cos(math.radians(deg)), math.sin(math.radians(deg)))
        tag = '%s %d deg' % (pc.name, deg)
        if deg == 90:
            placed = pc.add(u * (R - BAR_SPAN[0]), u * (R - BAR_SPAN[1]), BAR, tag)
        elif deg % 30 == 0:
            placed = pc.add(u * (R - TICK_OFF), None, DOT_L, tag)
        else:
            placed = pc.add(u * (R - TICK_OFF), None, DOT_S, tag)
        if placed:
            pc.notches.append(u * R)

    rc = R - BR_OFF
    for deg in (30, 60, 90, 120, 150):
        th = math.radians(deg)

        def place(x, y, th=th):
            t = th - x / rc            # saat yonunde okunur, ust taraf disa bakar
            return v2(math.cos(t), math.sin(t)) * (rc + y)
        pc.add_braille(str(deg), place, '%s %d deg braille' % (pc.name, deg))

    # tabanda merkezden iki yana cm olcegi + merkez cizgisi
    kmax = int((R - 5) // 10)
    linear_scale(pc, v2(0, 0), v2(1, 0), v2(0, 1), 1, kmax, v2(1, 0))
    linear_scale(pc, v2(0, 0), v2(-1, 0), v2(0, 1), 1, kmax, v2(1, 0))
    pc.add(v2(0, notch + BAR[0] + MARGIN + 0.2), v2(0, 12.0), BAR, 'merkez cizgisi')
    return pc


def make_pieces():
    s3 = math.sqrt(3)
    return [
        make_ruler(20),
        make_set_square('gonye_45', [v2(0, 0), v2(150, 0), v2(0, 150)], 0, 1),
        make_set_square('gonye_30_60', [v2(0, 0), v2(100, 0), v2(0, 100 * s3)], 0, 1),
        make_protractor(),
    ]


# ---------------------------------------------------------------------------
# 3B
# ---------------------------------------------------------------------------
def plate_mesh(pc):
    bm = bmesh.new()
    edges = []
    for loop in [pc.outer] + pc.holes:
        vs = [bm.verts.new((p.x, p.y, 0.0)) for p in loop]
        for i in range(len(vs)):
            edges.append(bm.edges.new((vs[i], vs[(i + 1) % len(vs)])))
    res = bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=edges,
                                  normal=(0, 0, 1))
    faces = [f for f in res['geom'] if isinstance(f, bmesh.types.BMFace)]
    filled = sum(f.calc_area() for f in faces)
    expected = area(pc.outer) - sum(area(h) for h in pc.holes)
    assert abs(filled - expected) < 0.01 * expected, (pc.name, filled, expected)
    ext = bmesh.ops.extrude_face_region(bm, geom=faces)
    top = [g for g in ext['geom'] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, 0, T), verts=top)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(pc.name + '_plate')
    bm.to_mesh(me)
    bm.free()
    return me


def ring(p0, p1, rho, n):
    if (p1 - p0).length < 1e-6:
        return [p0 + v2(math.cos(2 * math.pi * k / n), math.sin(2 * math.pi * k / n)) * rho
                for k in range(n)]
    d = (p1 - p0).normalized()
    base = math.atan2(d.y, d.x)
    half = n // 2
    pts = [p1 + v2(math.cos(t), math.sin(t)) * rho
           for t in (base - math.pi / 2 + math.pi * k / (half - 1) for k in range(half))]
    pts += [p0 + v2(math.cos(t), math.sin(t)) * rho
            for t in (base + math.pi / 2 + math.pi * k / (half - 1) for k in range(half))]
    return pts


def bumps_mesh(pc, n=24):
    """Her kabartma kapali bir kubbe/kapsul; alt kismi plakaya SINK kadar gomulu."""
    bm = bmesh.new()
    thetas = [math.radians(a) for a in (0, 22, 40, 55, 67, 77, 85)]
    for p0, p1, r, h in pc.bumps:
        profile = [(r, T - SINK)] + [(r * math.cos(t), T + h * math.sin(t)) for t in thetas]
        rings = []
        for rho, z in profile:
            rings.append([bm.verts.new((p.x, p.y, z)) for p in ring(p0, p1, rho, n)])
        bm.faces.new(rings[0][::-1])
        for lo, hi in zip(rings, rings[1:]):
            m = len(lo)
            for i in range(m):
                bm.faces.new((lo[i], lo[(i + 1) % m], hi[(i + 1) % m], hi[i]))
        bm.faces.new(rings[-1])
    me = bpy.data.meshes.new(pc.name + '_bumps')
    bm.to_mesh(me)
    bm.free()
    return me


def notches_mesh(pc, n=24):
    """Kenar centikleri icin dikey silindirler; merkezleri kenar uzerinde."""
    bm = bmesh.new()
    for c in pc.notches:
        pts = ring(c, c, NOTCH_R, n)
        lo = [bm.verts.new((p.x, p.y, -1.0)) for p in pts]
        hi = [bm.verts.new((p.x, p.y, T + 1.0)) for p in pts]
        bm.faces.new(lo[::-1])
        for i in range(n):
            bm.faces.new((lo[i], lo[(i + 1) % n], hi[(i + 1) % n], hi[i]))
        bm.faces.new(hi)
    me = bpy.data.meshes.new(pc.name + '_centik')
    bm.to_mesh(me)
    bm.free()
    return me


def mesh_report(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    nonman = sum(1 for e in bm.edges if not e.is_manifold)
    vol = bm.calc_volume()
    bm.free()
    return nonman, vol


def build_object(pc):
    coll = bpy.context.scene.collection
    plate = bpy.data.objects.new(pc.name, plate_mesh(pc))
    tool = bpy.data.objects.new(pc.name + '_bumps', bumps_mesh(pc))
    cutter = bpy.data.objects.new(pc.name + '_centik', notches_mesh(pc))
    coll.objects.link(plate)
    coll.objects.link(tool)
    coll.objects.link(cutter)
    plate_vol = mesh_report(plate.data)[1]
    result = None
    for solver in ('MANIFOLD', 'EXACT'):
        mod = plate.modifiers.new('birlesim', 'BOOLEAN')
        mod.operation = 'UNION'
        mod.object = tool
        try:
            mod.solver = solver
        except TypeError:
            plate.modifiers.remove(mod)
            continue
        cut = plate.modifiers.new('centik', 'BOOLEAN')
        cut.operation = 'DIFFERENCE'
        cut.object = cutter
        cut.solver = solver
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(plate.evaluated_get(dg))
        plate.modifiers.remove(cut)
        plate.modifiers.remove(mod)
        nonman, vol = mesh_report(me)
        if nonman == 0 and vol > plate_vol:
            result = (me, solver, vol)
            break
        bpy.data.meshes.remove(me)
    assert result, pc.name + ': boolean birlesim basarisiz'
    me, solver, vol = result
    old = plate.data
    plate.data = me
    me.name = pc.name
    bpy.data.meshes.remove(old)
    bpy.data.objects.remove(tool)
    bpy.data.objects.remove(cutter)
    return plate, solver, vol


# ---------------------------------------------------------------------------
# Disa aktarim ve onizleme
# ---------------------------------------------------------------------------
def export_stl(obj, path):
    for o in bpy.context.scene.objects:
        o.select_set(o == obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True, apply_modifiers=True,
                          ascii_format=False, global_scale=1.0, use_scene_unit=False,
                          forward_axis='Y', up_axis='Z')


def bbox(obj):
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    zs = [v.co.z for v in obj.data.vertices]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def render(objs, path, center, size, tilt=28.0, res=(1800, 1200)):
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.film_transparent = False
    sh = scene.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'OBJECT'
    sh.show_cavity = True
    sh.cavity_type = 'BOTH'
    sh.show_shadows = True
    sh.background_type = 'VIEWPORT'
    sh.background_color = (0.93, 0.91, 0.87)
    cam = scene.camera
    if cam is None:
        cam = bpy.data.objects.new('kamera', bpy.data.cameras.new('kamera'))
        scene.collection.objects.link(cam)
        scene.camera = cam
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = size
    cam.data.clip_end = 5000
    t = math.radians(tilt)
    cam.location = (center[0], center[1] - 600 * math.sin(t), 600 * math.cos(t))
    cam.rotation_euler = (t, 0, 0)
    for o in scene.objects:
        if o.type == 'MESH':
            o.hide_render = o not in objs
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.abspath(argv[0]) if argv else here
    stl_dir = os.path.join(out, 'stl')
    os.makedirs(stl_dir, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    pieces = make_pieces()
    objs = []
    for pc in pieces:
        obj, solver, vol = build_object(pc)
        (x0, y0, z0), (x1, y1, z1) = bbox(obj)
        fits = (x1 - x0) <= BED and (y1 - y0) <= BED
        print('PARCA %-12s %6.1f x %6.1f x %4.1f mm  kabartma=%3d  centik=%2d  hacim=%7.1f cm3  solver=%s  tabla=%s'
              % (pc.name, x1 - x0, y1 - y0, z1 - z0, len(pc.bumps), len(pc.notches), vol / 1000, solver,
                 'OK' if fits else 'SIGMIYOR'))
        for s in pc.skipped:
            print('  atlandi:', s)
        export_stl(obj, os.path.join(stl_dir, pc.name + '.stl'))
        obj.color = (0.95, 0.45, 0.12, 1.0)
        objs.append(obj)

    # onizleme icin yerlestir (STL'ler kendi koordinatlariyla zaten disa aktarildi)
    layout = {
        'cetvel_20cm': (-108, -150),
        'gonye_45': (-215, -95),
        'gonye_30_60': (-45, -95),
        'iletki_180': (165, -80),
    }
    for o in objs:
        o.location = (*layout.get(o.name, (0, 0)), 0)
    render(objs, os.path.join(out, 'onizleme.png'), center=(25, -40), size=540)
    ruler = next(o for o in objs if o.name.startswith('cetvel'))
    render([ruler], os.path.join(out, 'onizleme_cetvel_detay.png'),
           center=(ruler.location.x + 60, ruler.location.y + 10), size=130, tilt=35)
    prot = next(o for o in objs if o.name.startswith('iletki'))
    render([prot], os.path.join(out, 'onizleme_iletki.png'),
           center=(prot.location.x, prot.location.y + 45), size=240, tilt=20)
    bpy.context.preferences.filepaths.save_version = 0   # .blend1 yedegi olusturma
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, 'geometri_seti.blend'))


main()
