"""
Bambu Lab X2D icin hazir baski projeleri (.3mf) uretir.

Calistirma (3DPrint klasorunden):
  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
      --python bambu-x2d/uret_x2d.py [-- geometri_seti_x2d ...]
Proje adi verilirse yalnizca o projeler yeniden uretilir (digerleri degismez).

Gerekenler: Bambu Studio 2.8 veya ustu (/Applications/BambuStudio.app). Bambu Studio en az bir kez
acilmis olmali; sistem on ayarlari ~/Library/Application Support/BambuStudio/system/BBL altina iner.

Ne yapar:
1. Iki renkli her STL, renk degisim yuksekliginden ikiye bolunur: zemin (filament 1) ve kabartma
   (filament 2). Bambu Studio'da ikisi tek nesnenin iki parcasi olur, duraklatma gerekmez.
   Bolme degisim yuksekliginin 0,02 mm ustunden yapilir. 0,20 mm katmanda degisim yukseklikleri
   (3,0 / 4,0 / 5,0 / 5,4) katman sinirina denk gelir: ustteki katman H+0,1'de dilimlenip kabartmaya,
   alttaki H-0,1'de dilimlenip zemine duser.
2. Sistem on ayarlari (Bambu Lab X2D 0.4 nozzle, 0.20mm Standard @BBL X2D,
   Bambu PLA Basic @BBL X2D 0.4 nozzle) miras zinciri cozulerek duz JSON'a yazilir; komut satiri
   sistem on ayarlarinin mirasini kendisi cozmuyor (filament yogunlugu 0 cikiyor).
3. Parcalar plakalara elle dizilir (asagidaki SETS tablosu) ve prime tower her plakada bos bir yere
   konur. Bambu Studio komut satiri projeyi yazar; nesne ve parca adlari Turkcelestirilir.
4. Yazilan proje dosyasi dilimlenerek denetlenir: her plaka basarili, uyari yok, tabla disina tasan
   nesne yok. Plaka basina sure ve filament miktari yazdirilir.

Bambu Studio 2.8.4 komut satirinda karsilasilan sorunlar ve secilen yol:
- Filament degisimini "height range" (yukseklik araligi) ile vermek komut satirini cokertiyor;
  bu yuzden parca bolme kullanildi.
- Otomatik dizme X2D'de prime tower'i 2. plakada iletkinin ustune koydu (G-code cakismasi);
  bu yuzden plakalar elle dizildi.
"""
import bpy
import bmesh
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from xml.sax.saxutils import escape
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                                  # 3DPrint
BAMBU = '/Applications/BambuStudio.app/Contents/MacOS/BambuStudio'
PROFILES = [os.path.expanduser('~/Library/Application Support/BambuStudio/system/BBL'),
            '/Applications/BambuStudio.app/Contents/Resources/profiles/BBL']
MACHINE = 'Bambu Lab X2D 0.4 nozzle'
PROCESS = '0.20mm Standard @BBL X2D'
FILAMENT = 'Bambu PLA Basic @BBL X2D 0.4 nozzle'
BED = 'Textured PEI Plate'
SPLIT_UP = 0.02         # bolme duzleminin degisim yuksekliginden yukarida kalma miktari

BEYAZ, SIYAH, KIRMIZI, MAVI = '#FFFFFF', '#000000', '#C12E1F', '#0A2989'   # Bambu PLA Basic

PLATE = 256.0          # X2D tablasi (mm)
SAFE_X0 = 22.0         # ikinci (Bowden) nozul x < 20,5 mm'ye ulasamaz; parcalar bunun sagina dizilir


def item(rel, label, h=None, fil=None, at=(0, 0), rot=0):
    """Plakadaki bir parca.

    h: renk degisim yuksekligi (iki renkli parca); None ise parca tek renk ve `fil` filamentiyle basilir.
    at: parcanin tabandaki sinir kutusunun sol alt kosesi (plaka koordinati, mm).
    rot: z ekseni etrafinda donus (derece), dizmeden once uygulanir.
    """
    return dict(rel=rel, label=label, h=h, fil=fil, at=at, rot=rot)


def kesir_grid(ns):
    """Dort kesir dairesi 2 x 2 dizilir; prime tower ortadaki bosluga gelir."""
    cells = [(24, 6), (147, 6), (24, 145), (147, 145)]
    return [item('kesir-seti/stl/kesir_1_%d.stl' % n, 'Kesir 1/%d' % n, 4.0, at=c) for n, c in zip(ns, cells)]


def pin_grid(rel, label, fil, x0, y0, cols=6, rows=2, step=15):
    """Ayni pimden cols x rows tane; her biri ayri nesne (Bambu Studio'da tek tek silinebilir)."""
    return [item(rel, '%s %d' % (label, r * cols + c + 1), fil=fil, at=(x0 + step * c, y0 + step * r))
            for r in range(rows) for c in range(cols)]


# (dosya, baslik, filament renkleri, plakalar)
# plaka: ad, prime tower'in sol alt kosesi, nesne nesne basim (by object) mi, parcalar
SETS = [
    ('geometri_seti_x2d', 'Geometri seti', [BEYAZ, SIYAH], [
        # Daire cetveli ve delik deneme parcasi, gonyelerin hipotenusu ile tablanin sag kenari
        # arasindaki bos seride dik konur.
        dict(name='1 - Cetvel, 45° gönye ve daire çizim cetveli', tower=(210, 205), items=[
            item('geometri-seti/stl/cetvel_20cm.stl', 'Cetvel 20 cm', 3.0, at=(30, 12)),
            item('geometri-seti/stl/gonye_45.stl', 'Gönye 45°', 3.0, at=(30, 54)),
            item('daire-cetveli/stl/daire_cetveli.stl', 'Daire çizim cetveli', 3.0, at=(214, 62), rot=90)]),
        # 30-60 gonye uzun kenari yatay, dik kosesi solda ustte; iletkinin duz kenarinin altina girer
        dict(name='2 - İletki, 30°-60° gönye ve delik deneme', tower=(215, 20), items=[
            item('geometri-seti/stl/iletki_180.stl', 'İletki 180°', 3.0, at=(28, 140)),
            item('geometri-seti/stl/gonye_30_60.stl', 'Gönye 30°-60°', 3.0, at=(28, 25), rot=-90),
            item('daire-cetveli/stl/delik_deneme.stl', 'Delik deneme', 3.0, at=(224, 62), rot=90)]),
    ]),
    ('kesir_seti_x2d', 'Kesir seti', [BEYAZ, SIYAH], [
        # Plaka adinda "/" olursa komut satiri adi siliyor; kesirler yaziyla yazildi.
        dict(name='1 - Tabak ve bütün', tower=(200, 185), items=[
            item('kesir-seti/stl/tabak.stl', 'Tabak', 5.4, at=(26, 8)),
            item('kesir-seti/stl/kesir_1_1.stl', 'Kesir 1/1', 4.0, at=(148, 8))]),
        dict(name='2 - Yarım, üçte bir, çeyrek, beşte bir', tower=(125.5, 115.5),
             items=kesir_grid((2, 3, 4, 5))),
        dict(name='3 - Altıda, sekizde, onda, on ikide bir', tower=(125.5, 115.5),
             items=kesir_grid((6, 8, 10, 12))),
    ]),
    # Kaydiricilar ve deneme rayi nesne nesne basilir: her renk bir kez degisir, her katmanda degil.
    ('sayi_dogrusu_x2d', 'Sayı doğrusu', [BEYAZ, SIYAH, KIRMIZI, MAVI], [
        dict(name='1 - Deneme rayı ve kaydırıcılar', seq=True, items=[
            item('sayi-dogrusu/stl/ray_deneme.stl', 'Deneme rayı', 3.0, at=(40, 40)),
            item('sayi-dogrusu/stl/kaydirici_ucgen.stl', 'Kaydırıcı (üçgen uçlu)', fil=3, at=(130, 120)),
            item('sayi-dogrusu/stl/kaydirici_yuvarlak.stl', 'Kaydırıcı (yuvarlak uçlu)', fil=4, at=(190, 190))]),
        dict(name='2 - Sayı doğrusu', tower=(200, 190), items=[
            item('sayi-dogrusu/stl/sayi_dogrusu.stl', 'Sayı doğrusu', 3.0, at=(30, 100))]),
    ]),
    # Pim deneme parcasi pimlerle ayni plakada ve kirmizi basilir: plakada iki filament olur, her
    # biri bir nozulda; katman katman renk degisimi olmaz. Tahta, delik olcusu secildikten sonra basilir.
    ('koordinat_tahtasi_x2d', 'Koordinat tahtası', [BEYAZ, SIYAH, KIRMIZI, MAVI], [
        dict(name='1 - Pim deneme ve pimler', tower=(200, 200), items=[
            item('koordinat-tahtasi/stl/pim_deneme.stl', 'Pim deneme', fil=3, at=(30, 20))]
            + pin_grid('koordinat-tahtasi/stl/pim_yuvarlak.stl', 'Pim (yuvarlak baş)', 3, 30, 60)
            + pin_grid('koordinat-tahtasi/stl/pim_kare.stl', 'Pim (kare baş)', 4, 30, 100)),
        dict(name='2 - Koordinat tahtası', tower=(200, 212), items=[
            item('koordinat-tahtasi/stl/koordinat_tahtasi.stl', 'Koordinat tahtası', 5.0, at=(30, 6))]),
    ]),
    # Isaret pimleri ve pim deneme parcasi tek renk (kirmizi); plakada renk degisimi yok. Pim
    # deneme parcasi koordinat tahtasininkiyle ayni (delikler ayni); orada basildiysa silinebilir.
    ('yuzluk_tablo_x2d', 'Yüzlük tablo', [BEYAZ, SIYAH, KIRMIZI], [
        dict(name='1 - Pim deneme ve işaret pimleri', items=[
            item('koordinat-tahtasi/stl/pim_deneme.stl', 'Pim deneme', fil=3, at=(30, 20))]
            + pin_grid('yuzluk-tablo/stl/isaret_pimi.stl', 'İşaret pimi', 3, 30, 60, cols=10, rows=5, step=13)),
        dict(name='2 - Yüzlük tablo', tower=(195, 216), items=[
            item('yuzluk-tablo/stl/yuzluk_tablo.stl', 'Yüzlük tablo', 5.0, at=(26, 4))]),
    ]),
]


# --- Bambu on ayarlari -------------------------------------------------------------------------

def profile_dir():
    for d in PROFILES:
        if os.path.exists(d + '.json') or os.path.exists(os.path.join(d, 'machine')):
            return d
    raise SystemExit('Bambu Studio on ayarlari bulunamadi')


def flat_presets(out_dir):
    """Sistem on ayarlarini miras zinciri cozulmus tek JSON olarak yazar."""
    base = profile_dir()
    index = os.path.join(os.path.dirname(base), 'BBL.json')
    paths = {}
    for key in ('machine_model_list', 'machine_list', 'process_list', 'filament_list'):
        for e in json.load(open(index))[key]:
            paths[e['name']] = os.path.join(base, e['sub_path'])

    def resolve(name):
        d = json.load(open(paths[name]))
        out = resolve(d['inherits']) if d.get('inherits') else {}
        for inc in d.get('include', []):
            out.update(resolve(inc))
        out.update(d)
        return out

    files = {}
    for name in (MACHINE, PROCESS, FILAMENT):
        d = resolve(name)
        for k in ('inherits', 'include', 'instantiation'):
            d.pop(k, None)
        d['name'], d['from'] = name, 'system'
        files[name] = os.path.join(out_dir, name + '.json')
        json.dump(d, open(files[name], 'w'), indent=1)
    return files


# --- STL bolme ---------------------------------------------------------------------------------

def mesh_stats(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    open_edges = sum(1 for e in bm.edges if not e.is_manifold)
    vol = bm.calc_volume()
    bm.free()
    return open_edges, vol


def slab(z0, z1):
    me = bpy.data.meshes.new('kutu')
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = -1000 if v.co.x < 0 else 1000
        v.co.y = -1000 if v.co.y < 0 else 1000
        v.co.z = z0 if v.co.z < 0 else z1
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new('kutu', me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def export_selected(ob, path):
    for o in bpy.context.scene.objects:
        o.select_set(o is ob)
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)


def prepare(it, out_base):
    """STL'yi dondurur, sinir kutusunun sol alt kosesini orijine tasir ve yazar.

    Iki renkli parca h + SPLIT_UP duzleminden ikiye bolunur (<out_base>_zemin.stl ve _kabartma.stl),
    tek renkli parca oldugu gibi yazilir (<out_base>_tek.stl). Plakadaki genisligi doner.
    """
    src = os.path.join(ROOT, it['rel'])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.stl_import(filepath=src)
    whole = bpy.context.selected_objects[0]
    me = whole.data
    me.transform(Matrix.Rotation(math.radians(it['rot']), 4, 'Z'))
    lo = [min(v.co[a] for v in me.vertices) for a in range(3)]
    me.transform(Matrix.Translation((-lo[0], -lo[1], -lo[2])))
    size = [max(v.co[a] for v in me.vertices) for a in range(2)]
    x0, y0 = it['at']
    if x0 < SAFE_X0 or y0 < 2 or x0 + size[0] > PLATE - 2 or y0 + size[1] > PLATE - 2:
        raise SystemExit('%s plakaya sigmiyor: %.1f..%.1f x %.1f..%.1f'
                         % (it['rel'], x0, x0 + size[0], y0, y0 + size[1]))
    if it['h'] is None:
        export_selected(whole, out_base + '_tek.stl')
        return size
    _, vol0 = mesh_stats(whole)
    z = it['h'] + SPLIT_UP
    vols = []
    for suffix, z0, z1 in (('zemin', -1.0, z), ('kabartma', z, 1000.0)):
        # EXACT cok noktali tahtada (yuzluk tablo) ust yuzde acik kenar birakiyor; o zaman MANIFOLD
        for solver in ('EXACT', 'MANIFOLD'):
            ob = whole.copy()
            ob.data = whole.data.copy()
            bpy.context.scene.collection.objects.link(ob)
            cut = slab(z0, z1)
            mod = ob.modifiers.new('kes', 'BOOLEAN')
            mod.operation, mod.solver, mod.object = 'INTERSECT', solver, cut
            bpy.context.view_layer.objects.active = ob
            bpy.ops.object.modifier_apply(modifier=mod.name)
            bpy.data.objects.remove(cut)
            open_edges, vol = mesh_stats(ob)
            if open_edges == 0 and vol > 0:
                break
            print('  %s %s: %s ile acik kenar=%d hacim=%.1f' % (it['rel'], suffix, solver, open_edges, vol))
            m = ob.data
            bpy.data.objects.remove(ob)
            bpy.data.meshes.remove(m)
        else:
            raise SystemExit('%s %s: bolunemedi' % (src, suffix))
        export_selected(ob, '%s_%s.stl' % (out_base, suffix))
        vols.append(vol)
    if abs(sum(vols) - vol0) > 0.002 * vol0:
        raise SystemExit('%s: parcalarin hacmi tutmuyor (%.1f + %.1f != %.1f)' % (src, vols[0], vols[1], vol0))
    print('BOL %-42s h=%.1f zemin %5.1f cm3, kabartma %4.2f cm3'
          % (it['rel'], it['h'], vols[0] / 1000, vols[1] / 1000))
    return size


# --- Proje -------------------------------------------------------------------------------------

def run_bambu(args, out_dir):
    log = os.path.join(out_dir, 'bambu.log')
    with open(log, 'w') as f:
        rc = subprocess.call([BAMBU, '--debug', '2'] + args, stdout=f, stderr=subprocess.STDOUT, cwd=out_dir)
    res_path = os.path.join(out_dir, 'result.json')
    res = json.load(open(res_path)) if os.path.exists(res_path) else {}
    if rc != 0 or res.get('return_code', -1) != 0:
        raise SystemExit('Bambu Studio hatasi (cikis %d, %s), kayit: %s' % (rc, res.get('error_string'), log))
    return res


def finish_project(path, names):
    """Komut satirinin yazdigi projeyi tamamlar.

    - assemble_K nesnelerine ve pK_<tur>_1 parcalarina okunur adlar verir.
    - extruder_nozzle_stats bos yaziliyor; boyle bir proje dilimlenirken "No valid nozzle found"
      hatasi veriyor. Bambu Studio'nun dilimlerken yazdigi degerle (her nozulda bir Standard
      nozul) doldurulur.
    """
    def obj(m):
        return 'value=%s' % json.dumps(names[int(m.group(1))], ensure_ascii=False)

    def part(m):
        label = {'zemin': 'zemin', 'kabartma': 'kabartma', 'tek': 'tek renk'}[m.group(2)]
        return 'value="%s - %s"' % (escape(names[int(m.group(1))]), label)

    tmp = path + '.tmp'
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == 'Metadata/model_settings.config':
                text = data.decode('utf-8')
                text = re.sub(r'value="assemble_(\d+)"', obj, text)
                text = re.sub(r'value="p(\d+)_(zemin|kabartma|tek)_1"', part, text)
                data = text.encode('utf-8')
            elif item.filename == 'Metadata/project_settings.config':
                cfg = json.loads(data)
                stats = ['%s#1' % t for t in cfg['nozzle_volume_type']]
                for key in ('extruder_nozzle_stats', 'extruder_nozzle_stats_new'):
                    if not cfg.get(key):
                        cfg[key] = stats
                data = json.dumps(cfg, indent=4, ensure_ascii=False).encode('utf-8')
            zout.writestr(item, data)
    os.replace(tmp, path)


def build_set(fname, title, colours, plates, presets, work):
    n_fil = len(colours)
    names, plate_json, k = {}, [], 0
    tower_x, tower_y = [], []
    for plate in plates:
        objs, obj_params = [], []
        for it in plate['items']:
            k += 1
            names[k] = it['label']
            base = os.path.join(work, 'p%d' % k)
            prepare(it, base)
            pos = {'count': 1, 'assemble_index': [k], 'pos_x': [it['at'][0]], 'pos_y': [it['at'][1]], 'pos_z': [0]}
            if it['h'] is None:
                objs.append(dict(pos, path=base + '_tek.stl', filaments=[it['fil']]))
                # Tek parcali nesnede parcanin filamenti projeye yazilirken kayboluyor (nesne
                # filament 1'e dusuyor); filament nesnenin kendisine de verilir.
                obj_params.append({'assemble_index': k, 'print_params': {'extruder': str(it['fil'])}})
            else:
                objs.append(dict(pos, path=base + '_zemin.stl', filaments=[1]))
                objs.append(dict(pos, path=base + '_kabartma.stl', filaments=[2]))
        p = {'plate_name': plate['name'], 'need_arrange': False, 'objects': objs}
        if obj_params:
            p['assembled_params'] = obj_params
        if plate.get('seq'):
            p['plate_params'] = {'print_sequence': 'by object'}
        plate_json.append(p)
        tx, ty = plate.get('tower', (200, 200))
        tower_x.append('%g' % tx)
        tower_y.append('%g' % ty)
    asm = os.path.join(work, fname + '_plakalar.json')
    json.dump({'plates': plate_json}, open(asm, 'w'), ensure_ascii=False, indent=1)

    run_bambu(['--load-settings', '%s;%s' % (presets[MACHINE], presets[PROCESS]),
               '--load-filaments', ';'.join([presets[FILAMENT]] * n_fil),
               '--filament-colour', ';'.join(colours),
               '--curr-bed-type', BED,
               '--wipe-tower-x', ','.join(tower_x), '--wipe-tower-y', ','.join(tower_y),
               '--metadata-name', 'Title;Designer',
               '--metadata-value', '%s (Bambu Lab X2D);dokunduyogren.com' % title,
               '--load-assemble-list', asm,
               '--outputdir', work, '--export-3mf', fname + '.3mf'], work)
    out = os.path.join(HERE, fname + '.3mf')
    shutil.move(os.path.join(work, fname + '.3mf'), out)
    finish_project(out, names)
    return out


def check_set(path, work):
    """Projeyi dilimler; her plakanin basarili ve tabla icinde oldugunu denetler."""
    chk = os.path.join(work, 'denetim_' + os.path.splitext(os.path.basename(path))[0])
    os.makedirs(chk, exist_ok=True)
    res = run_bambu(['--slice', '0', '--outputdir', chk, '--export-3mf', 'dilimli.gcode.3mf', path], chk)
    with zipfile.ZipFile(os.path.join(chk, 'dilimli.gcode.3mf')) as z:
        z.extractall(os.path.join(chk, 'x'))
        info = z.read('Metadata/slice_info.config').decode('utf-8')
        settings = z.read('Metadata/model_settings.config').decode('utf-8')
    plate_names = re.findall(r'key="plater_name" value="([^"]*)"', settings)
    outside = re.findall(r'key="outside" value="(\w+)"', info)
    total_min, total_g = 0, 0.0
    print('PROJE %s' % os.path.relpath(path, ROOT))
    for p, name, out in zip(res['sliced_plates'], plate_names, outside):
        if out != 'false' or p.get('warning_message'):
            raise SystemExit('plaka %d (%s): disari tasan=%s uyari=%s' % (p['id'], name, out, p.get('warning_message')))
        grams = ', '.join('F%d %.1f g' % (f['id'], f['total_used_g']) for f in p['filaments'])
        minutes = p['total_predication'] / 60
        total_min += minutes
        total_g += sum(f['total_used_g'] for f in p['filaments'])
        print('  PLAKA %d %-30s %4.0f dk  %s  filament degisimi %d'
              % (p['id'], name, minutes, grams, p['filament_change_times']))
    print('  TOPLAM %.0f dk, %.0f g, %.1f MB, denetim: %s'
          % (total_min, total_g, os.path.getsize(path) / 1e6, chk))


def main():
    only = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    work = tempfile.mkdtemp(prefix='x2d_')
    presets = flat_presets(work)
    for fname, title, colours, plates in SETS:
        if only and fname not in only:
            continue
        out = build_set(fname, title, colours, plates, presets, work)
        check_set(out, work)


main()
