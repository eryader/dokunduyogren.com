"""
Dokunsal sutun grafik tahtasi (gorme engelli ve az goren ogrenciler icin) - STL ureteci.

Calistirma:
  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
      --python generate_sutun_grafik.py -- [cikti_klasoru]

Parcalar:
  sutun_grafik     : Alti kategori, her kategoride yan yana iki sutun delik (ikili sutun grafigi icin),
                     0'dan 10'a degerler. Delikler 10 mm arayla dizilir: sutuna alttan uste takilan
                     isaret pimleri bir cubuk olur, en ustteki pim degeri gosterir. Solda her degerde
                     Braille ve buyuk punto rakam. Kategoriler arasindaki bosluklarda her degerin
                     hizasinda kisa cizgi vardir: parmak cubugun ustundeki pimden sola kayarak degeri
                     bulur. Altta her kategori, ustte baslik ve iki aciklama (lejant) icin cerceveli
                     bos etiket alani; aciklama alanlarinda dizinin pimini gosteren birer delik.
  kare_isaret_pimi : Ikinci veri dizisi icin kare basli isaret pimi (ortak/pim.py, 'isaret_kare').
                     Birinci dizinin yuvarlak isaret pimi yuzluk tablonunkidir.

Delikler ve pimler koordinat tahtasi ve yuzluk tabloyla aynidir (ortak/pim.py); delik olcusu
orada secilir. Iki pim de, kare pimin kosesi hangi yone donerse donsun, 10 mm yanindaki pime ve
tahtadaki kabartmalara degmez. Koordinat tahtasinin uzun pimlerinin basi 10 mm oldugu icin yan
yana deliklere sigmaz.
Iki renkli baski: tahtada 5,0 mm'de duraklatip filament degistirin.
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ortak'))
from dokunsal import (BAR, BR_DOT, GAP, SINK, Piece, braille_number,  # noqa: E402
                      braille_width, build_object, export_stl, mesh_of, render, report,
                      reset_scene, rounded, save_blend, text_shape, v2)
from pim import (BOARD_T as T, CLR, HOLE_D, MARK_SQ_R, check_pin_fit, hole_keepout,  # noqa: E402
                 intersect_volume, make_pin, pin_holes, printed_pin, transformed)
import bpy  # noqa: E402

# ---------------------------------------------------------------------------
# Olculer (mm). z = 0 tahtanin alti; x = 0 tahtanin sol, y = 0 alt kenari.
# ---------------------------------------------------------------------------
K = 10                  # en buyuk deger
NCAT = 6                # kategori sayisi
P = 10.0                # deger araligi ve bir kategorideki iki sutun arasi (Braille satir araligi)
G = 29.0                # kategori genisligi
NUM_H = 4.6             # buyuk punto rakam yuksekligi (diger araclarla ayni)
E = 3.0                 # kenar boslugu
BR_GAP_H = 3.0          # Braille ile buyuk punto rakam arasi
LBL_H = 16.0            # etiket cercevesinin yuksekligi (cizgi ortasindan): 12 mm Braille bandi sigar
LG_W = 40.0             # aciklama cercevesinin genisligi (delik + etiket)
FR_GAP = 5.0            # yan yana iki cerceve arasi
FR_RC = 2.0             # cerceve kose yaricapi (cizgi ortasindan)
W = BAR[0]              # cizgilerin yari genisligi
# Kategoriler arasi cizgi deliklerden bu kadar uzakta biter (CLR: pim basi ve havsa)
DASH_IN = CLR + W + 0.05

BR_W = braille_width(braille_number(str(K)))
BR_RIGHT = E + BR_DOT[0] + BR_W                    # Braille etiketleri saga dayali
TICK_X0 = 2 * W + GAP + 0.05                       # y eksenine en yakin cizgi ile eksen arasi


def layout():
    """Yazi genisliklerine bagli yerlesim olculeri."""
    widths = {k: text_shape(str(k), NUM_H)['w'] for k in range(K + 1)}
    x_num_r = BR_RIGHT + BR_DOT[0] + BR_GAP_H + max(widths.values())    # rakamlar saga dayali
    x_ax = x_num_r + W + GAP + 0.8
    fr_y0 = E + W                                   # alttaki etiket cercevelerinin alt cizgisi
    y_ax = fr_y0 + LBL_H + 3.5
    top_y0 = y_ax + P * K + 7.5                     # ustteki cercevelerin alt cizgisi
    right = x_ax + NCAT * G + 2.2
    top = top_y0 + LBL_H + W + E
    return dict(widths=widths, x_num_r=x_num_r, x_ax=x_ax, fr_y0=fr_y0, y_ax=y_ax,
                top_y0=top_y0, right=right, top=top)


L = {}


def slot_x(s):
    return L['x_ax'] + (s + 0.5) * G


def col_x(s, side):
    """side 0: soldaki (yuvarlak pimler), 1: sagdaki (kare pimler) sutun."""
    return slot_x(s) + (side - 0.5) * P


def row_y(k):
    return L['y_ax'] + P * k


def hole(s, side, k):
    return v2(col_x(s, side), row_y(k))


def rrect(x0, y0, x1, y1, rc, n=6):
    """Koseleri rc yaricapla yuvarlatilmis dikdortgen (CCW)."""
    pts = []
    for q, (cx, cy) in enumerate(((x1 - rc, y1 - rc), (x0 + rc, y1 - rc), (x0 + rc, y0 + rc),
                                  (x1 - rc, y0 + rc))):
        for i in range(n + 1):
            t = math.radians(90 * q + 90 * i / n)
            pts.append(v2(cx + rc * math.cos(t), cy + rc * math.sin(t)))
    return pts


def frame_fill(boxes):
    """mesh_add icin: her kutunun cizgi ortasindan W kadar iki yana tasan duz ustlu cerceve."""
    def fill(bm):
        for x0, y0, x1, y1 in boxes:
            outer = rrect(x0 - W, y0 - W, x1 + W, y1 + W, FR_RC + W)
            inner = rrect(x0 + W, y0 + W, x1 - W, y1 - W, FR_RC - W)
            n = len(outer)
            zs = (T - SINK, T + BAR[1])
            ob, ot = ([bm.verts.new((p.x, p.y, z)) for p in outer] for z in zs)
            ib, it = ([bm.verts.new((p.x, p.y, z)) for p in inner] for z in zs)
            for i in range(n):
                j = (i + 1) % n
                bm.faces.new((ob[i], ob[j], ot[j], ot[i]))
                bm.faces.new((it[i], it[j], ib[j], ib[i]))
                bm.faces.new((ot[i], ot[j], it[j], it[i]))
                bm.faces.new((ib[i], ib[j], ob[j], ob[i]))
    return fill


# ---------------------------------------------------------------------------
# Tahta
# ---------------------------------------------------------------------------
def make_board():
    L.update(layout())
    x_ax, y_ax, right, top = L['x_ax'], L['y_ax'], L['right'], L['top']
    outer = rounded([v2(0, 0), v2(right, 0), v2(right, top), v2(0, top)], 4.0)

    # Cerceveler (cizgi ortasindan): altta kategori etiketleri, ustte baslik ve iki aciklama
    half = (G - 3.0) / 2
    boxes = [(slot_x(s) - half, L['fr_y0'], slot_x(s) + half, L['fr_y0'] + LBL_H) for s in range(NCAT)]
    ty0, ty1 = L['top_y0'], L['top_y0'] + LBL_H
    lg_b = (right - E - W - LG_W, ty0, right - E - W, ty1)
    lg_a = (lg_b[0] - FR_GAP - LG_W, ty0, lg_b[0] - FR_GAP, ty1)
    title = (E + W, ty0, lg_a[0] - FR_GAP, ty1)
    boxes += [title, lg_a, lg_b]
    L['boxes'] = boxes
    # Aciklama deligi cercevenin solunda: pimin basi cerceveye degmez
    legend = [v2(b[0] + W + CLR + 0.3, (ty0 + ty1) / 2) for b in (lg_a, lg_b)]
    L['legend'] = legend

    centers = [hole(s, side, k) for s in range(NCAT) for side in (0, 1) for k in range(1, K + 1)]
    centers += legend
    keep = hole_keepout(centers) + [rrect(x0 - W, y0 - W, x1 + W, y1 + W, FR_RC + W)
                                    for x0, y0, x1, y1 in boxes]
    pc = Piece('sutun_grafik', outer, thickness=T, keepout=keep)
    pc.mesh_cut.append(pin_holes(centers))
    pc.mesh_add.append(frame_fill(boxes))

    # Eksenler (koseda birbirine degmez: kabartmalar arasinda en az GAP)
    pc.add(v2(x_ax, y_ax), v2(x_ax, row_y(K) + 4.0), BAR, 'y ekseni')
    pc.add(v2(x_ax + TICK_X0, y_ax), v2(x_ax + NCAT * G - 1.5, y_ax), BAR, 'x ekseni')

    # Her degerin hizasinda: y ekseninin yaninda, kategoriler arasinda ve en sagda kisa cizgi
    for k in range(1, K + 1):
        y = row_y(k)
        pc.add(v2(x_ax + TICK_X0, y), v2(col_x(0, 0) - DASH_IN, y), BAR, 'cizgi %d eksen' % k)
        for s in range(1, NCAT):
            pc.add(v2(col_x(s - 1, 1) + DASH_IN, y), v2(col_x(s, 0) - DASH_IN, y), BAR,
                   'cizgi %d / %d' % (k, s))
        pc.add(v2(col_x(NCAT - 1, 1) + DASH_IN, y), v2(x_ax + NCAT * G - 1.5, y), BAR,
               'cizgi %d sag' % k)

    # Degerler: rakamlar ve Braille saga dayali
    for k in range(K + 1):
        y = row_y(k)
        w = L['widths'][k]
        pc.add_text(str(k), v2(L['x_num_r'] - w / 2, y), v2(0, 1), NUM_H, 'rakam %d' % k)
        cells = braille_number(str(k))
        c = v2(BR_RIGHT - braille_width(cells) / 2, y)
        pc.add_braille(cells, lambda x, yy, c=c: c + v2(x, yy), 'braille %d' % k, nudge=0)
    return pc


def rotated(src, name, deg):
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    return transformed(src, name, lambda x, y, z: (c * x - s * y, s * x + c * y, z))


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.abspath(argv[0]) if argv else here
    stl_dir = os.path.join(out, 'stl')
    os.makedirs(stl_dir, exist_ok=True)

    reset_scene()
    pc = make_board()
    board, _, _ = build_object(pc)
    report(pc.name, board, 'kabartma=%d yazi=%d' % (len(pc.bumps), len(pc.texts)))
    for s in pc.skipped:
        print('  atlandi:', s)
    assert not pc.skipped, 'yerlesmeyen kabartma ya da yazi var'
    export_stl(board, os.path.join(stl_dir, pc.name + '.stl'))
    board.color = (0.95, 0.93, 0.88, 1.0)
    print('OLCU delik %.1f, eksen x=%.2f y=%.2f, kategori %.1f, cizgi boyu %.2f (ara) %.2f (eksen), '
          'kare pim kosesi %.2f < CLR %.2f'
          % (HOLE_D, L['x_ax'], L['y_ax'], G, G - P - 2 * DASH_IN + 2 * W,
             col_x(0, 0) - DASH_IN - L['x_ax'] - TICK_X0 + 2 * W, MARK_SQ_R, CLR))

    round_pin = make_pin('_isaret_pimi', 'isaret')
    square = make_pin('kare_isaret_pimi_kullanim', 'isaret_kare')
    printed = printed_pin(square, 'kare_isaret_pimi', 'isaret_kare')
    report('kare_isaret_pimi', printed)
    export_stl(printed, os.path.join(stl_dir, 'kare_isaret_pimi.stl'))
    printed.hide_render = True

    # Kenardaki, koseki ve aciklama deliklerinde pim tahtaya carpmamali; kare pim donebilir
    probes = [hole(0, 0, 1), hole(0, 0, K), hole(2, 1, 5), hole(NCAT - 1, 1, 1),
              hole(NCAT - 1, 1, K)] + L['legend']
    probes = [(p.x, p.y) for p in probes]
    square45 = rotated(square, '_kare45', 45)
    worst = check_pin_fit(round_pin, board, probes, 'isaret_pimi')
    worst = max(worst, check_pin_fit(square, board, probes, 'kare_isaret_pimi'))
    worst = max(worst, check_pin_fit(square45, board, probes, 'kare_isaret_pimi 45'))
    # Yan yana deliklerde iki kare pim (koseleri birbirine donuk) birbirine degmemeli
    for dx, dy in ((P, 0), (0, P)):
        a = transformed(square45, '_a', lambda x, y, z: (x, y, z))
        b = transformed(square45, '_b', lambda x, y, z, dx=dx, dy=dy: (x + dx, y + dy, z))
        vol = intersect_volume(a, b)
        print('  iki kare pim (%g, %g) arayla: kesisim = %.3f mm3' % (dx, dy, vol))
        worst = max(worst, vol)
        for o in (a, b):
            m = o.data
            bpy.data.objects.remove(o)
            bpy.data.meshes.remove(m)
    assert worst < 1e-3, 'pim tahtaya ya da yandaki pime carpiyor'
    for o in (round_pin, square45):
        o.hide_render = True

    # Onizleme: ikili sutun grafigi (yuvarlak kirmizi, kare mavi), aciklama deliklerinde birer pim
    data = ((3, 7, 5, 8, 2, 6), (5, 4, 6, 9, 3, 4))
    red, blue = (0.85, 0.2, 0.2, 1.0), (0.15, 0.4, 0.85, 1.0)
    shown = [board]

    def place(src, name, p, col):
        o = transformed(src, name, lambda x, y, z: (p.x + x, p.y + y, T + z))
        o.color = col
        shown.append(o)
    for side, (src, col) in enumerate(((round_pin, red), (square, blue))):
        for s, v in enumerate(data[side]):
            for k in range(1, v + 1):
                place(src, 'onizleme_%d_%d_%d' % (s, side, k), hole(s, side, k), col)
        place(src, 'onizleme_aciklama_%d' % side, L['legend'][side], col)
    render(shown, os.path.join(out, 'onizleme.png'), center=(L['right'] / 2, L['top'] / 2 + 2),
           size=L['right'] * 1.12, tilt=28)
    render(shown, os.path.join(out, 'onizleme_detay.png'),
           center=(L['x_ax'] + 12, L['y_ax'] + 25), size=90, tilt=35)

    # Baski yonunde yuvarlak ve kare isaret pimi
    round_printed = printed_pin(round_pin, '_isaret_pimi_baski', 'isaret')
    shown = []
    for k, (src, col) in enumerate(((round_printed, red), (printed, blue))):
        for j in range(2):
            o = transformed(src, 'baski_%d_%d' % (k, j), lambda x, y, z: (x, y, z))
            o.location = (-15 + 10 * (2 * k + j), 0, 0)
            o.color = col
            shown.append(o)
    render(shown, os.path.join(out, 'onizleme_pim.png'), center=(0, 3), size=42, tilt=35)
    round_printed.hide_render = True
    save_blend(os.path.join(out, 'sutun_grafik.blend'))


main()
