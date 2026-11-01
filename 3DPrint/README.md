# 3D Baskı Dokunsal Ders Araçları

Görme engelli ve az gören öğrenciler için 3D yazıcıyla basılan ders araçları. Modeller
Blender'da Python betikleriyle parametrik olarak üretilir. Web sayfası: [`index.html`](index.html).

## Klasörler

| Klasör | İçerik |
|---|---|
| [`ortak/`](ortak/dokunsal.py) | Ortak kütüphane: dokunsal kodlama ölçüleri, Türk Braille, büyük punto yazı, boolean ve STL yardımcıları |
| [`geometri-seti/`](geometri-seti/) | 20 cm cetvel, 45° ve 30°-60° gönye, 180° iletki |
| [`kesir-seti/`](kesir-seti/) | 1/1–1/12 kesir daireleri ve tabak |
| [`sayi-dogrusu/`](sayi-dogrusu/) | −10…+10 sayı doğrusu, iki kaydırıcı ve deneme rayı |
| [`daire-cetveli/`](daire-cetveli/) | Daire çizim cetveli (pergel yerine) ve delik deneme parçası |
| [`koordinat-tahtasi/`](koordinat-tahtasi/) | Koordinat ve geometri tahtası, yuvarlak ve kare başlı pimler, pim deneme parçası |
| [`bambu-x2d/`](bambu-x2d/) | Bambu Lab X2D için hazır Bambu Studio projeleri (.3mf) ve onları üreten betik |
| [`ruler-01/`](ruler-01/) | İlk 10 cm dokunsal cetvel (STL ve G-code) |
| [`onizleme/`](onizleme/) | Web sayfasındaki görseller ([`onizleme_uret.py`](onizleme_uret.py) üretir) |

## Üretme

Her betik STL'leri `stl/` klasörüne, önizlemeleri ve `.blend` dosyasını kendi klasörüne yazar:

```sh
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
    --python sayi-dogrusu/generate_sayi_dogrusu.py
```

Çıktıda her parça için bir `PARCA` satırı yazar: boyut, hacim, gövde sayısı, açık kenar ve
tablaya sığıp sığmadığı. `acik kenar=0` ve beklenen gövde sayısı görülmeden STL kullanılmamalı.

STL'ler değişince Bambu Lab X2D projelerini de yeniden üretin (Bambu Studio 2.8 veya üstü gerekir):

```sh
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
    --python bambu-x2d/uret_x2d.py
```

Betik iki renkli parçaları zemin ve kabartma diye ikiye böler, plakalara dizer, projeyi Bambu
Studio'nun komut satırıyla yazar ve yazılan projeyi dilimleyerek denetler. Her plaka için bir
`PLAKA` satırı (süre, filament) yazar. Yeni bir parça eklenince betikteki `SETS` tablosuna
plakadaki yeriyle birlikte eklenmeli. Yalnızca bir projeyi yeniden üretmek için komutun sonuna
proje adını ekleyin (`-- geometri_seti_x2d`); diğer 3MF dosyaları değişmez.

## Ortak kurallar

- **Dokunsal kodlama:** küçük nokta 1 cm / 10°, büyük nokta 5 cm / 30° / başlangıç, çizgi 10 cm / 90°.
  Bütün araçlarda aynı kalır.
- **Çift format:** Braille'in yanında az gören öğrenciler için büyük punto (en az ~18 punto).
- **Kontrast:** Kabartmalar zeminden ayrı renkte basılır. Duraklatma yükseklikleri: geometri seti,
  daire çizim cetveli ve sayı doğrusu 3,0 mm, kesir parçaları 4,0 mm, koordinat tahtası 5,0 mm,
  tabak 5,4 mm.
- **Boyut:** Her parça 220 × 220 mm tablaya (Ender 3 S1) sığar. Küçük çocuklarda yutma riskine
  karşı parçaların 30 mm'nin altına inmemesi hedeflenir. İstisnalar 24 mm'lik kaydırıcılar ve
  10 mm'lik pimler; küçük yaşta gözetimle kullanılmalı (web sayfasında pimler için uyarı var).

## Yapılacaklar

Bir maddeyi bitirince `[ ]` işaretini `[x]` yapın.

### Önerilen sıra

1. Geometri setine büyük punto rakamlar (daire çizim cetvelindeki gibi)
2. SVG'den kabartma plaka aracı (katmanlı bir örnek SVG gerekiyor)
3. Pimli tahta ailesinin devamı: sütun grafik, yüzlük tablo (koordinat tahtasının pimini ve deliğini
   kullanır)
4. Kesir çubukları ve onluk taban blokları

### Deneme ve onay

- [ ] Kesir Braille yazımını (pay normal rakam, payda alt rakam) bir Braille öğretmenine onaylatmak
- [ ] Negatif sayı Braille yazımını (sayı işareti + 5-6, 3-6 + rakam) bir Braille öğretmenine onaylatmak
- [ ] Tabak ve 1/4 seti deneme baskısı: pim, 0,5 mm kenar boşluğu, 0,3 mm parça aralığı, parmak oyuğu
- [ ] `89b8b91` öncesi basılmış tabakları yeniden basmak (eski parmak oyuğu cebe çıkıntı yapıyordu)
- [ ] Deneme rayı ve kaydırıcı baskısı: sıkılık (`CLEAR`) ve tık gücü (`DETENT`)
- [ ] Daire çizim cetveli denemesi: delik deneme parçasıyla tükenmez ve kurşun kaleme göre
      `HOLE_D` seçimi; çizim altlığında raptiyeyle ve merkezde dik tutulan kalemle daire çizmek
- [ ] Koordinat tahtası denemesi: pim deneme parçasıyla `HOLE_D` seçimi; lastik gerilince pimin dik
      durması; yuvarlak ve kare başın dokunarak ayırt edilmesi; eksen çizgilerinin ve orijinin
      parmakla bulunması
- [ ] Bambu Lab X2D projelerini Bambu Studio arayüzünde açıp birer plaka basmak (komut satırında
      dilimlenip denetlendi, arayüzde ve yazıcıda denenmedi)
- [ ] Bir öğretmen ve birkaç öğrenciyle sınıf denemesi, geri bildirimlerin buraya işlenmesi

### 1. kutu: Matematik ve geometri

- [x] Geometri seti: cetvel, gönyeler, iletki, kalem çentikleri
- [ ] Geometri setine büyük punto rakamlar
- [ ] Bütün plakalarda aynı köşede yön işareti
- [x] Kesir daireleri ve tabak
- [ ] Kesir parçalarına paydaya göre yüzey dokusu (isteğe bağlı; şu an renk, Braille ve büyük punto var)
- [x] Sayı doğrusu, iki kaydırıcı, deneme rayı
- [ ] Sayı doğrusunda negatif tarafı dokuyla ayırmak
- [ ] Sayı doğrusunun büyük sürümü (−5…+5, 2 cm birim, daha büyük rakam; ağır az görme için)
- [ ] Kaydırıcıları 30 mm'nin üstüne büyütmeyi değerlendirmek (yutma riski)
- [x] Daire çizim cetveli (pergel yerine): merkez deliği, 1–10 cm arası her 0,5 cm'de kalem deliği
- [x] Koordinat ve geometri tahtası: 11 × 11 delik, kabartma eksenler, yuvarlak ve kare başlı pimler, lastik
- [ ] Geometrik cisimler: küp, prizma, piramit, silindir, koni, küre
- [ ] Dokunsal saat: sürtünmeli akrep ve yelkovan
- [ ] Döner kollu açı modeli: 30°, 45°, 60° ve 90°'de tık diye oturur

### 2. kutu: Fen

- [ ] Ay'ın evreleri: 8 disk ve halka tepsi, aydınlık kısım dokulu
- [ ] Hayvan ve bitki hücresi: her organel ayrı dokuda
- [ ] DNA baz eşleşme yapbozu: A yalnız T'ye, G yalnız C'ye oturur
- [ ] Bohr atom modelleri: H, He, C, N, O, Na
- [ ] Elektrik devre karoları: pil, ampul, anahtar

### Kutu ve paket

- [ ] Kalıp tepsiler: her parçanın kendi yuvası
- [ ] Kapak etiket plakası: Braille ve büyük punto
- [ ] Öğretmen kılavuzu: her araç için bir sayfa kullanım ve etkinlik önerisi

### Altyapı

- [x] Bambu Lab X2D için hazır projeler: geometri seti, kesir seti, sayı doğrusu, koordinat tahtası
      (iki renk, duraklatmasız)
- [ ] SVG'den kabartma plaka aracı: `çizgi`, `doku-1`, `doku-2`, `etiket` katmanları; etiketler
      kendiliğinden Braille ve büyük puntoya çevrilir
- [ ] Kütüphaneye pim / delik geçmesi ve döner eksen (menteşe). Havşalı delik kütüphanede
      (`countersunk_holes`); pim şimdilik koordinat tahtası betiğinde
- [ ] MEB kazanımlarına göre konu eşlemesi: hangi konu dokunarak öğretilmeli

### Fikir havuzu

Matematik ve geometri:
- [ ] Kesir çubukları (kesir, ondalık ve yüzde karşılaştırması)
- [ ] Onluk taban blokları (birlik, onluk, yüzlük)
- [ ] Örüntü blokları (altıgen, yamuk, eşkenar dörtgen, üçgen)
- [ ] Tangram ve tepside şekil siluetleri
- [ ] Pisagor yapbozu, daire alanı yapbozu
- [ ] Sütun grafik tahtası
- [ ] Yüzlük tablo ve çarpım tablosu tahtası
- [ ] Kabartma plakalar: açı türleri, üçgen ve dörtgen çeşitleri, çemberin elemanları
- [ ] Fonksiyon grafikleri ve simetri kartları
- [ ] Cisimlerin katlanır açınımları
- [ ] Hacim karşılaştırma kapları (silindir, koni, küre)
- [ ] Denklem terazisi
- [ ] Braille zar ve olasılık çarkı
- [ ] Abaküs
- [ ] Çentikli ölçü kabı (mL)

Fen:
- [ ] Maddenin hâlleri tanecik plakaları
- [ ] Periyodik tablonun ilk 20 elementi için karolar
- [ ] Geçmeli molekül seti (top ve çubuk)
- [ ] Basit makineler: kaldıraç ve ağırlıklar
- [ ] Mercek kesitleri, Dünya'nın katmanları, çiçek ve yaprak, kalp ve göz kesiti

Diğer:
- [ ] Büyük Braille öğretim hücresi (6 delik, takılıp çıkarılan pimler)
- [ ] İmza ve yazı rehberi şablonu
- [ ] Kabartma Türkiye haritası (il sınırları, yeryüzü şekilleri)
- [ ] Anıtkabir krokisinin 3D hali
