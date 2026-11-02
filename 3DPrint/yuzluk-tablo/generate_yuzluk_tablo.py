"""
Dokunsal yuzluk tablo (gorme engelli ve az goren ogrenciler icin) - STL ureteci.

Calistirma:
  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
      --python generate_yuzluk_tablo.py -- [cikti_klasoru]

Parcalar:
  yuzluk_tablo : 1'den 100'e on sira, on sutun; hucreler 20 mm. Her hucrede ustte Braille, altta
                 solda pim deligi ve hemen saginda buyuk punto sayi; delik Braille'in ilk
                 hucresinin altindadir. Hucreler kabartma cizgilerle ayrilir: siralar arasinda
                 kenara kadar uzanan yatay, sutunlar arasinda dikey cizgi. Asagi inmek 10 ekler,
                 saga gitmek 1.
  isaret_pimi  : Tahtaya oturan alcak, yuvarlak basli pim (8 mm). Deliklere takilip sayilari
                 isaretler: ikiser sayma, tek ve cift, katlar. Lastik takilmaz.

Delikler koordinat tahtasininkiyle ayni (ortak/pim.py): koordinat tahtasinin pimleri ve pim deneme
parcasi buraya da uyar; delik olcusu orada secilir. Pimin basi ya da flansi hucredeki Braille'e ve
rakama degmez. Isaret pimleri basi tablaya gelecek sekilde ters basilir; destek gerekmez.
Iki renkli baski: tahtada 5,0 mm'de duraklatip filament degistirin.
"""
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ortak'))
from dokunsal import (BAR, BR_DOT, GAP, MARGIN, Piece, braille_number,  # noqa: E402
                      braille_width, build_object, export_stl, render, report, reset_scene,
                      rounded, save_blend, text_shape, v2)
from pim import (BOARD_T as T, CLR, HOLE_D, check_pin_fit, hole_keepout, make_pin,  # noqa: E402
                 pin_holes, printed_pin, transformed)

# ---------------------------------------------------------------------------
# Olculer (mm). Hucre (sira r, sutun c): r = 0 ustteki sira (1-10), c = 0 soldaki sutun.
# Hucrenin sol alt kosesi (C * c, C * (N - 1 - r)); z = 0 tahtanin alti.
# ---------------------------------------------------------------------------
N = 10
C = 20.0                # hucre araligi
NUM_H = 4.6             # buyuk punto rakam yuksekligi (koordinat tahtasi ve sayi dogrusuyla ayni)
X_L = 1.0               # Braille'in sol kenari, hucrenin sol kenarindan
BR_Y = 14.5             # Braille'in orta sirasi, hucrenin altindan
HY = 5.5                # delik merkezi ve rakam ortasi, hucrenin altindan
# Yaklasik 900 Braille noktasi ve 100 sayi: varsayilan cozunurlukte STL 25 MB oluyordu. 1,5 mm'lik
# noktada 12 kose ile daire arasindaki fark 0,03 mm, baskida gorulmez.
BUMP_N, TEXT_RES = 12, 4
EDGE = 4.5              # izgaranin disinda kalan kenar (100'un Braille'i sag kenara tasar)
# Sutun ayiraci: iki basamakli sayinin Braille'inin sag kenari ile sonraki hucrenin Braille'inin
# ortasi. Satir cizgilerine GAP kadar yaklasir, degmez.
SEP_X = (X_L + 2 * BR_DOT[0] + braille_width(braille_number('10')) + C + X_L) / 2
SEP_Y = 2 * BAR[0] + GAP + 0.1
# Delik soldaki ayiracin hemen saginda (pimin flansi ayiraca degmez), rakam deligin hemen saginda:
# delik kendi sayisinin yanindadir, bir sonrakinin degil.
HX = SEP_X - C + CLR + BAR[0] + 0.4
NUM_X = HX + CLR + 0.2  # rakamin sol kenari


def number(r, c):
    return 10 * r + c + 1


def corner(r, c):
    return v2(C * c, C * (N - 1 - r))


def hole(r, c):
    return corner(r, c) + v2(HX, HY)


# ---------------------------------------------------------------------------
# Tahta
# ---------------------------------------------------------------------------
def make_board():
    side = N * C
    outer = rounded([v2(-EDGE, -EDGE), v2(side + EDGE, -EDGE), v2(side + EDGE, side + EDGE),
                     v2(-EDGE, side + EDGE)], 4.0)
    centers = [hole(r, c) for r in range(N) for c in range(N)]
    pc = Piece('yuzluk_tablo', outer, thickness=T, keepout=hole_keepout(centers))
    pc.bump_n, pc.text_res = BUMP_N, TEXT_RES
    pc.mesh_cut.append(pin_holes(centers))

    # Siralar arasinda cizgi (kenara kadar uzanir: parmak kenardan sirayi bulur)
    x_end = EDGE - MARGIN - BAR[0] - 0.5
    for k in range(1, N):
        pc.add(v2(-x_end, C * k), v2(side + x_end, C * k), BAR, 'sira cizgisi %d' % k)

    # Sutunlar arasinda dikey cizgi (100'un Braille'i son sutunun sagina tasar; orada cizgi yok)
    for r in range(N):
        for c in range(N - 1):
            o = corner(r, c)
            pc.add(o + v2(SEP_X, SEP_Y), o + v2(SEP_X, C - SEP_Y), BAR, 'ayirac %d' % number(r, c))

    for r in range(N):
        for c in range(N):
            n, o = number(r, c), corner(r, c)
            w = text_shape(str(n), NUM_H, TEXT_RES)['w']
            pc.add_text(str(n), o + v2(NUM_X + w / 2, HY), v2(0, 1), NUM_H, 'rakam %d' % n)
            cells = braille_number(str(n))
            bc = o + v2(X_L + BR_DOT[0] + braille_width(cells) / 2, BR_Y)
            pc.add_braille(cells, lambda x, y, bc=bc: bc + v2(x, y), 'braille %d' % n, nudge=0)
    return pc


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
    print('OLCU hucre %.1f, delik %.1f, delik hucrede (%.2f, %.2f), rakam %.2f..%.2f (100), ayirac x %.2f, CLR %.2f'
          % (C, HOLE_D, HX, HY, NUM_X, NUM_X + text_shape('100', NUM_H, TEXT_RES)['w'], SEP_X, CLR))

    mark = make_pin('isaret_pimi_kullanim', 'isaret')
    printed = printed_pin(mark, 'isaret_pimi', 'isaret')
    report('isaret_pimi', printed)
    export_stl(printed, os.path.join(stl_dir, 'isaret_pimi.stl'))
    printed.hide_render = True
    # Koselerde, 100'de ve ortada pim tahtaya (Braille, rakam, cizgi) carpmamali; koordinat
    # tahtasinin flansli pimi de ayni deliklere girer
    probe_cells = [(0, 0), (0, 9), (4, 4), (4, 5), (9, 0), (9, 8), (9, 9)]
    worst = check_pin_fit(mark, board, [hole(r, c) for r, c in probe_cells], 'isaret_pimi')
    tall = make_pin('_pim_yuvarlak', 'yuvarlak')
    worst = max(worst, check_pin_fit(tall, board, [hole(r, c) for r, c in probe_cells[:3]], 'pim_yuvarlak'))
    assert worst < 1e-3, 'pim tahtaya carpiyor'
    tall.hide_render = True

    # Onizleme: 3'un katlari isaretli (capraz siralar)
    shown = [board]
    red = (0.85, 0.2, 0.2, 1.0)
    for r in range(N):
        for c in range(N):
            if number(r, c) % 3 == 0:
                h = hole(r, c)
                o = transformed(mark, 'onizleme_%d' % number(r, c),
                                lambda x, y, z, h=h: (h.x + x, h.y + y, T + z))
                o.color = red
                shown.append(o)
    render(shown, os.path.join(out, 'onizleme.png'), center=(N * C / 2, N * C / 2 + 3), size=300, tilt=28)
    render(shown, os.path.join(out, 'onizleme_detay.png'), center=(38, 170), size=84, tilt=35)

    # Baski yonunde isaret pimleri
    shown = []
    for k in range(4):
        o = transformed(printed, 'baski_%d' % k, lambda x, y, z: (x, y, z))
        o.location = (-15 + 10 * k, 0, 0)
        o.color = red
        shown.append(o)
    render(shown, os.path.join(out, 'onizleme_pim.png'), center=(0, 0), size=42, tilt=35)
    save_blend(os.path.join(out, 'yuzluk_tablo.blend'))


main()
