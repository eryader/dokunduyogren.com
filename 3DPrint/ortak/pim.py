"""
Pimli tahtalar (koordinat tahtasi, yuzluk tablo) icin ortak pim ve delik.

Butun pimli tahtalarin delikleri ayni oldugu icin her pim her tahtaya uyar. Pim deneme
parcasiyla secilen delik capi burada (HOLE_D) degistirilir; sonra pimli tahtalarin betikleri
yeniden calistirilir.

Pim turleri (kullanim konumunda z = 0 tahtanin ustu, govde asagi gider):
  yuvarlak, kare : flans, 7 mm boyun ve bas. Boyna lastik takilir (geometri tahtasi).
  isaret         : tahtaya oturan alcak, yuvarlak bas. Lastik takilmaz; sayi ya da nokta
                   isaretler. Basi flans kadar genis oldugu icin tahtadaki kabartmalara degmez.
Hepsi basi tablaya gelecek sekilde ters basilir; destek gerekmez (bkz. printed_pin).
"""
import math

from dokunsal import (DOT_S, MARGIN, Piece, add_loft, boolean_solid, circle, countersunk_holes,
                      mesh_of, rounded, v2)
import bmesh
import bpy

BOARD_T = 5.0           # tahta kalinligi (pim bu kadar derine girer)
HOLE_D = 5.0            # pim deligi capi (pim deneme parcasiyla secilir)
CS_DEPTH = 0.6          # deligin ustundeki 45 derecelik havsa: pimin ucu delige kayar
TEST_DS = (4.8, 4.9, 5.0, 5.1, 5.2)

SHANK_D = 4.8           # delige giren govde
SHANK_L = BOARD_T - 0.6  # govde tahtanin altina ulasmaz (ilk katmanlardaki daralmaya degmez)
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
MARK_D, MARK_H = FLANGE_D, 5.0  # isaret pimi basi (cap, yukseklik; 5 mm parmakla tutulup cekilir)

CS_R = HOLE_D / 2 + CS_DEPTH
CLR = max(CS_R + MARGIN, FLANGE_D / 2 + 0.4)   # delik merkezinden kabartmalara en az uzaklik


def hole_keepout(centers):
    """Piece keepout'u: kabartmalar delik merkezinden en az CLR uzakta kalir (_fits MARGIN ekler)."""
    return [circle(c, CLR - MARGIN, 32) for c in centers]


def pin_holes(centers, top=BOARD_T):
    """Piece.mesh_cut icin havsali pim delikleri."""
    return countersunk_holes(centers, HOLE_D, CS_DEPTH, top)


def pin_top(kind):
    return MARK_H if kind == 'isaret' else HEAD_TOP


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
    """Kullanim konumunda pim nesnesi; kind: 'yuvarlak', 'kare' ya da 'isaret'."""
    rs = SHANK_D / 2
    shank = [(rs - SHANK_TIP, -SHANK_L), (rs, -SHANK_L + SHANK_TIP), (rs, 0.0)]

    def solid(profile, n=64):
        return lambda bm: add_loft(bm, [[(p.x, p.y, z) for p in circle(v2(0, 0), r, n)]
                                        for r, z in profile])
    if kind == 'isaret':
        rm = MARK_D / 2
        body = shank + [(rm, 0.0), (rm, MARK_H - HEAD_CH), (rm - HEAD_CH, MARK_H)]
        obj = bpy.data.objects.new(name, mesh_of(name, solid(body)))
        bpy.context.scene.collection.objects.link(obj)
        return obj
    body = shank + [(FLANGE_D / 2, 0.0), (FLANGE_D / 2, FLANGE_T), (POST_D / 2, POST_Z0),
                    (POST_D / 2, POST_Z1 + 1.0)]
    base = mesh_of(name, solid(body))
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


def printed_pin(use, name, kind):
    """Baski yonu: bas tablada, govde yukarida."""
    top = pin_top(kind)
    return transformed(use, name, lambda x, y, z: (x, -y, top - z))


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


def check_pin_fit(use, board, positions, label, top=BOARD_T):
    """Pimi tahtadaki her (x, y) deligine oturt; tahtayla kesisim hacmini yaz, en buyugunu dondur."""
    worst = 0.0
    for x0, y0 in positions:
        probe = transformed(use, '_deneme', lambda x, y, z: (x0 + x, y0 + y, top + z + 0.01))
        vol = intersect_volume(probe, board)
        print('  %s (%.1f, %.1f) deliginde tahtayla kesisim = %.3f mm3' % (label, x0, y0, vol))
        worst = max(worst, vol)
        m = probe.data
        bpy.data.objects.remove(probe)
        bpy.data.meshes.remove(m)
    return worst


def make_pin_test(num_h, pitch=16.0, x0=10.0):
    """pim_deneme: TEST_DS caplarinda bes delik; ustunde 1-5 nokta, altinda olcu."""
    L = 2 * x0 + pitch * (len(TEST_DS) - 1)
    outer = rounded([v2(0, -10.5), v2(L, -10.5), v2(L, 9.5), v2(0, 9.5)], 3.0)
    centers = [v2(x0 + pitch * i, 0) for i in range(len(TEST_DS))]
    keep = [circle(c, d / 2 + CS_DEPTH, 32) for c, d in zip(centers, TEST_DS)]
    pc = Piece('pim_deneme', outer, thickness=BOARD_T, keepout=keep)
    for c, d in zip(centers, TEST_DS):
        pc.mesh_cut.append(countersunk_holes([c], d, CS_DEPTH, BOARD_T))
    r_max = max(TEST_DS) / 2 + CS_DEPTH
    y_dot = r_max + MARGIN + DOT_S[0] + 0.3
    y_num = -(r_max + MARGIN + num_h / 2 + 0.3)
    for i, (c, d) in enumerate(zip(centers, TEST_DS)):
        n = i + 1
        for j in range(n):
            pc.add(c + v2((j - (n - 1) / 2) * 2.8, y_dot), None, DOT_S, '%.1f nokta %d' % (d, j))
        pc.add_text(('%.1f' % d).replace('.', ','), c + v2(0, y_num), v2(0, 1), num_h, '%.1f yazi' % d)
    return pc
