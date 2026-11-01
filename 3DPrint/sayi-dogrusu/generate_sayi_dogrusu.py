"""
Dokunsal sayi dogrusu (-10 ... +10) ve iki kaydirici (gorme engelli ve az goren
ogrenciler icin) - STL ureteci.

Calistirma:
  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
      --python generate_sayi_dogrusu.py -- [cikti_klasoru]

Parcalar:
  sayi_dogrusu        : 216 x 47 mm serit, birim 1 cm (cetvelle ayni).
                        Sayi dogrusunun kendisi kirlangic kuyrugu kesitli bir ray. Uclari ok
                        gibi sivrilir ve alcalir (dogru iki yana devam eder). Rayin ustunde her
                        tam sayida bir oluk vardir: parmakla sayilir, kaydirici burada tik diye
                        oturur.
                        Rayin ustunde her tam sayida cizgi vardir. 5'in katlarinda cizgi uzundur;
                        sifirda uzun cizgi + buyuk nokta (kesir tabagindaki baslangic isaretiyle
                        ayni).
                        Her tam sayinin ustunde buyuk punto rakam (~18 punto). Rayin altinda
                        -10, -5, 0, 5 ve 10 icin Braille.
  kaydirici_ucgen     : Raya uctan gecen isaretci. Burnu, cizginin dibini gosterir. Ust
                        plakadaki esnek dilin altindaki tirnak oluklara oturur: her tam
                        sayida bir tik.
  kaydirici_yuvarlak  : Ayni isaretci, yuvarlak burunlu; baska renkte basilir. Iki isaretciyle
                        baslangic / bitis, iki sayi arasi uzaklik ve karsilastirma calisilir.
  ray_deneme          : 5 olukluk kisa ray (~20 dk). Uzun seridi basmadan once kaydiricinin
                        oturmasini ve tikini bununla deneyin.

Kaydiricilar ust yuzu tablaya gelecek sekilde ters cevrilmis olarak disa aktarilir; destek
gerekmez. Iki renkli baski: seritte 3.0 mm'de duraklatip filament degistirin.
Kaydirici sikiysa ya da bossa CLEAR'i, tik zayif ya da sertse DETENT'i degistirin.

Negatif sayilarin Braille yazimi: sayi isareti + (5,6)(3,6) + rakam. Bu, Duxbury'nin Turk
Braille matematik dizinindeki '-3' ornegine dayaniyor; ogretmen onayi bekleniyor.
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ortak'))
from dokunsal import (BAR, DOT_L, GAP, MARGIN, SINK, Piece, add_box, add_extrusion,  # noqa: E402
                      add_loft, add_prism, boolean_solid, braille_signed, build_object,
                      export_stl, mesh_of, rect, render, report, reset_scene,
                      rounded, save_blend, v2)
import bmesh  # noqa: E402
import bpy  # noqa: E402

# ---------------------------------------------------------------------------
# Olculer (mm)
# ---------------------------------------------------------------------------
N = 10                  # -N ... +N
UNIT = 10.0             # bir birim = 1 cm
END = 8.0               # son cizgiden serit ucuna
L = 2 * N * UNIT + 2 * END
T = 3.0                 # serit kalinligi
X0 = L / 2              # sifirin yeri

# Ray: serit yuzeyinden olculur. Tabanda RB, ustte RT yari genislik (kirlangic kuyrugu).
RB, RT, RH = 3.5, 5.0, 3.0
TIP = 1.0               # ok ucunun serit ucuna uzakligi
TIP_LEN = 6.0           # sivrilip alcalan kismin boyu (kaydirici buradan raya girer)
TIP_S, TIP_H = 0.25, 0.35   # ok ucunda genislik / yukseklik orani
GROOVE_R, GROOVE_D = 1.0, 0.6   # her tam sayidaki oluk (yaricap, derinlik)

# Kaydirici (z = serit yuzeyi)
CLEAR = 0.3             # ray ile kaydirici arasi bosluk
WALL = 2.0              # yan duvar
TOP = 2.0               # ust plaka
BOT = 0.4               # kaydiricinin alti ile serit arasi
LS = 24.0               # kaydirici boyu
TONGUE_W, TONGUE_T = 5.0, 1.0           # esnek dil eni / kalinligi
TONGUE_ROOT, TONGUE_TIP = -10.8, 1.5    # dilin koku / ucu (x)
SLOT = 1.0              # dil cevresindeki yarik
NUB_R, NUB_W = 0.9, 4.0 # tirnak (alt yaricap, en)
DETENT = 0.4            # tirnagin ray ustunde dili esnetme miktari
NOSE = 3.5              # burnun yan duvardan tasmasi

# Serit uzerinde yerlesim (y, okuyucu tarafi 0)
YB = 4.6                # Braille satiri
YR = 16.5               # ray ekseni
NUM_H = 4.6             # buyuk punto rakam yuksekligi (~18 punto)
TICK_S, TICK_L = 5.0, 9.0
W = 47.0

# Turetilen olculer
_FL = math.hypot(RT - RB, RH)
SIN_T = (RT - RB) / _FL                 # yan yuzun dikeyle yaptigi acinin sinusu
ZC = RH + CLEAR                         # kanal tavani
ZT = ZC + TOP                           # kaydirici ustu
PLAY = CLEAR / SIN_T                    # kaydiricinin yukari bosluğu (yan yuzler degene kadar)
NUB_LOW = RH - PLAY - DETENT            # tirnagin alt ucu (kaydirici ortalanmisken)


def flank_y(z):
    """Kanalin (rayin CLEAR kadar disari ofsetli yan yuzu) z yuksekligindeki yari genisligi."""
    nx, nz = RH / _FL, -(RT - RB) / _FL
    return RB + CLEAR * nx + (z - CLEAR * nz) * (RT - RB) / RH


HW = flank_y(ZC) + WALL                 # kaydirici yari genisligi


def label(k):
    return '−%d' % -k if k < 0 else '%d' % k


# ---------------------------------------------------------------------------
# Serit
# ---------------------------------------------------------------------------
def rail_fill(length, yr):
    """0..length boyunca ray; iki ucu ok gibi sivrilip alcalir."""
    def ring(x, s, h):
        z0 = -SINK
        hw0 = RB + (RT - RB) * z0 / RH
        pts = [(-hw0 * s, z0), (hw0 * s, z0), (RT * s, RH * h), (-RT * s, RH * h)]
        return [(x, yr + y, T + z) for y, z in pts]

    def fill(bm):
        add_loft(bm, [ring(TIP, TIP_S, TIP_H), ring(TIP + TIP_LEN, 1, 1),
                      ring(length - TIP - TIP_LEN, 1, 1), ring(length - TIP, TIP_S, TIP_H)])
    return fill


def groove_fill(xs, yr):
    """Ray ustunde xs noktalarinda enine oluk (kaydirici tirnagi buraya oturur)."""
    zc = T + RH + GROOVE_R - GROOVE_D
    prof = [(GROOVE_R * math.cos(2 * math.pi * j / 32), GROOVE_R * math.sin(2 * math.pi * j / 32))
            for j in range(32)]

    def fill(bm):
        for x in xs:
            add_extrusion(bm, prof, (x, yr, zc), (1, 0, 0), (0, 0, 1), (0, -1, 0), -(RT + 1), RT + 1)
    return fill


def make_strip():
    outer = rounded(rect(L, W), 3.0)
    lane = [v2(-5, YR - HW - 0.2), v2(L + 5, YR - HW - 0.2),
            v2(L + 5, YR + HW + 0.2), v2(-5, YR + HW + 0.2)]       # kaydiricinin gectigi serit
    pc = Piece('sayi_dogrusu', outer, thickness=T, keepout=[lane])
    pc.mesh_add.append(rail_fill(L, YR))
    pc.mesh_cut_last.append(groove_fill([X0 + k * UNIT for k in range(-N, N + 1)], YR))

    y0 = YR + HW + 0.2 + BAR[0] + MARGIN + 0.05
    for k in range(-N, N + 1):
        x = X0 + k * UNIT
        span = TICK_L if k % 5 == 0 else TICK_S
        pc.add(v2(x, y0), v2(x, y0 + span), BAR, 'cizgi %d' % k)
    y_dot = y0 + TICK_L + BAR[0] + GAP + DOT_L[0] + 0.2
    pc.add(v2(X0, y_dot), None, DOT_L, 'sifir noktasi')

    y_num = y_dot + DOT_L[0] + GAP + 0.15 + NUM_H / 2
    for k in range(-N, N + 1):
        # "-10"un uzun eksi isareti "-9"a yapisik gorunmesin: uctaki etiket biraz disari
        dx = -1.5 if k == -N else 0.0
        pc.add_text(label(k), v2(X0 + k * UNIT + dx, y_num), v2(0, 1), NUM_H, 'rakam %d' % k)
    for k in range(-N, N + 1, 5):
        c = v2(X0 + k * UNIT, YB)
        pc.add_braille(braille_signed(k), lambda x, y, c=c: c + v2(x, y), 'braille %d' % k,
                       nudge=12.0)
    return pc


def make_test(units=5):
    """Kisa deneme rayi: kaydiricinin oturmasini ve tikini uzun seridi basmadan dene."""
    length = (units - 1) * UNIT + 2 * (TIP + TIP_LEN + 4.0)
    width = 2 * HW + 6.0
    pc = Piece('ray_deneme', rounded(rect(length, width), 3.0), thickness=T)
    pc.mesh_add.append(rail_fill(length, width / 2))
    x0 = (length - (units - 1) * UNIT) / 2
    pc.mesh_cut_last.append(groove_fill([x0 + i * UNIT for i in range(units)], width / 2))
    return pc


# ---------------------------------------------------------------------------
# Kaydirici (kullanim konumunda: x ray boyunca, y ray ekseninden, z serit yuzeyinden)
# ---------------------------------------------------------------------------
def make_slider(name, nose):
    yb, yt = flank_y(BOT), flank_y(ZC)
    body = [(-HW, BOT), (-yb, BOT), (-yt, ZC), (yt, ZC), (yb, BOT), (HW, BOT), (HW, ZT), (-HW, ZT)]
    base = mesh_of(name, lambda bm: add_extrusion(bm, body, (0, 0, 0), (0, 1, 0), (0, 0, 1),
                                                  (1, 0, 0), -LS / 2, LS / 2))
    if nose == 'ucgen':
        npts = [v2(-3.5, HW - 1.0), v2(3.5, HW - 1.0), v2(0, HW + NOSE)]
    else:
        npts = [v2(-3.5, HW - 1.0), v2(3.5, HW - 1.0)] + [
            v2(3.5 * math.cos(math.pi * j / 16), HW + 3.5 * math.sin(math.pi * j / 16))
            for j in range(17)]
    hw_t = TONGUE_W / 2
    slot = [v2(TONGUE_ROOT, -hw_t - SLOT), v2(TONGUE_TIP + SLOT, -hw_t - SLOT),
            v2(TONGUE_TIP + SLOT, hw_t + SLOT), v2(TONGUE_ROOT, hw_t + SLOT),
            v2(TONGUE_ROOT, hw_t), v2(TONGUE_TIP, hw_t), v2(TONGUE_TIP, -hw_t),
            v2(TONGUE_ROOT, -hw_t)]
    nub_top = ZT - TONGUE_T + 0.3
    zc_n = NUB_LOW + NUB_R
    nub = [(NUB_R * math.cos(t), zc_n + NUB_R * math.sin(t))
           for t in (math.pi + math.pi * j / 12 for j in range(13))]
    nub += [(NUB_R, nub_top), (-NUB_R, nub_top)]
    ops = [
        # burun ust yuzle ayni hizada: ters basilinca tablaya oturur
        ('UNION', mesh_of(name + '_burun', lambda bm: add_prism(bm, npts, ZC, ZT))),
        ('DIFFERENCE', mesh_of(name + '_yarik', lambda bm: add_prism(bm, slot, ZC - 0.5, ZT + 0.5))),
        ('DIFFERENCE', mesh_of(name + '_dil', lambda bm: add_box(
            bm, TONGUE_ROOT + 0.4, TONGUE_TIP + 0.5, -hw_t - 0.5, hw_t + 0.5, ZC - 0.5,
            ZT - TONGUE_T))),
        ('UNION', mesh_of(name + '_tirnak', lambda bm: add_extrusion(
            bm, nub, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0), -NUB_W / 2, NUB_W / 2))),
    ]
    obj, _, _ = boolean_solid(name, base, ops)
    return obj


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
    """a ile b'nin kesisim hacmi (kaydirici rayla carpisiyor mu diye bakmak icin)."""
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


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.abspath(argv[0]) if argv else here
    stl_dir = os.path.join(out, 'stl')
    os.makedirs(stl_dir, exist_ok=True)

    reset_scene()
    pc = make_strip()
    strip, _, _ = build_object(pc)
    report(pc.name, strip, 'kabartma=%d yazi=%d' % (len(pc.bumps), len(pc.texts)))
    for s in pc.skipped:
        print('  atlandi:', s)
    export_stl(strip, os.path.join(stl_dir, 'sayi_dogrusu.stl'))
    strip.color = (0.95, 0.93, 0.88, 1.0)
    test, _, _ = build_object(make_test())
    report(test.name, test)
    export_stl(test, os.path.join(stl_dir, 'ray_deneme.stl'))
    test.hide_render = True

    print('KAYDIRICI yari genislik=%.2f  yukari bosluk=%.2f  tirnak alt ucu=%.2f (ray ustu %.1f)'
          % (HW, PLAY, NUB_LOW, RH))
    shown = [strip]
    for name, nose, k, col in (('kaydirici_ucgen', 'ucgen', -3, (0.85, 0.2, 0.2)),
                               ('kaydirici_yuvarlak', 'yuvarlak', 4, (0.15, 0.4, 0.85))):
        use = make_slider(name, nose)
        printed = transformed(use, name + '_baski', lambda x, y, z: (x, -y, ZT - z))
        report(name, printed)
        export_stl(printed, os.path.join(stl_dir, name + '.stl'))
        printed.hide_render = True
        # kullanim konumu: k noktasinda, raya oturmus
        placed = transformed(use, name + '_yerinde',
                             lambda x, y, z, k=k: (X0 + k * UNIT + x, YR + y, T + z))
        placed.color = (*col, 1.0)
        shown.append(placed)
        # carpisma denetimi: iki oluk arasinda, yukari itilmisken yalniz tirnak raya girmeli
        probe = transformed(use, '_deneme', lambda x, y, z: (X0 + 5.0 + x, YR + y, T + z + PLAY))
        print('  %s: kaydirici yukarida iken rayla kesisim = %.2f mm3 (yalniz tirnak, ~%.1f mm basinc)'
              % (name, intersect_volume(probe, strip), DETENT))
        for o in (probe, use):
            m = o.data
            bpy.data.objects.remove(o)
            bpy.data.meshes.remove(m)

    render(shown, os.path.join(out, 'onizleme.png'), center=(L / 2, W / 2 - 6), size=232, tilt=30)
    render(shown, os.path.join(out, 'onizleme_detay.png'), center=(X0 - 20, W / 2 - 2), size=80,
           tilt=40)
    bpr = [o for o in bpy.data.objects if o.name.endswith('_baski')]
    for i, o in enumerate(bpr):
        o.hide_render = False
        o.location = (300 + i * 40, 0, 0)
        o.color = shown[i + 1].color
    render(bpr, os.path.join(out, 'onizleme_kaydirici.png'), center=(320, 0), size=90, tilt=35)
    save_blend(os.path.join(out, 'sayi_dogrusu.blend'))


main()
