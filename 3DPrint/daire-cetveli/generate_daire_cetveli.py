"""
Dokunsal daire cizim cetveli (pergel yerine; gorme engelli ve az goren ogrenciler icin) - STL ureteci.

Calistirma:
  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
      --python generate_daire_cetveli.py -- [cikti_klasoru]

Parcalar:
  daire_cetveli : 122,5 x 31 mm serit. Yuvarlak bastaki merkez deligine raptiye takilip cizim
                  altligina batirilir (ya da deligi dik tutulan bir kalemle bastirilir). Kalem
                  istenen yaricaptaki delige takilip cetvel merkez cevresinde dondurulur.
                  Delikler merkezden 1 cm ile 10 cm arasinda her 0,5 cm'de. Tam santimetrelerde
                  geometri setiyle ayni kodlama: kucuk nokta, 5 cm'de buyuk nokta, 10 cm'de cizgi
                  (merkez de cetveldeki sifir gibi cizgiyle isaretli). 5 ve 10'da Braille, her
                  santimetrede buyuk punto rakam (merkezde 0). Yarim santimetre deliklerinin
                  yaninda isaret yok: tam santimetrelerin arasindaki deliktir.
  delik_deneme  : 1,8 / 2,0 / 2,2 / 2,4 mm dort delik. Deligin ustunde 1-4 kucuk nokta, altinda
                  buyuk punto olcu. Ogrencinin kalemi hangisine rahat giriyor ve ucu kagida
                  degiyorsa betikteki HOLE_D o yapilip cetvel yeniden uretilir.

Her deligin ustu 45 derece havsalidir: kalemin ucu deligin ortasina kayar, tukenmez kalemin ve
acilmis kursun kalemin ucu 2 mm'lik delikten kagida degecek kadar iner.
Iki renkli baski: 3,0 mm'de duraklatip filament degistirin (geometri setiyle ayni).
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ortak'))
from dokunsal import (BAR, BR_DOT, BR_PITCH, DOT_L, DOT_S, MARGIN, Piece,  # noqa: E402
                      braille_number, braille_width, build_object, circle, convex_hull,
                      countersunk_holes, export_stl, render, report, reset_scene, rounded,
                      save_blend, v2)

# ---------------------------------------------------------------------------
# Olculer (mm). Merkez deligi orijinde, delikler +x yonunde, y = 0 cizgisinde.
# ---------------------------------------------------------------------------
T = 3.0                 # kalinlik (geometri setiyle ayni)
STEP = 5.0              # delik araligi (0,5 cm)
R_MAX = 100.0           # en buyuk yaricap
HOLE_D = 2.0            # kalem deligi capi
CS_DEPTH = 1.0          # havsa derinligi; 45 derece: ustte cap HOLE_D + 2 * CS_DEPTH
R_HUB = 11.5            # merkezdeki yuvarlak basin yaricapi
X_END = 111.0           # serit ucu
X_WIDE = 38.0           # Braille satirinin oldugu genis kismin basladigi yer
Y_TOP = 19.5            # genis kismin ust kenari
Y_BOT = -R_HUB          # alt kenar (duz)
NUM_H = 4.6             # buyuk punto rakam yuksekligi (~18 punto, sayi dogrusuyla ayni)

CS_R = HOLE_D / 2 + CS_DEPTH                    # havsanin ustteki yaricapi
Y_DOT = CS_R + MARGIN + DOT_L[0] + 0.6          # kodlama noktalari
Y_BAR = (CS_R + MARGIN + BAR[0], CS_R + MARGIN + BAR[0] + 6.0)   # cizgi (cetveldeki gibi 6 mm)
Y_BR = Y_BAR[1] + BAR[0] + 0.5 + BR_PITCH + BR_DOT[0]           # Braille merkezi
Y_NUM = -(CS_R + MARGIN + NUM_H / 2 + 0.3)      # buyuk punto rakam merkezi


def make_ruler():
    pts = circle(v2(0, 0), R_HUB, 96) + [v2(X_END, Y_BOT), v2(X_END, Y_TOP), v2(X_WIDE, Y_TOP)]
    outer = rounded(convex_hull(pts), 3.0)
    centers = [v2(0, 0)] + [v2(STEP * i, 0) for i in range(2, int(R_MAX / STEP) + 1)]
    keep = [circle(c, CS_R, 32) for c in centers]
    pc = Piece('daire_cetveli', outer, thickness=T, keepout=keep)
    pc.mesh_cut.append(countersunk_holes(centers, HOLE_D, CS_DEPTH, T))

    for k in range(0, int(R_MAX // 10) + 1):
        x = 10.0 * k
        tag = '%d cm' % k
        if k % 10 == 0:
            pc.add(v2(x, Y_BAR[0]), v2(x, Y_BAR[1]), BAR, tag)
        else:
            pc.add(v2(x, Y_DOT), None, DOT_L if k % 5 == 0 else DOT_S, tag)
        pc.add_text('%d' % k, v2(x, Y_NUM), v2(0, 1), NUM_H, tag + ' rakam')
        if k % 5 == 0 and k > 0:
            c = v2(x, Y_BR)
            pc.add_braille(braille_number(str(k)), lambda u, w, c=c: c + v2(u, w), tag + ' braille')
    return pc


def make_test(ds=(1.8, 2.0, 2.2, 2.4), pitch=14.0):
    x0 = 9.0
    L = 2 * x0 + pitch * (len(ds) - 1)
    pts = [v2(0, -10.0), v2(L, -10.0), v2(L, 8.0), v2(0, 8.0)]
    outer = rounded(pts, 3.0)
    centers = [v2(x0 + pitch * i, 0) for i in range(len(ds))]
    keep = [circle(c, d / 2 + CS_DEPTH, 32) for c, d in zip(centers, ds)]
    pc = Piece('delik_deneme', outer, thickness=T, keepout=keep)
    for c, d in zip(centers, ds):
        pc.mesh_cut.append(countersunk_holes([c], d, CS_DEPTH, T))
    for i, (c, d) in enumerate(zip(centers, ds)):
        n = i + 1
        for j in range(n):
            pc.add(c + v2((j - (n - 1) / 2) * 2.8, Y_DOT), None, DOT_S, '%.1f nokta %d' % (d, j))
        pc.add_text(('%.1f' % d).replace('.', ','), c + v2(0, Y_NUM), v2(0, 1), NUM_H, '%.1f yazi' % d)
    return pc


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.abspath(argv[0]) if argv else here
    stl_dir = os.path.join(out, 'stl')
    os.makedirs(stl_dir, exist_ok=True)

    reset_scene()
    objs = []
    for pc in (make_ruler(), make_test()):
        obj, _, _ = build_object(pc)
        report(pc.name, obj, 'kabartma=%d yazi=%d' % (len(pc.bumps), len(pc.texts)))
        for s in pc.skipped:
            print('  atlandi:', s)
        export_stl(obj, os.path.join(stl_dir, pc.name + '.stl'))
        obj.color = (0.95, 0.45, 0.12, 1.0)
        objs.append(obj)
    print('OLCU delik %.1f, havsa ustte %.1f, nokta y=%.2f, cizgi y=%.2f..%.2f, Braille y=%.2f, '
          'rakam y=%.2f, Braille genisligi(10)=%.1f'
          % (HOLE_D, 2 * CS_R, Y_DOT, Y_BAR[0], Y_BAR[1], Y_BR, Y_NUM, braille_width(braille_number('10'))))

    ruler, test = objs
    test.location = (25, -40, 0)
    render([ruler, test], os.path.join(out, 'onizleme.png'), center=(55, -8), size=150, tilt=30)
    render([ruler], os.path.join(out, 'onizleme_detay.png'), center=(25, 4), size=60, tilt=35)
    save_blend(os.path.join(out, 'daire_cetveli.blend'))


main()
