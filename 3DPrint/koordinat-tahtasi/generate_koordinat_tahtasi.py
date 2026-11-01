"""
Dokunsal koordinat ve geometri tahtasi (gorme engelli ve az goren ogrenciler icin) - STL ureteci.

Calistirma:
  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
      --python generate_koordinat_tahtasi.py -- [cikti_klasoru]

Parcalar:
  koordinat_tahtasi : 204 x 186 x 5 mm tahta. -5 ... +5 arasinda 11 x 11 delik, delikler arasi 15 mm.
                      Eksenler deliklerin arasinda kabartma cizgilerdir; arti uclarinda ok ve buyuk
                      punto "x", "y" vardir. Orijin, dort yanindan cizgi cikan tek deliktir: parmak
                      eksen cizgisini izleyip delikleri sayarak noktaya gider.
                      x icin altta, y icin solda her tam sayida buyuk punto rakam; -5, 0 ve 5'te
                      Braille. Etiketler izgaranin disindadir; pim ve lastik ustlerini kapatmaz.
  pim_yuvarlak      : Yuvarlak basli pim. Delige gecer, basinin altindaki boyna lastik takilir
                      (geometri tahtasi). Koordinat duzleminde nokta isaretler.
  pim_kare          : Kare basli pim; baska renkte basilir. Iki nokta kumesini ya da bir seklin
                      koseleriyle ayri noktalari dokunarak ayirmak icin.
  pim_deneme        : 4,8 / 4,9 / 5,0 / 5,1 / 5,2 mm bes delik; ustunde 1-5 nokta, altinda olcu.
                      Pim hangi delikte dik ve sikica durup elle rahat cikiyorsa betikteki HOLE_D
                      o olcu yapilip tahta yeniden uretilir.

Pimler basi tablaya gelecek sekilde ters basilir; destek gerekmez. Pimin flansi deligin havsasini
kapatir, eksen cizgileri ve etiketler flansin disinda kalir: eksen uzerindeki noktalara da pim
dik oturur.
Iki renkli baski: tahtada ve deneme parcasinda 5,0 mm'de duraklatip filament degistirin.
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ortak'))
from dokunsal import (BAR, BR_DOT, BR_PITCH, DOT_S, MARGIN, SINK, Piece,  # noqa: E402
                      add_bump, add_loft, add_prism, boolean_solid, braille_signed, braille_width, build_object, circle, convex_hull,
                      countersunk_holes, export_stl, mesh_of, render, report, reset_scene,
                      rounded, save_blend, text_shape, v2)
import bmesh  # noqa: E402
import bpy  # noqa: E402

# ---------------------------------------------------------------------------
# Olculer (mm). Orijin tahtanin orijini; z = 0 tahtanin alti.
# ---------------------------------------------------------------------------
N = 5                   # -N ... +N
P = 15.0                # delik araligi (bir birim)
G = N * P               # izgaranin yari genisligi
T = 5.0                 # tahta kalinligi (pim bu kadar derine girer)
HOLE_D = 5.0            # pim deligi capi (pim_deneme ile secilir)
CS_DEPTH = 0.6          # deligin ustundeki 45 derecelik havsa: pimin ucu delige kayar
TEST_DS = (4.8, 4.9, 5.0, 5.1, 5.2)
NUM_H = 4.6             # buyuk punto rakam yuksekligi (~18 punto, sayi dogrusuyla ayni)

# Pim (kullanim konumunda; z = 0 tahtanin ustu, govde asagi gider)
SHANK_D = 4.8           # delige giren govde
SHANK_L = T - 0.6       # govde tahtanin altina ulasmaz (ilk katmanlardaki daralmaya degmez)
SHANK_TIP = 0.5         # govde ucundaki pah
FLANGE_D, FLANGE_T = 8.0, 0.8   # tahtaya oturan flans
POST_D = 6.0            # lastigin takildigi boyun
POST_Z0 = FLANGE_T + (FLANGE_D - POST_D) / 2   # flans konisinin ustu (45 derece: ters basilinca)
POST_Z1 = POST_Z0 + 7.0                         # boyun boyu 7 mm: uc-dort lastik ust uste
HEAD_T = 2.5
HEAD_TOP = POST_Z1 + HEAD_T
HEAD_D = 10.0           # yuvarlak bas
HEAD_SQ, HEAD_RC = 9.0, 1.5     # kare bas (kenar, kose yaricapi)
HEAD_CH = 0.6           # basin ust kenarindaki pah

# Tahta yerlesimi
CS_R = HOLE_D / 2 + CS_DEPTH
CLR = max(CS_R + MARGIN, FLANGE_D / 2 + 0.4)   # delik merkezinden kabartmalara en az uzaklik
A = CLR + BAR[0] + 0.05                         # eksen cizgisinin delik merkezine yakin ucu
ARROW_L, ARROW_W = 7.0, 3.5                     # eksen oku (boy, yari genislik)
ARROW_BASE = G + A + 4.5
ARROW_TIP = ARROW_BASE + ARROW_L
BR_GAP_V, BR_GAP_H = 2.0, 3.0   # Braille ile buyuk punto rakam arasi (alt alta / yan yana);
                                # Braille okuyan parmak rakama carpmasin
Y_NUM_X = -(G + CLR + NUM_H / 2 + 0.3)          # x rakamlarinin merkezi
Y_BR_X = Y_NUM_X - NUM_H / 2 - BR_GAP_V - BR_DOT[0] - BR_PITCH   # x Braille'inin orta sirasi
X_NUM_R = -(G + CLR + 0.3)                      # y rakamlarinin sag kenari
BRAILLE_AT = (-N, 0, N)


def label(k):
    return '−%d' % -k if k < 0 else '%d' % k


def arrow(u):
    """u yonundeki eksenin ucundaki ok (koseleri yuvarlatilmis ucgen)."""
    n = v2(-u.y, u.x)
    tri = [u * ARROW_BASE - n * ARROW_W, u * ARROW_TIP, u * ARROW_BASE + n * ARROW_W]
    return rounded(tri, 0.6)


# ---------------------------------------------------------------------------
# Tahta
# ---------------------------------------------------------------------------
def make_board():
    widths = {k: text_shape(label(k), NUM_H)['w'] for k in range(-N, N + 1)}
    br_right = X_NUM_R - max(widths.values()) - BR_GAP_H - BR_DOT[0]   # y Braille'i saga dayali
    x_min = math.floor(br_right - braille_width(braille_signed(-N)) - BR_DOT[0] - MARGIN - 0.2)
    y_min = math.floor((Y_BR_X - BR_PITCH - BR_DOT[0] - MARGIN - 0.2) * 2) / 2
    edge = math.ceil((ARROW_TIP + 2.0) * 2) / 2
    outer = rounded([v2(x_min, y_min), v2(edge, y_min), v2(edge, edge), v2(x_min, edge)], 4.0)

    centers = [v2(P * i, P * j) for i in range(-N, N + 1) for j in range(-N, N + 1)]
    keep = [circle(c, CLR - MARGIN, 32) for c in centers]
    pc = Piece('koordinat_tahtasi', outer, thickness=T, keepout=keep)
    pc.mesh_cut.append(countersunk_holes(centers, HOLE_D, CS_DEPTH, T))

    # Eksenler: delikler arasinda cizgi, arti ucta ok
    arrows = []
    for u, name in ((v2(1, 0), 'x'), (v2(0, 1), 'y')):
        for i in range(-N, N):
            pc.add(u * (P * i + A), u * (P * (i + 1) - A), BAR, '%s ekseni %d' % (name, i))
        pc.add(u * (G + A), u * (ARROW_BASE + 0.6), BAR, '%s ekseni ok' % name)
        tri = arrow(u)
        arrows.append(tri)
        pc.mesh_add.append(lambda bm, tri=tri: add_prism(bm, tri, T - SINK, T + BAR[1]))
    pc.keepout.extend(arrows)          # yazilar oklara yaklasmasin
    mid = ARROW_BASE + ARROW_L / 2
    pc.add_text('x', v2(mid, -(ARROW_W + MARGIN + NUM_H / 2 + 0.5)), v2(0, 1), NUM_H, 'x etiketi')
    wy = text_shape('y', NUM_H)['w']
    pc.add_text('y', v2(-(ARROW_W + MARGIN + wy / 2 + 0.5), mid), v2(0, 1), NUM_H, 'y etiketi')

    # x: altta rakam ve Braille; y: solda rakam (saga dayali) ve Braille (saga dayali)
    for k in range(-N, N + 1):
        pc.add_text(label(k), v2(P * k, Y_NUM_X), v2(0, 1), NUM_H, 'x rakam %d' % k)
        pc.add_text(label(k), v2(X_NUM_R - widths[k] / 2, P * k), v2(0, 1), NUM_H, 'y rakam %d' % k)
    for k in BRAILLE_AT:
        cells = braille_signed(k)
        cx = v2(P * k, Y_BR_X)
        pc.add_braille(cells, lambda x, y, c=cx: c + v2(x, y), 'x braille %d' % k)
        cy = v2(br_right - braille_width(cells) / 2, P * k)
        pc.add_braille(cells, lambda x, y, c=cy: c + v2(x, y), 'y braille %d' % k)
    return pc


def make_test(pitch=16.0, x0=10.0):
    L = 2 * x0 + pitch * (len(TEST_DS) - 1)
    outer = rounded([v2(0, -10.5), v2(L, -10.5), v2(L, 9.5), v2(0, 9.5)], 3.0)
    centers = [v2(x0 + pitch * i, 0) for i in range(len(TEST_DS))]
    keep = [circle(c, d / 2 + CS_DEPTH, 32) for c, d in zip(centers, TEST_DS)]
    pc = Piece('pim_deneme', outer, thickness=T, keepout=keep)
    for c, d in zip(centers, TEST_DS):
        pc.mesh_cut.append(countersunk_holes([c], d, CS_DEPTH, T))
    r_max = max(TEST_DS) / 2 + CS_DEPTH
    y_dot = r_max + MARGIN + DOT_S[0] + 0.3
    y_num = -(r_max + MARGIN + NUM_H / 2 + 0.3)
    for i, (c, d) in enumerate(zip(centers, TEST_DS)):
        n = i + 1
        for j in range(n):
            pc.add(c + v2((j - (n - 1) / 2) * 2.8, y_dot), None, DOT_S, '%.1f nokta %d' % (d, j))
        pc.add_text(('%.1f' % d).replace('.', ','), c + v2(0, y_num), v2(0, 1), NUM_H, '%.1f yazi' % d)
    return pc


# ---------------------------------------------------------------------------
# Pim
# ---------------------------------------------------------------------------
def rsquare(h, rc, n=8):
    """Merkezli, yari kenari h, kose yaricapi rc olan kare (CCW, 4 * (n + 1) nokta)."""
    pts = []
    for k, (sx, sy) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):
        c = v2(sx * (h - rc), sy * (h - rc))
        for i in range(n + 1):
            t = math.radians(90 * k + 90 * i / n)
            pts.append(c + v2(math.cos(t), math.sin(t)) * rc)
    return pts


def make_pin(name, kind):
    rs = SHANK_D / 2
    body = [(rs - SHANK_TIP, -SHANK_L), (rs, -SHANK_L + SHANK_TIP), (rs, 0.0),
            (FLANGE_D / 2, 0.0), (FLANGE_D / 2, FLANGE_T), (POST_D / 2, POST_Z0),
            (POST_D / 2, POST_Z1 + 1.0)]
    base = mesh_of(name, lambda bm: add_loft(
        bm, [[(p.x, p.y, z) for p in circle(v2(0, 0), r, 64)] for r, z in body]))
    if kind == 'yuvarlak':
        def shape(d):
            return circle(v2(0, 0), HEAD_D / 2 - d, 64)
    else:
        def shape(d):
            return rsquare(HEAD_SQ / 2 - d, HEAD_RC - d)
    head = [(0.0, POST_Z1), (0.0, HEAD_TOP - HEAD_CH), (HEAD_CH, HEAD_TOP)]
    ops = [('UNION', mesh_of(name + '_bas', lambda bm: add_loft(
        bm, [[(p.x, p.y, z) for p in shape(d)] for d, z in head])))]
    obj, _, _ = boolean_solid(name, base, ops)
    return obj


# ---------------------------------------------------------------------------
# Yardimcilar
# ---------------------------------------------------------------------------
def transformed(src, name, fn):
    """src'nin kopyasi; her koseye fn(x, y, z) -> (x, y, z) uygulanir."""
    bm = bmesh.new()
    bm.from_mesh(src.data)
    for v in bm.verts:
        v.co = fn(*v.co)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def intersect_volume(a, b):
    tmp = transformed(a, '_kesisim', lambda x, y, z: (x, y, z))
    mod = tmp.modifiers.new('k', 'BOOLEAN')
    mod.operation, mod.object, mod.solver = 'INTERSECT', b, 'EXACT'
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bm = bmesh.new()
    bm.from_mesh(me)
    vol = bm.calc_volume()
    bm.free()
    bpy.data.objects.remove(tmp)
    bpy.data.meshes.remove(me)
    return vol


def band(name, pins, z):
    """Onizleme icin: pinlerin boyunlarina gecirilmis lastik."""
    hull = convex_hull([p for c in pins for p in circle(c, POST_D / 2 + 0.5, 24)])

    def fill(bm):
        for p0, p1 in zip(hull, hull[1:] + hull[:1]):
            add_bump(bm, p0, p1, 0.55, 0.55, z, n=12)
    obj = bpy.data.objects.new(name, mesh_of(name, fill))
    bpy.context.scene.collection.objects.link(obj)
    return obj


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.abspath(argv[0]) if argv else here
    stl_dir = os.path.join(out, 'stl')
    os.makedirs(stl_dir, exist_ok=True)

    reset_scene()
    objs = {}
    for pc in (make_board(), make_test()):
        obj, _, _ = build_object(pc)
        report(pc.name, obj, 'kabartma=%d yazi=%d' % (len(pc.bumps), len(pc.texts)))
        for s in pc.skipped:
            print('  atlandi:', s)
        export_stl(obj, os.path.join(stl_dir, pc.name + '.stl'))
        obj.color = (0.95, 0.93, 0.88, 1.0)
        objs[pc.name] = obj
    board = objs['koordinat_tahtasi']
    print('OLCU delik %.1f (havsa ustte %.1f), pim govdesi %.1f, flans %.1f, eksen cizgisi delik '
          'merkezinden %.2f..%.2f, ok ucu %.2f'
          % (HOLE_D, 2 * CS_R, SHANK_D, FLANGE_D, A, P - A, ARROW_TIP))

    pins = {}
    for kind in ('yuvarlak', 'kare'):
        name = 'pim_' + kind
        use = make_pin(name + '_kullanim', kind)
        printed = transformed(use, name, lambda x, y, z: (x, -y, HEAD_TOP - z))
        report(name, printed)
        export_stl(printed, os.path.join(stl_dir, name + '.stl'))
        printed.hide_render = True
        pins[kind] = (use, printed)
        # Eksen uzerindeki, kosedeki ve etiket yanindaki deliklerde pim tahtaya carpmamali
        for i, j in ((3, 0), (0, -5), (-5, -5), (5, 5)):
            probe = transformed(use, '_deneme', lambda x, y, z, i=i, j=j: (P * i + x, P * j + y, T + z + 0.01))
            vol = intersect_volume(probe, board)
            print('  %s (%d, %d) deliginde tahtayla kesisim = %.3f mm3' % (name, i, j, vol))
            m = probe.data
            bpy.data.objects.remove(probe)
            bpy.data.meshes.remove(m)

    # Onizleme: bir ucgen (yuvarlak pimler ve lastik) ve iki nokta (kare pimler)
    shown = [board]
    red, blue = (0.85, 0.2, 0.2, 1.0), (0.15, 0.4, 0.85, 1.0)
    tri = [(-4, -3), (2, -3), (-4, 2)]
    for kind, pts, col in (('yuvarlak', tri, red), ('kare', [(1, 3), (3, 1)], blue)):
        for i, j in pts:
            o = transformed(pins[kind][0], 'onizleme_%s_%d_%d' % (kind, i, j),
                            lambda x, y, z, i=i, j=j: (P * i + x, P * j + y, T + z))
            o.color = col
            shown.append(o)
    b = band('lastik', [v2(P * i, P * j) for i, j in tri], T + POST_Z0 + 2.5)
    b.color = (0.95, 0.75, 0.15, 1.0)
    shown.append(b)
    objs['pim_deneme'].hide_render = True
    render(shown, os.path.join(out, 'onizleme.png'), center=(-9, 2), size=262, tilt=28)
    render(shown, os.path.join(out, 'onizleme_detay.png'), center=(-78, -66), size=80, tilt=35)

    # Baski yonunde pimler ve deneme parcasi
    test = objs['pim_deneme']
    test.location = (-42, -30, 0)
    test.hide_render = False
    shown = [test]
    for k, (kind, col) in enumerate((('yuvarlak', red), ('kare', blue))):
        o = pins[kind][1]
        o.location = (-15 + 30 * k, 2, 0)
        o.color = col
        o.hide_render = False
        shown.append(o)
    render(shown, os.path.join(out, 'onizleme_pim.png'), center=(0, -12), size=100, tilt=35)
    for o in (test, *(p[1] for p in pins.values())):
        o.location = (0, 0, 0)
    save_blend(os.path.join(out, 'koordinat_tahtasi.blend'))


main()
