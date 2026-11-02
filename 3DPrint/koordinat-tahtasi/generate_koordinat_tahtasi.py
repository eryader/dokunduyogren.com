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
                      Pim hangi delikte dik ve sikica durup elle rahat cikiyorsa ortak/pim.py'deki
                      HOLE_D o olcu yapilip tahta yeniden uretilir.

Pim ve delik olculeri ortak/pim.py'dedir; yuzluk tablonun pimleri ve delikleri de aynidir.
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
from dokunsal import (BAR, BR_DOT, BR_PITCH, MARGIN, SINK, Piece,  # noqa: E402
                      add_bump, add_prism, braille_signed, braille_width, build_object, circle,
                      convex_hull, export_stl, mesh_of, render, report, reset_scene, rounded,
                      save_blend, text_shape, v2)
from pim import (BOARD_T as T, CLR, CS_DEPTH, CS_R, FLANGE_D, HOLE_D, POST_D,  # noqa: E402
                 POST_Z0, SHANK_D, check_pin_fit, hole_keepout, make_pin, make_pin_test,
                 pin_holes, printed_pin, transformed)
import bpy  # noqa: E402

# ---------------------------------------------------------------------------
# Olculer (mm). Orijin tahtanin orijini; z = 0 tahtanin alti.
# ---------------------------------------------------------------------------
N = 5                   # -N ... +N
P = 15.0                # delik araligi (bir birim)
G = N * P               # izgaranin yari genisligi
NUM_H = 4.6             # buyuk punto rakam yuksekligi (~18 punto, sayi dogrusuyla ayni)

# Tahta yerlesimi (pim ve delik olculeri ortak/pim.py'de; CLR delik merkezinden kabartmalara
# en az uzaklik)
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
    pc = Piece('koordinat_tahtasi', outer, thickness=T, keepout=hole_keepout(centers))
    pc.mesh_cut.append(pin_holes(centers))

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


# ---------------------------------------------------------------------------
# Onizleme
# ---------------------------------------------------------------------------
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
    for pc in (make_board(), make_pin_test(NUM_H)):
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
        printed = printed_pin(use, name, kind)
        report(name, printed)
        export_stl(printed, os.path.join(stl_dir, name + '.stl'))
        printed.hide_render = True
        pins[kind] = (use, printed)
        # Eksen uzerindeki, kosedeki ve etiket yanindaki deliklerde pim tahtaya carpmamali
        check_pin_fit(use, board, [(P * i, P * j) for i, j in ((3, 0), (0, -5), (-5, -5), (5, 5))], name)

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
