"""
Dokunsal kesir seti + tabak (gorme engelli ve az goren ogrenciler icin) - STL ureteci.

Calistirma:
  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
      --python generate_kesir.py -- [cikti_klasoru]

Parcalar:
  tabak          : kesir dairelerinin oturdugu tabak. Ortadaki pim, parcalarin uclarini
                   merkeze toplar; kenar parcalari disaridan tutar. Saat 12'de buyuk nokta
                   = baslangic isareti (kesirler buradan saat yonunde dizilip karsilastirilir).
                   Saat 3 ve 9'da parmak oyugu (parcayi kaldirmak icin). Tutma dilinde
                   Braille "kesir" ve buyuk punto "KESİR".
  kesir_1_N      : 1/N parcalari (N adet), her parcada
                   - merkezden disa dogru okunan Braille kesir (pay normal, payda alt rakam)
                   - yay kenarina yakin, az gorenler icin buyuk punto "1/N"

Iki renkli baski (az gorenler icin kontrast): parcalarda 4.0 mm'de, tabakta 5.4 mm'de
duraklatip filament degistirin; kabartmalar zemin renginden ayrilir.
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ortak'))
from dokunsal import (DOT_L, SINK, Piece, braille_fraction, braille_width, braille_word,  # noqa: E402
                      build_object, circle, convex_hull, export_stl, left_normal, merge_objects,
                      polar, render, report, reset_scene, rounded, save_blend, v2)

# ---------------------------------------------------------------------------
# Olculer (mm)
# ---------------------------------------------------------------------------
DENOMS = (1, 2, 3, 4, 5, 6, 8, 10, 12)
R = 50.0                # parca yaricapi (1/12'de Braille + buyuk punto sigsin diye 100 mm cap)
T_PIECE = 4.0           # parca kalinligi
KERF = 0.3              # komsu parcalar arasindaki toplam bosluk
RC = 4.0                # parca ucundaki merkez oyugu (sivri uc olmasin, pime otursun)
EXPLODE = 2.5           # STL'de parcalar arasi aralik (tablaya yerlesim)
LP_HEIGHT = 6.0         # buyuk punto yazi yuksekligi
LP_R = 44.5             # buyuk punto yazinin merkezden uzakligi
BR_R0 = 17.0            # Braille'in merkezden basladigi uzaklik

FLOOR = 2.4             # tabak taban kalinligi
RIM_H = 3.0             # kenarin taban ustundeki yuksekligi (parca 1 mm disari tasar)
RIM_W = 5.0             # kenar genisligi
CLEAR = 0.5             # parca ile tabak kenari arasi bosluk
BOSS_R = RC - 0.4       # merkez pimi
TAB_W = 46.0            # tutma dili genisligi
TAB_D = 26.0            # tutma dilinin kenardan tasma miktari
SCOOP_R = 9.0           # parmak oyugu yaricapi
SCOOP_DEPTH = 1.2       # parmak oyugunun tabana inme derinligi


def arc(r, deg0, deg1, step=1.0):
    k = max(1, math.ceil(abs(deg1 - deg0) / step))
    return [polar(r, deg0 + (deg1 - deg0) * j / k) for j in range(k + 1)]


def make_piece(n):
    """1/n parcasi; aciortay +y yonunde (90 derece)."""
    name = 'kesir_1_%d_parca' % n
    if n == 1:
        pc = Piece(name, circle(v2(0, 0), R, 360), [circle(v2(0, 0), RC, 48)], thickness=T_PIECE)
    else:
        half = 180.0 / n
        k = KERF / 2
        do = math.degrees(math.asin(k / R))
        di = math.degrees(math.asin(k / RC))
        poly = arc(R, 90 - half + do, 90 + half - do) + arc(RC, 90 + half - di, 90 - half + di, 5.0)
        pc = Piece(name, poly, thickness=T_PIECE)

    b = v2(0, 1)                    # aciortay (disa)
    up = left_normal(b)
    cells = braille_fraction(1, n)
    c = b * (BR_R0 + braille_width(cells) / 2)
    pc.add_braille(cells, lambda x, y: c + b * x + up * y, name + ' braille')
    pc.add_text('1/%d' % n, b * LP_R, -b, LP_HEIGHT, name + ' buyuk punto')
    return pc


def make_plate():
    rp = R + CLEAR + RIM_W
    top = FLOOR + RIM_H
    tab = [v2(-TAB_W / 2, -rp - TAB_D), v2(TAB_W / 2, -rp - TAB_D),
           v2(TAB_W / 2, -rp + 10), v2(-TAB_W / 2, -rp + 10)]
    outer = rounded(convex_hull(circle(v2(0, 0), rp, 180) + tab), 4.0)
    pocket = circle(v2(0, 0), R + CLEAR, 180)
    scoops = [v2(s * (R + CLEAR + RIM_W / 2), 0) for s in (1, -1)]
    pc = Piece('tabak', outer, thickness=top,
               keepout=[pocket] + [circle(s, SCOOP_R, 48) for s in scoops])
    pc.cyl_cut.append((v2(0, 0), R + CLEAR, FLOOR, top + 1.0))
    for s in scoops:
        pc.cyl_cut.append((s, SCOOP_R, FLOOR - SCOOP_DEPTH, top + 1.0))
    pc.cyl_add.append((v2(0, 0), BOSS_R, FLOOR - SINK, top))

    pc.add(v2(0, R + CLEAR + RIM_W / 2), None, DOT_L, 'baslangic isareti')
    pc.add_text('KESİR', v2(0, -rp - 7.5), v2(0, 1), LP_HEIGHT, 'tabak buyuk punto')
    c = v2(0, -rp - 17.5)
    pc.add_braille(braille_word('kesir'), lambda x, y: c + v2(x, y), 'tabak braille')
    return pc


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.abspath(argv[0]) if argv else here
    stl_dir = os.path.join(out, 'stl')
    os.makedirs(stl_dir, exist_ok=True)

    reset_scene()
    plate_pc = make_plate()
    plate, _, _ = build_object(plate_pc)
    report('tabak', plate)
    for s in plate_pc.skipped:
        print('  atlandi:', s)
    export_stl(plate, os.path.join(stl_dir, 'tabak.stl'))

    colors = [(0.1, 0.1, 0.1), (0.85, 0.2, 0.2), (0.15, 0.4, 0.85), (0.15, 0.65, 0.3),
              (0.95, 0.75, 0.1), (0.6, 0.3, 0.75), (0.95, 0.5, 0.1), (0.2, 0.7, 0.75),
              (0.85, 0.4, 0.6)]
    sets = {}
    for n, col in zip(DENOMS, colors):
        pc = make_piece(n)
        wedge, _, _ = build_object(pc)
        for s in pc.skipped:
            print('  atlandi:', s)
        step = 360.0 / n
        placed = [(wedge, tuple(polar(EXPLODE if n > 1 else 0, 90 + i * step)), i * step)
                  for i in range(n)]
        obj = merge_objects('kesir_1_%d' % n, placed)
        report(obj.name, obj, '(%d parca)' % n)
        export_stl(obj, os.path.join(stl_dir, obj.name + '.stl'))
        obj.color = (*col, 1.0)
        sets[n] = (wedge, obj)

    # onizleme: tabakta 1/4 seti + butun setler
    plate.color = (0.92, 0.92, 0.9, 1.0)
    wedge4 = sets[4][0]
    inplate = merge_objects('tabakta_1_4', [(wedge4, (0, 0), i * 90) for i in range(4)])
    inplate.location = (0, 0, FLOOR)
    inplate.color = sets[4][1].color
    grid = [(130, 0), (260, 0), (-130, -130), (0, -130), (130, -130), (260, -130),
            (-130, 0), (0, -260), (130, -260)]
    shown = [plate, inplate]
    for (n, (_, obj)), pos in zip(sets.items(), grid):
        if n == 4:
            obj.hide_render = True
            continue
        obj.location = (*pos, 0)
        shown.append(obj)
    render(shown, os.path.join(out, 'onizleme.png'), center=(65, -105), size=560, tilt=25)
    render([plate, inplate], os.path.join(out, 'onizleme_tabak.png'), center=(0, -12), size=170, tilt=35)
    w12 = sets[12][0]
    w12.location = (600, 0, 0)
    w12.color = sets[12][1].color
    render([w12], os.path.join(out, 'onizleme_1_12.png'), center=(600, 28), size=70, tilt=15)
    save_blend(os.path.join(out, 'kesir_seti.blend'))


main()
