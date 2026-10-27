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

Dokunsal kodlama (butun parcalarda ayni, olculer ../ortak/dokunsal.py icinde):
  kucuk nokta = 1 cm / 10 derece, buyuk nokta = 5 cm / 30 derece,
  cizgi = 10 cm / 90 derece (ve cetvelde sifir), Braille = sayi isareti + rakam
Her olcek isaretinin hizasinda kenarda yarim daire centik var: cizerken kalem ucu
centige takilir, ogrenci kac cm ilerledigini sayabilir (ruler-01'deki centik olcusu).
Braille etiketler, olcek kenari okuyucuya en yakin olacak sekilde tutuldugunda
soldan saga okunur.
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ortak'))
from dokunsal import (BAR, BAR_SPAN, BR_OFF, DOT_L, DOT_S, TICK_OFF, Piece, arc_poly,  # noqa: E402
                      braille_number, build_object, circle, export_stl, inset, left_normal,
                      linear_scale, rect, render, report, reset_scene, rounded, save_blend, v2)

END_CLEAR = 15.0        # gonyede olcek, karsi sivri koseden bu kadar once biter
                        # (iki kenarin olcegi koseye yakin karismasin)


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
        pc.add_braille(braille_number(str(deg)), place, '%s %d deg braille' % (pc.name, deg))

    # tabanda merkezden iki yana cm olcegi + merkez cizgisi
    kmax = int((R - 5) // 10)
    linear_scale(pc, v2(0, 0), v2(1, 0), v2(0, 1), 1, kmax, v2(1, 0))
    linear_scale(pc, v2(0, 0), v2(-1, 0), v2(0, 1), 1, kmax, v2(1, 0))
    pc.add(v2(0, notch + BAR[0] + 1.0), v2(0, 12.0), BAR, 'merkez cizgisi')
    return pc


def make_pieces():
    s3 = math.sqrt(3)
    return [
        make_ruler(20),
        make_set_square('gonye_45', [v2(0, 0), v2(150, 0), v2(0, 150)], 0, 1),
        make_set_square('gonye_30_60', [v2(0, 0), v2(100, 0), v2(0, 100 * s3)], 0, 1),
        make_protractor(),
    ]


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.abspath(argv[0]) if argv else here
    stl_dir = os.path.join(out, 'stl')
    os.makedirs(stl_dir, exist_ok=True)

    reset_scene()
    objs = []
    for pc in make_pieces():
        obj, solver, vol = build_object(pc)
        report(pc.name, obj, 'kabartma=%d centik=%d' % (len(pc.bumps), len(pc.notches)))
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
    save_blend(os.path.join(out, 'geometri_seti.blend'))


main()
