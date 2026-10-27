"""
Dokunsal materyal ortak kutuphanesi (Blender icinde calisir).

2B geometri, Braille, kabartma noktalar/cizgiler, buyuk punto kabartma yazi,
boolean birlesim, STL disa aktarim ve onizleme yardimcilari. Butun parcalar ayni
dokunsal kodlamayi kullansin diye olculer burada tek yerde tutulur.
"""
import bpy
import bmesh
import math
from mathutils import Vector

# ---------------------------------------------------------------------------
# Ortak dokunsal kodlama (mm)
# ---------------------------------------------------------------------------
TICK_OFF = 4.5          # olcek noktalarinin kenardan uzakligi
DOT_S = (0.9, 0.8)      # kucuk nokta (yaricap, yukseklik): 1 cm / 10 derece
DOT_L = (1.6, 1.0)      # buyuk nokta: 5 cm / 30 derece / baslangic isareti
BAR = (0.7, 0.9)        # cizgi (yari genislik, yukseklik): 10 cm / 90 derece
BAR_SPAN = (2.0, 8.0)   # cizginin kenardan baslangic / bitis uzakligi
BR_DOT = (0.75, 0.6)    # Braille noktasi (yaricap, yukseklik)
BR_PITCH = 2.5          # hucre ici nokta araligi
BR_CELL = 6.0           # hucre baslangiclari arasi
BR_OFF = 14.5           # olcek etiketlerinde Braille merkezinin kenardan uzakligi
LP_H = 0.8              # buyuk punto yazinin kabarma yuksekligi
NOTCH_R = 0.5           # kenar centigi yaricapi (1.0 genis, 0.5 derin; ruler-01 ile ayni)
MARGIN = 0.8            # kabartma ile parca kenari arasindaki en az bosluk
GAP = 0.5               # iki kabartma arasindaki en az bosluk
SINK = 0.3              # kabartmalarin plakaya gomulme payi (boolean birlesim icin)
BED = 220.0             # tabla boyutu (Ender 3 S1)
FONT_PATH = '/System/Library/Fonts/Supplemental/Arial Bold.ttf'

# Turk Braille (6 nokta). Rakamlar sayi isaretinden sonra a-j harfleridir.
BRAILLE_NUM_SIGN = (3, 4, 5, 6)
BRAILLE_DIGITS = {
    '1': (1,), '2': (1, 2), '3': (1, 4), '4': (1, 4, 5), '5': (1, 5),
    '6': (1, 2, 4), '7': (1, 2, 4, 5), '8': (1, 2, 5), '9': (2, 4), '0': (2, 4, 5),
}
# Alt rakamlar: ust rakamlarin bir sira asagi kaydirilmis hali (kesir paydasi icin).
BRAILLE_LOWER_DIGITS = {
    '1': (2,), '2': (2, 3), '3': (2, 5), '4': (2, 5, 6), '5': (2, 6),
    '6': (2, 3, 5), '7': (2, 3, 5, 6), '8': (2, 3, 6), '9': (3, 5), '0': (3, 5, 6),
}
BRAILLE_LETTERS = {
    'a': (1,), 'b': (1, 2), 'c': (1, 4), 'ç': (1, 6), 'd': (1, 4, 5), 'e': (1, 5),
    'f': (1, 2, 4), 'g': (1, 2, 4, 5), 'ğ': (1, 2, 6), 'h': (1, 2, 5), 'ı': (3, 5),
    'i': (2, 4), 'j': (2, 4, 5), 'k': (1, 3), 'l': (1, 2, 3), 'm': (1, 3, 4),
    'n': (1, 3, 4, 5), 'o': (1, 3, 5), 'ö': (2, 4, 6), 'p': (1, 2, 3, 4), 'r': (1, 2, 3, 5),
    's': (2, 3, 4), 'ş': (1, 4, 6), 't': (2, 3, 4, 5), 'u': (1, 3, 6), 'ü': (1, 2, 5, 6),
    'v': (1, 2, 3, 6), 'y': (1, 3, 4, 5, 6), 'z': (1, 3, 5, 6),
}


def braille_number(text):
    return [BRAILLE_NUM_SIGN] + [BRAILLE_DIGITS[c] for c in text]


def braille_fraction(p, q):
    """Pay normal rakam, payda alt rakam: 1/4 -> sayi isareti + 1 + alt 4.
    Turk Braille matematik gosterimi icin ogretmen onayi bekleniyor."""
    return ([BRAILLE_NUM_SIGN] + [BRAILLE_DIGITS[c] for c in str(p)]
            + [BRAILLE_LOWER_DIGITS[c] for c in str(q)])


def braille_word(word):
    low = word.replace('I', 'ı').replace('İ', 'i').lower()
    return [BRAILLE_LETTERS[c] for c in low]


def braille_layout(cells):
    """Hucre listesini (x, y) nokta konumlarina cevir; x okuma yonu, y yukari, merkezli."""
    width = (len(cells) - 1) * BR_CELL + BR_PITCH
    dots = []
    for ci, cell in enumerate(cells):
        x0 = -width / 2 + ci * BR_CELL
        for d in cell:
            col = 0 if d <= 3 else 1
            row = (d - 1) % 3
            dots.append((x0 + col * BR_PITCH, (1 - row) * BR_PITCH))
    return dots


def braille_width(cells):
    return (len(cells) - 1) * BR_CELL + BR_PITCH


# ---------------------------------------------------------------------------
# 2B geometri
# ---------------------------------------------------------------------------
def v2(x, y):
    return Vector((x, y))


def polar(r, deg):
    t = math.radians(deg)
    return v2(math.cos(t), math.sin(t)) * r


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


def convex_hull(points):
    pts = sorted(set((round(p.x, 6), round(p.y, 6)) for p in points))
    if len(pts) < 3:
        return [v2(*p) for p in pts]

    def half(seq):
        h = []
        for p in seq:
            while len(h) >= 2 and ((h[-1][0] - h[-2][0]) * (p[1] - h[-2][1])
                                   - (h[-1][1] - h[-2][1]) * (p[0] - h[-2][0])) <= 0:
                h.pop()
            h.append(p)
        return h
    lower, upper = half(pts), half(pts[::-1])
    return [v2(*p) for p in lower[:-1] + upper[:-1]]


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
# Buyuk punto yazi (az gorenler icin kabartma)
# ---------------------------------------------------------------------------
_font = None
_text_cache = {}


def _load_font():
    global _font
    if _font is None:
        try:
            _font = bpy.data.fonts.load(FONT_PATH, check_existing=True)
        except RuntimeError:
            _font = bpy.data.fonts.get('Bfont Regular') or bpy.data.curves.new('_', 'FONT').font
    return _font


def text_shape(text, height):
    """Yazinin agini olustur: xy merkezli, sinir kutusu yuksekligi = height, z 0..1."""
    key = (text, height)
    if key in _text_cache:
        return _text_cache[key]
    cu = bpy.data.curves.new('yazi', 'FONT')
    cu.body = text
    cu.font = _load_font()
    cu.size = 1.0
    cu.extrude = 0.5
    ob = bpy.data.objects.new('yazi', cu)
    bpy.context.scene.collection.objects.link(ob)
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    zs = [v.co.z for v in bm.verts]
    s = height / (max(ys) - min(ys))
    cx, cy, z0, dz = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, min(zs), max(zs) - min(zs)
    verts = [((v.co.x - cx) * s, (v.co.y - cy) * s, (v.co.z - z0) / dz) for v in bm.verts]
    idx = {v: i for i, v in enumerate(bm.verts)}
    faces = [[idx[v] for v in f.verts] for f in bm.faces]
    shape = {'verts': verts, 'faces': faces, 'w': (max(xs) - min(xs)) * s, 'h': height}
    bm.free()
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    bpy.data.meshes.remove(me)
    _text_cache[key] = shape
    return shape


# ---------------------------------------------------------------------------
# Parca: dis hat + delikler + kabartmalar + yazilar + silindir ekle/cikar
# ---------------------------------------------------------------------------
class Piece:
    def __init__(self, name, outer, holes=(), thickness=3.0, keepout=()):
        self.name = name
        self.outer = ccw(outer)
        self.holes = [ccw(h) for h in holes]
        self.keepout = [ccw(k) for k in keepout]   # kabartma konmayacak bolgeler (cep vb.)
        self.thickness = thickness
        self.bumps = []      # (p0, p1, r, h)
        self.texts = []      # (shape, center, U, up)
        self.text_pts = []   # yazi sinir kutusu ornekleri (carpisma kontrolu)
        self.notches = []    # kenar uzerindeki centik merkezleri
        self.cyl_add = []    # (merkez, r, z0, z1) eklenen silindirler
        self.cyl_cut = []    # (merkez, r, z0, z1) oyulan silindirler
        self.skipped = []

    def _free(self, p, clearance):
        if not inside(p, self.outer):
            return False
        if any(inside(p, h) for h in self.holes + self.keepout):
            return False
        return min(loop_dist(p, lp) for lp in [self.outer] + self.holes + self.keepout) >= clearance

    def _fits(self, p0, p1, r):
        pts = samples(p0, p1)
        if not all(self._free(p, r + MARGIN) for p in pts):
            return False
        for q0, q1, rq, _ in self.bumps:
            if min(seg_dist(p, q0, q1) for p in pts) < r + rq + GAP:
                return False
        return all(seg_dist(t, p0, p1) >= r + GAP for t in self.text_pts)

    def add_group(self, items):
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
        if self.add_group([(p0, p1, size[0], size[1])]):
            return True
        self.skipped.append(label)
        return False

    def add_braille(self, cells, place, label, nudge=6.0):
        """place(x, y) -> dunya noktasi; x okuma yonu, y yukari. Sigmazsa okuma yonunde kaydir."""
        dots = braille_layout(cells)
        for k in range(int(nudge * 2) + 1):
            dx = (k + 1) // 2 * 0.5 * (-1 if k % 2 else 1)
            items = [(place(x + dx, y), None, BR_DOT[0], BR_DOT[1]) for x, y in dots]
            if self.add_group(items):
                return True
        self.skipped.append(label)
        return False

    def add_text(self, text, center, up, height, label):
        """Buyuk punto kabartma yazi; up yazinin yukari yonu, okuma yonu up'in sagi."""
        shape = text_shape(text, height)
        up = up.normalized()
        U = v2(up.y, -up.x)
        w, h = shape['w'], shape['h']
        nx, ny = max(2, math.ceil(w)), max(2, math.ceil(h))
        pts = [center + U * (-w / 2 + w * i / nx) + up * (-h / 2 + h * j / ny)
               for i in range(nx + 1) for j in range(ny + 1)]
        ok = all(self._free(p, MARGIN) for p in pts) and all(
            seg_dist(p, q0, q1) >= rq + GAP for p in pts for q0, q1, rq, _ in self.bumps)
        if not ok:
            self.skipped.append(label)
            return False
        self.texts.append((shape, center, U, up))
        self.text_pts.extend(pts)
        return True


def linear_scale(pc, origin, mdir, inward, kmin, kmax, read, labels=True):
    """origin'den mdir yonunde her 10 mm'de bir isaret + centik; Braille 5'in katlarinda."""
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
            pc.add_braille(braille_number(str(k)), lambda x, y, c=c: c + read * x + inward * y,
                           tag + ' braille')


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
    bmesh.ops.translate(bm, vec=(0, 0, pc.thickness), verts=top)
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


def add_prism(bm, pts, z0, z1):
    lo = [bm.verts.new((p.x, p.y, z0)) for p in pts]
    hi = [bm.verts.new((p.x, p.y, z1)) for p in pts]
    n = len(pts)
    bm.faces.new(lo[::-1])
    for i in range(n):
        bm.faces.new((lo[i], lo[(i + 1) % n], hi[(i + 1) % n], hi[i]))
    bm.faces.new(hi)


def add_bump(bm, p0, p1, r, h, z0, n=24):
    """Kubbe (p0 == p1) ya da kapsul; alt kismi SINK kadar plakaya gomulu."""
    thetas = [math.radians(a) for a in (0, 22, 40, 55, 67, 77, 85)]
    profile = [(r, z0 - SINK)] + [(r * math.cos(t), z0 + h * math.sin(t)) for t in thetas]
    rings = [[bm.verts.new((p.x, p.y, z)) for p in ring(p0, p1, rho, n)] for rho, z in profile]
    bm.faces.new(rings[0][::-1])
    for lo, hi in zip(rings, rings[1:]):
        m = len(lo)
        for i in range(m):
            bm.faces.new((lo[i], lo[(i + 1) % m], hi[(i + 1) % m], hi[i]))
    bm.faces.new(rings[-1])


def add_text_mesh(bm, shape, center, U, up, z0):
    vs = []
    for x, y, zn in shape['verts']:
        p = center + U * x + up * y
        vs.append(bm.verts.new((p.x, p.y, z0 - SINK + zn * (LP_H + SINK))))
    for f in shape['faces']:
        bm.faces.new([vs[i] for i in f])


def tool_mesh(pc):
    bm = bmesh.new()
    top = pc.thickness
    for p0, p1, r, h in pc.bumps:
        add_bump(bm, p0, p1, r, h, top)
    for shape, center, U, up in pc.texts:
        add_text_mesh(bm, shape, center, U, up, top)
    for c, r, z0, z1 in pc.cyl_add:
        add_prism(bm, circle(c, r, 48), z0, z1)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(pc.name + '_ekle')
    bm.to_mesh(me)
    bm.free()
    return me


def cutter_mesh(pc):
    bm = bmesh.new()
    for c in pc.notches:
        add_prism(bm, circle(c, NOTCH_R, 24), -1.0, pc.thickness + 2.0)
    for c, r, z0, z1 in pc.cyl_cut:
        add_prism(bm, circle(c, r, 96), z0, z1)
    me = bpy.data.meshes.new(pc.name + '_oy')
    bm.to_mesh(me)
    bm.free()
    return me


def mesh_report(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    nonman = sum(1 for e in bm.edges if not e.is_manifold)
    vol = bm.calc_volume()
    # ayrik govde sayisi
    seen, shells = set(), 0
    for f in bm.faces:
        if f.index in seen:
            continue
        shells += 1
        stack = [f]
        seen.add(f.index)
        while stack:
            g = stack.pop()
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index)
                        stack.append(h)
    bm.free()
    return nonman, vol, shells


def build_object(pc):
    """Plaka - (centik + oyma) + (kabartma + yazi + ek silindir). Tek, kapali govde dondurur."""
    coll = bpy.context.scene.collection
    plate = bpy.data.objects.new(pc.name, plate_mesh(pc))
    coll.objects.link(plate)
    helpers = []
    ops = []
    if pc.notches or pc.cyl_cut:
        cut = bpy.data.objects.new(pc.name + '_oy', cutter_mesh(pc))
        helpers.append(cut)
        ops.append(('DIFFERENCE', cut))
    if pc.bumps or pc.texts or pc.cyl_add:
        add = bpy.data.objects.new(pc.name + '_ekle', tool_mesh(pc))
        helpers.append(add)
        ops.append(('UNION', add))
    for h in helpers:
        coll.objects.link(h)
    result = None
    for solver in ('MANIFOLD', 'EXACT'):
        mods = []
        try:
            for op, ob in ops:
                mod = plate.modifiers.new(op.lower(), 'BOOLEAN')
                mods.append(mod)
                mod.operation = op
                mod.object = ob
                mod.solver = solver
        except TypeError:
            for mod in mods:
                plate.modifiers.remove(mod)
            continue
        me = bpy.data.meshes.new_from_object(plate.evaluated_get(bpy.context.evaluated_depsgraph_get()))
        for mod in mods:
            plate.modifiers.remove(mod)
        nonman, vol, shells = mesh_report(me)
        if nonman == 0 and vol > 0 and shells == 1:
            result = (me, solver, vol)
            break
        print('  %s: %s cozumu basarisiz (acik kenar=%d, govde=%d)' % (pc.name, solver, nonman, shells))
        bpy.data.meshes.remove(me)
    assert result, pc.name + ': boolean birlesim basarisiz'
    me, solver, vol = result
    old = plate.data
    plate.data = me
    me.name = pc.name
    bpy.data.meshes.remove(old)
    for h in helpers:
        bpy.data.objects.remove(h)
    return plate, solver, vol


def merge_objects(name, placed):
    """placed: [(obj, (dx, dy), aci_derece)] -> tek nesne (ayri govdeler)."""
    bm = bmesh.new()
    for obj, (dx, dy), deg in placed:
        t = math.radians(deg)
        c, s = math.cos(t), math.sin(t)
        tmp = bmesh.new()
        tmp.from_mesh(obj.data)
        for v in tmp.verts:
            x, y = v.co.x, v.co.y
            v.co.x, v.co.y = c * x - s * y + dx, s * x + c * y + dy
        me = bpy.data.meshes.new('_tmp')
        tmp.to_mesh(me)
        tmp.free()
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    return obj


# ---------------------------------------------------------------------------
# Disa aktarim, rapor ve onizleme
# ---------------------------------------------------------------------------
def reset_scene():
    global _font
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _font = None
    _text_cache.clear()


def bbox(obj):
    vs = obj.data.vertices
    return ((min(v.co.x for v in vs), min(v.co.y for v in vs), min(v.co.z for v in vs)),
            (max(v.co.x for v in vs), max(v.co.y for v in vs), max(v.co.z for v in vs)))


def report(name, obj, extra=''):
    (x0, y0, z0), (x1, y1, z1) = bbox(obj)
    nonman, vol, shells = mesh_report(obj.data)
    fits = (x1 - x0) <= BED and (y1 - y0) <= BED
    print('PARCA %-14s %6.1f x %6.1f x %4.1f mm  hacim=%6.1f cm3 (~%3.0f g PLA)  govde=%2d  acik kenar=%d  tabla=%s  %s'
          % (name, x1 - x0, y1 - y0, z1 - z0, vol / 1000, vol / 1000 * 1.24, shells, nonman,
             'OK' if fits else 'SIGMIYOR', extra))


def export_stl(obj, path):
    for o in bpy.context.scene.objects:
        o.select_set(o == obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True, apply_modifiers=True,
                          ascii_format=False, global_scale=1.0, use_scene_unit=False,
                          forward_axis='Y', up_axis='Z')


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


def save_blend(path):
    bpy.context.preferences.filepaths.save_version = 0   # .blend1 yedegi olusturma
    bpy.ops.wm.save_as_mainfile(filepath=path)
