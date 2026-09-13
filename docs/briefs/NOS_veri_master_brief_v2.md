# NOS: Tercih Sihirbazı — Veri Çekme Master Brief

> Amaç: Türkiye'deki TÜM üniversitelerin TÜM lisans ve önlisans programlarının
> 2023-2024-2025 yerleştirme sonuçlarını + 2026 kontenjan/koşullarını,
> duplicate'siz ve doğrulanmış şekilde tek bir `programs.json` dosyasına dökmek.
> Bu dosya Expo uygulamasına bundle edilecek; backend yok, veri offline çalışacak.

---

## 1. KAYNAK MİMARİSİ (kesin kural)

### Yetkili kaynak — veri BURADAN çekilir
**K1. YÖK Atlas resmî JSON API** — `yokatlas.yok.gov.tr`
- Erişim: `yokatlas-py` v0.6.x Python kütüphanesi (`pip install yokatlas-py`,
  repo: github.com/saidsurucu/yokatlas-py, MIT). README.md ve API.md'yi oku.
- Her program tek istekte 4 yıllık veri döner: `current` (2025) +
  `history` (2024, 2023, 2022). Alanlar: taban puan (`min_puan`),
  başarı sırası (`basari_sirasi`), `kontenjan`, `yerlesen`.
- Arama: `SearchFilters(puan_turu=..., birim_turu_id=...)` ile sayfalı tarama.
  Sayfa boyutu 100, sayfalar arası 300ms bekle, hata halinde exponential backoff
  (5 deneme). SIRALAMA: `sort_by="basariSirasi"`.

### Resmî tamamlayıcı — 2026 kontenjan + özel koşullar
**K2. ÖSYM 2026-YKS Yükseköğretim Programları ve Kontenjanları Kılavuzu**
- `osym.gov.tr` → 21 Temmuz 2026'da yayımlandı. Tablo 4 (lisans) ve
  Tablo 3 (önlisans) PDF/XLS.
- Buradan alınacaklar: 2026 kontenjanı, "Bakınız" özel koşul kodları,
  yeni açılan programlar (YÖK Atlas'ta geçmişi olmayanlar).
- Eşleştirme anahtarı: ÖSYM program kodu = YÖK Atlas `kilavuz_kodu`.

### Doğrulama kaynakları — veri ÇEKİLMEZ, sadece karşılaştırılır
**K3.** basarisiralamalari.com — rastgele 20 program için 2025 taban
puan/sıralama karşılaştırması
**K4.** kariyer.net/universite-taban-puanlari — aynı 20 program
**K5.** YÖK Atlas web arayüzünün kendisi — 10 programı elle aç, API çıktısıyla
birebir karşılaştır (API ↔ site tutarlılık testi)

> KURAL: K3/K4 ile K1 çelişirse doğru olan K1'dir; ama çelişki oranı %5'i
> geçerse export pipeline'ında hata var demektir — yayın DURDURULUR.

---

## 2. ÇEKİLECEK EVREN (eksiksiz kapsam tanımı)

Aşağıdaki kombinasyonların TAMAMI taranacak:

| Boyut | Değerler |
|---|---|
| Puan türü | SAY, EA, SÖZ, DİL (lisans) + TYT (önlisans) |
| Birim türü | 46 = LİSANS, 47 = ÖNLİSANS |
| Üniversite türü | Devlet, Vakıf, KKTC ve yurt dışı dahil HEPSİ (filtre uygulama) |
| Öğrenim türü | Örgün, İkinci Öğretim, Açıköğretim, Uzaktan — HEPSİ |
| Burs varyantları | Burslu, %75, %50, %25 indirimli, Ücretli — HEPSİ AYRI SATIR |

Dikkat: puan türü kodları "sa/söz" değil, resmî kodlar **SAY / EA / SÖZ / DİL /
TYT**'dir. TYT yalnızca önlisansta, diğer dördü yalnızca lisansta geçerlidir —
çapraz kombinasyonları sorgulamaya çalışma (boş döner, zaman kaybı).

Beklenen toplam: ~27.000 ± 3.000 program satırı. 15.000 altı veya 40.000 üstü
çıkarsa tarama eksik/hatalı demektir.

---

## 3. DUPLICATE ÖNLEME (kesin kurallar)

1. **Birincil anahtar = `kilavuz_kodu`** (ÖSYM program kodu). Aynı kod ikinci
   kez görülürse üzerine yazılmaz, ilk kayıt korunur, olay loglanır.
2. Bir bölümün her burs oranı ve her öğrenim türü AYRI kilavuz kodudur ve AYRI
   satırdır — bunlar duplicate DEĞİLDİR. (Örn. Koç Tıp Burslu ve Koç Tıp Ücretli
   iki ayrı kayıttır.) Deduplication SADECE kilavuz kodu üzerinden yapılır,
   üniversite+bölüm adı üzerinden ASLA yapılmaz.
3. Farklı puan türü taramalarında aynı program tekrar gelebilir (nadiren) —
   kilavuz kodu anahtarı bunu otomatik çözer.
4. Export sonunda assert: `len(rows) == len(set(kilavuz_kodu'lar))`.

---

## 4. VERİ ŞEMASI (çıktı formatı)

`programs.json` — tek dosya, minify edilmiş, UTF-8:

```json
{
  "meta": {
    "exportedAt": "ISO-8601",
    "source": "yokatlas.yok.gov.tr + ÖSYM 2026 Kılavuzu",
    "programCount": 0,
    "sha256": "..."
  },
  "programs": [
    {
      "id": 102210277,          // kilavuz_kodu — BİRİNCİL ANAHTAR
      "uni": "BOĞAZİÇİ ÜNİVERSİTESİ",
      "uniTur": "DEVLET",       // DEVLET | VAKIF | KKTC | YURTDIŞI
      "prog": "Bilgisayar Mühendisliği (İngilizce)",
      "grup": "Bilgisayar Mühendisliği",  // normalize ad — filtre bu alandan
      "il": "İSTANBUL",
      "puanTuru": "SAY",
      "dil": "İngilizce",
      "ogrTur": "Örgün",
      "burs": null,             // vakıfsa: "Burslu" | "%50 İndirimli" | ...
      "sure": 4,
      "kosul": ["17", "21"],   // 2026 kılavuzu Bakınız kodları (K2'den)
      "kont2026": 120,          // 2026 kontenjanı (K2'den)
      "yillar": [               // yeni → eski; 2026 sonuç verisi YOKTUR
        {"y": 2025, "k": 115, "z": 115, "p": 541.2, "s": 1050},
        {"y": 2024, "k": 110, "z": 110, "p": 538.7, "s": 980},
        {"y": 2023, "k": 110, "z": 110, "p": 535.1, "s": 1120}
      ]
    }
  ]
}
```

Null kuralları: dolmayan bölümde `p` ve `s` null olabilir — 0 YAZMA, null bırak.
Yeni açılan bölümde `yillar` boş dizi olabilir; uygulama "yeni program, geçmiş
veri yok" rozetini bu boş diziden üretecek.

---

## 5. BİLİNEN TUZAKLAR (agent bunları elle handle edecek)

- **Dolmayan bölümler:** taban puan/sıralama null gelir. Sihirbaz mantığında
  "null = herkese güvenli tercih" olarak işaretlenecek, sıfır sanılmayacak.
- **Yeni açılan programlar (2026):** K2 kılavuzunda var, K1'de geçmişi yok.
  Bunlar es geçilmeyecek, `yillar: []` ile eklenecek.
- **Kapanan programlar:** K1'de geçmişi var ama K2 2026 kılavuzunda yok →
  `kont2026: null` işaretle; uygulama bunları listeden GİZLEYECEK
  (tercih edilemez).
- **İsim normalizasyonu:** "Bilgisayar Müh." / "Bilgisayar Mühendisliği (İng.)"
  varyantlarını `grup` alanı (YÖK Atlas `birim_grup_adi`) çözer — kendi regex
  normalizasyonunu YAZMA, YÖK Atlas'ın grup alanını kullan.
- **Türkçe karakter/locale:** JSON UTF-8; "İ/ı" dönüşümlerinde asla
  `toLowerCase` (JS) / `lower()` (Py) locale'siz kullanma; aramada
  Türkçe-insensitive normalize katmanı uygulama tarafında olacak.
- **KKTC + yurt dışı üniversiteler** kılavuzda vardır, atlanmayacak.
- **Sıralama tipi:** başarı sırası int'tir ama "80.000" gibi noktalı string
  gelebilecek her yerde parse güvenliği kur.

---

## 6. DOĞRULAMA PROTOKOLÜ (yayın kapısı — hepsi geçmeden bundle edilmez)

1. **Hacim:** 15.000 < programCount < 40.000; her puan türünde > 0 kayıt.
2. **Duplicate:** kilavuz kodu tekilliği assert'i geçti.
3. **Referans seti (altın örnekler, elle kontrol):**
   - Boğaziçi Bilgisayar Müh. (SAY) → 2025 sıralaması < 3.000
   - Herhangi bir devlet Tıp (SAY) → sıralama < 60.000
   - Bir Hukuk (EA), bir PDR (SÖZ→EA kontrol), bir İng. Öğretmenliği (DİL),
     bir önlisans Anestezi (TYT) örneği YÖK Atlas sitesinden birebir doğrulanacak.
4. **Çapraz kaynak:** rastgele 20 program K3 ve K4 ile karşılaştırılır;
   sapma > %5 ise yayın durur.
5. **Yıl bütünlüğü:** kayıtların en az %70'inde 2023+2024+2025 üçü de dolu.
6. **Tutarlılık:** hiçbir kayıtta yerlesen > kontenjan olamaz (İÖ ek kontenjan
   istisnaları loglanır); taban puan 100-560 aralığında olmalı.
7. Sonuç raporu: `validation_report.md` — sayılar, null oranları, çelişki
   listesi, checksum. Bu rapor insan onayına sunulmadan bundle YAPILMAZ.

---

## 7. TERCİH SİHİRBAZI İÇİN MOTOR SÖZLEŞMESİ (verinin kullanım şekli)

- Eşleştirme SIRALAMA ile yapılır, puanla ASLA yapılmaz.
- Kullanıcı sırası `S`, programın 2025 sıralaması `P` olmak üzere:
  - `S < P × 0.85` → **Güven**
  - `P × 0.85 ≤ S ≤ P × 1.10` → **Denge**
  - `P × 1.10 < S ≤ P × 1.35` → **Hedef**
  - üstü → listelenmez (ama "hayal bölümüm" aramasında görünür)
  - Eşikler config'de tutulur, hardcode edilmez.
- Trend düzeltmesi: 3 yılda sıralaması istikrarlı iyileşen (rakam küçülen)
  bölümlere "yükselen bölüm ⚠" rozeti; Denge sınıfındaysa Hedef'e kaydır.
- Null sıralamalı (dolmamış) bölümler → Güven, "geçen yıl dolmadı" rozetiyle.
- `kont2026` null olanlar (kapanan) hiçbir sonuçta gösterilmez.

---

## 8. GÜNCELLEME DÖNGÜSÜ (backend'siz)

- Export scripti tercih dönemi boyunca günde 1 kez yeniden koşulur
  (YÖK Atlas/ÖSYM düzeltme yayımlayabilir).
- Yeni `programs.json` GitHub Releases'a yüklenir; uygulama açılışta
  `meta.sha256` karşılaştırıp değişmişse indirir. İndirme başarısızsa
  bundled kopyayla çalışmaya devam eder (offline garantisi bozulmaz).

---

## 9. OUTBOX PIPELINE (repo yapısı ve tek komutla çalışma)

Veri çekme işi repo kökünde `OUTBOX/` klasöründe yaşar ve uygulama kodundan
tamamen izoledir. Uygulama, OUTBOX'un ürettiği çıktıları sadece TÜKETİR.

### Klasör yapısı
```
OUTBOX/
├── run.py                  # TEK GİRİŞ NOKTASI — tüm pipeline'ı tetikler
├── pipeline/
│   ├── fetch.py            # K1 (YÖK Atlas API) + K2 (ÖSYM kılavuz) çekme
│   ├── merge.py            # K1+K2 birleştirme, dedup (kilavuz_kodu)
│   ├── validate.py         # Bölüm 6'daki yayın kapısı protokolü
│   ├── build_sqlite.py     # JSON → SQLite dönüşümü + indeksler
│   └── tests.py            # SQLite üzerinde detaylı test paketi
├── raw/                    # ham API yanıtları (debug için, git-ignore)
├── dist/                   # NİHAİ ÇIKTILAR — uygulamaya gömülecekler
│   ├── programs.json       # minify, uygulamanın uzaktan güncelleme dosyası
│   ├── nos.db              # SQLite — uygulamaya bundle edilen asıl veri
│   ├── meta.json           # tarih, sayılar, sha256 (hem json hem db için)
│   └── validation_report.md
└── logs/                   # her koşunun tarihli logu (git-ignore)
```

### Tek komut sözleşmesi
`python OUTBOX/run.py` çalıştırıldığında sırayla ve OTOMATİK olarak:
1. **FETCH** — K1'den tüm evren (Bölüm 2), K2'den 2026 kontenjan/koşullar
   çekilir; ham yanıtlar `raw/`a tarihli yazılır.
2. **MERGE + DEDUP** — Bölüm 3 kuralları uygulanır; dedup log'u tutulur.
3. **VALIDATE** — Bölüm 6 protokolü koşulur. HERHANGİ BİR MADDE FAIL EDERSE
   pipeline burada DURUR, `dist/` GÜNCELLENMEZ, exit code 1 döner ve
   `validation_report.md`'ye fail nedenleri yazılır. Eski `dist/` bozulmaz
   (atomik yazma: önce temp'e üret, tüm testler geçince taşı).
4. **BUILD SQLITE** — `nos.db` üretilir:
   - Tablolar: `programs` (ana), `yearly_stats` (yıl bazlı, FK: program_id),
     `meta` (tek satır: exportedAt, sha256, programCount).
   - İndeksler: `puan_turu`, `il`, `grup`, `uni_tur`, `basari_sirasi(2025)`,
     `kilavuz_kodu UNIQUE`. Sihirbazın ana sorgusu
     (puan_turu + sıralama aralığı + filtreler) 27k kayıtta < 50ms hedefler.
5. **TEST** — SQLite üzerinde detaylı paket (aşağıda). Fail → exit 1,
   dist taşınmaz.
6. **REPORT** — `validation_report.md` + konsol özeti: kayıt sayıları,
   null oranları, dedup istatistiği, test sonuç tablosu, iki dosyanın sha256'sı.

### SQLite test paketi (adım 5'in kapsamı — hepsi zorunlu)
- **Bütünlük:** JSON satır sayısı == programs tablo satır sayısı;
  her programın yearly_stats FK'ları eksiksiz; UNIQUE ihlali yok.
- **Şema/tip:** puan REAL 100-560 aralığı, sıralama INTEGER > 0 veya NULL,
  yıl ∈ {2022,2023,2024,2025}; boş string yok (ya değer ya NULL).
- **Sorgu doğruluğu (motor simülasyonu):** 5 sentetik kullanıcı profili
  (SAY 15k, EA 80k, SÖZ 120k, DİL 30k, TYT 400k) için sihirbaz sorgusu koşulur;
  her profil > 0 sonuç döndürmeli ve dönen her kayıt Bölüm 7 eşiklerine
  matematiksel olarak uymalı (rastgele 50 kayıt yeniden hesaplanıp doğrulanır).
- **Altın referans:** Bölüm 6.3'teki örnekler DB'den sorgulanıp beklenen
  aralıklarla karşılaştırılır.
- **Negatif testler:** kont2026 NULL (kapanan) programlar motor sorgusunda
  dönmüyor mu; dolmayan (sıralama NULL) programlar Güven'de doğru etiketle
  geliyor mu; Türkçe arama normalizasyonu ("BİLGİSAYAR" = "bilgisayar" =
  "bilgisayar mühendisliği") çalışıyor mu.
- **Performans:** ana sihirbaz sorgusu ve 3 tipik filtre kombinasyonu
  ölçülür, süreler rapora yazılır.

### Kullanım kuralları
- `dist/nos.db` uygulamaya asset olarak bundle edilir (ilk açılışta cihaza
  kopyalanır — parse maliyeti sıfır). `dist/programs.json` GitHub Releases'a
  yüklenir; uygulama uzaktan güncellemede JSON'u indirip yerel DB'yi yeniden
  doldurur.
- `raw/` ve `logs/` .gitignore'da; `dist/` commit'lenir (uygulama build'i
  ona bağımlı).
- Pipeline idempotenttir: üst üste iki koşu, kaynak değişmediyse aynı
  sha256'yı üretmelidir (rapor bunu doğrular).

---

## 10. NET SİHİRBAZI VERİSİ (yerleşen son öğrencinin net profili)

### Kaynak
K1 ile aynı resmî API. `yokatlas-py` içindeki `search_netler(NetFilters(...))`
fonksiyonu (sayfalı, `search`'le aynı kullanım). Filtreler: `puan_turu`,
`birim_turu_id`, `yil`, `katsayi`.

### Verinin anlamı (ÇOK ÖNEMLİ — yanlış yorumlanmayacak)
Her kayıt, o programa O YIL en düşük puanla YERLEŞEN öğrencinin profilidir:
`taban_puan`, `obp` ve ders bazında netler — TYT: trk/sos/mat/fen;
AYT: mat/fiz/kim/bio/tde/trh1/cog1/trh2/cog2/fel/din; YDT: ydil.
Bu bir puan HESAPLAMA verisi DEĞİLDİR; kıyas referansıdır.

### Çekme kuralı
- Tüm puan türleri × lisans/önlisans evreni için, mevcut TÜM yıllar çekilir
  (2025 öncelikli; 2024/2023 varsa alınır).
- Birincil anahtar: (`kilavuz_kodu`, `yil`, `katsayi`) üçlüsü — dedup bu
  anahtarla yapılır.
- SQLite'ta ayrı tablo: `net_profiles` (FK: kilavuz_kodu → programs).
  İndeks: (kilavuz_kodu, yil).

### Uygulamada kullanım sözleşmesi
- Özellik adı: "Net Kıyası". Kullanıcı kendi netlerini girer; seçtiği/
  listesindeki her bölüm için "yerleşen son öğrencinin netleri" yan yana
  gösterilir (kullanıcı neti >= referans net ise yeşil, altındaysa turuncu).
- YASAK: bu veriden puan/sıralama HESAPLANMAZ. "Netlerinden puan hesaplama"
  özelliği v1'de YOKTUR; eklenirse ayrı bir "tahminî" modül olarak ve açık
  uyarıyla eklenir (ÖSYM katsayıları yıl sonuna kadar kesinleşmez).
- Ekranda ibare: "Referans: bu programa [yıl] yılında en düşük puanla
  yerleşen öğrencinin netleri (Kaynak: YÖK Atlas)."

### Test eklentileri (Bölüm 9 test paketine dahil)
- net_profiles satırlarının >= %90'ı programs tablosuyla eşleşmeli
  (eşleşmeyen kilavuz kodları loglanır).
- Net değerleri alan aralığı: TYT testleri 0-40, AYT testleri 0-40 (ders
  bazlı soru sayısı sınırları), OBP 100-500, negatif değer yok
  (yanlış cevap kaynaklı küçük negatif netler NULL'a çevrilir, loglanır).
- Altın örnek: Boğaziçi Bilgisayar 2025 net profili YÖK Atlas web
  arayüzünden elle doğrulanır.
