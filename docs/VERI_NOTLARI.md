# NOS Veri Katmanı — Önemli Notlar

> Bu doküman, veri pipeline'ı (OUTBOX) ve uygulama veri katmanı geliştirilirken
> tespit edilen, **koddan bakınca görünmeyen** kritik gerçekleri kaydeder.
> Detaylı plan: `.omc/plans/2026-07-24-nos-veri-sqlite-plan.md` · Yayın raporu:
> `OUTBOX/dist/validation_report.md`

Son güncelleme: 2026-09-13 · Veri: YÖK Atlas (2026 yerleştirme sonuçları + 2022'ye kadar
arşiv), ~21.5k program · Şema: v8 (DDL değişmedi; `yearly_stats.yil` CHECK kümesi 2022..2026)
· Yıl modeli: `pipeline/years.py` (bkz. §1.2, §1.6)

---

## 1. Veri kaynağı gerçekleri

### 1.1 Kapanan programlar verisetinde HİÇ YOK (bilinçli)
`kont2026` kapsaması %100'dür — yani "kapanan program" (kont2026 NULL) kaydı
**sıfırdır**. Bunun nedeni bir hata değil, kaynağın doğası: YÖK Atlas yeni API'si
yalnız **2026 kılavuzunda yer alan** programları döndürür; kapanan programlar
listeye hiç girmez. Planın "kapananları gizle" kuralı yapı gereği kendiliğinden
sağlanır. **Dikkat:** uzaktan güncelleme verisi de aynı kaynaktan üretildiği
sürece bu değişmez; farklı bir kaynak eklenirse `kont2026 IS NULL` filtresi
motorda zaten mevcuttur.

### 1.2 Yıl modeli: İKİ ÇAPA + arşiv (2026-09-13 geçişi; tek kaynak `pipeline/years.py`)
YÖK Atlas kaydı 4 yıl taşır: `current` (suffix'siz) + `suffix1/2/3`. Ama alan
grupları FARKLI yıllara çapalıdır (2026-09-13'te Temmuz ve Eylül ham verisi 300
DİL programında karşılaştırılarak KANITLANDI — `gk1/gk2/gk3` iki anlık görüntüde
birebir aynı, `minPuan/basariSirasi` tam bir suffix kaydı):

| Alan grubu | Çapa | 2026-09 eşlemesi |
|---|---|---|
| `minPuan{N}`, `basariSirasi{N}` (SONUÇ: puan/sıra) | `RESULT_YEAR - N` (en son yerleştirme) | current→2026, 1→2025, 2→2024, 3→2023 |
| `kontenjan`,`gkY` (N=0), `gk{N}`,`gkY{N}` (KONTENJAN/YERLEŞEN) | `CATALOG_YEAR - N` (kılavuz yılı) | kontenjan/gkY→2026, gk1→2025, gk2→2024, gk3→2023 |

Bugün `RESULT_YEAR == CATALOG_YEAR == 2026` olduğu için iki çapa çakışır; Temmuz'da
(kılavuz çıkmış, yerleştirme yapılmamış) bir yıl ayrıktı ve **Temmuz build'i
kontenjan/yerleşeni bir yıl eski etiketlemişti** ("2024" satırındaki k/z aslında
2025'indi; `gkY1` = 2025 yerleşen). `merge._extract_years` artık iki çapayı ayrı
ayrı uygular, Temmuz arşivi `--kz-year-shift 1` ile düzeltilerek üretildi (§1.6).

**2026-09 API şema değişikliği:** `gkY` (current yerleşen), `sgyY`, `obkY`, `y34`
eklendi; `gkY1`, `obk1`, `sgy1`, `y34_1`, `dprm1` (tarihsel yerleşen/alt kırılımlar)
kaldırıldı. Dolayısıyla 2025 yerleşen yalnız ARŞİVDEN gelir (Temmuz gkY1); 2024/2023
yerleşen hiçbir kaynakta yok (NULL). 2022 yalnız p/s taşır (k/z yok).

Yerleşme verisi olan yıllar: **2022–2026** (`ALL_YEARS`). `son_yil/son_siralama`
en güncel sırası dolu yıl (çoğunlukla 2026); trend `TREND_YEARS` = 2024–2026;
`kont2026` = 2026 kılavuz kontenjanı = 2026 satırının `kontenjan`ı (aynı değer).

2026-09-13 build'i (`yearly_stats`, 21.493 program; sıra/puan/kontenjan/yerleşen dolu satır):

| yıl | satır | sıra | kontenjan | yerleşen | kaynak |
|---|---|---|---|---|---|
| 2026 | 21.493 | 18.251 | 21.493 | 20.737 | API current (`kontenjan`,`gkY`) |
| 2025 | 20.254 | 17.325 | 20.242 | 19.649 | API suffix1 (p/s, `gk1`); yerleşen ARŞİV (Temmuz `gkY1`) |
| 2024 | 18.688 | 16.895 | 18.493 | 0 | API suffix2 + `gk2` |
| 2023 | 17.513 | 16.443 | 17.005 | 0 | API suffix3 + `gk3` |
| 2022 | 15.801 | 15.801 | 0 | 0 | yalnız ARŞİV (Temmuz suffix3 p/s) |

`son_yil` dağılımı: 2026 %84.9, 2025 374, 2024 848, 2023 518, 2022 174, NULL 1.328 (%6.2 —
Temmuz'da %10.6'ydı). Arşiv↔API çakışması **0**. 2026'da elit SAY sıraları piyasa
genelinde ~2x geriledi (İTÜ Bilg. 1435→2503, ODTÜ 1204→2989, Boğaziçi 1448→4560; aynı
puanın sırası iki kat) — gerçek dağılım kayması; altın referans eşiği 3000→10000 alındı
(`validate._GOLD_BOGAZICI_CS_MAX`, gerekçe kodda).

> **Tarihçe (Task #14, 2026-07-25):** İlk fazda `current` atlanıp suffix1/2/3
> 2025/2024/2023 sanılmıştı; net_profiles.taban_puan == yearly_stats.puan
> çapraz kontrolüyle current→2025 olduğu görüldü (%99.8). Bu kontrol yalnız
> p/s çapasını doğruluyordu; k/z çapası 2026-09-13'te ayrıca kanıtlandı.

### 1.3 ÖSYM kılavuz PDF — ARTIK OTORİTER kaynak (2026-07-25 kararı DEĞİŞTİ)
Önceki not (2026-07 öncesi): 2026 kontenjanı, koşul kodları, koşul açıklamaları
ve başarı sırası barajları YÖK Atlas'tan (K1) inline geliyordu; ÖSYM dosyası
yalnız opsiyonel çapraz-kontrol sayılıyordu (`raw/osym/` boştu, atlanıyordu).

**Bu karar tersine çevrildi.** Kullanıcı resmî `docs/kontkilavuz_yktd21072026.pdf`
(2026-YKS Yükseköğretim Programları ve Kontenjanları Kılavuzu, 793 sayfa)
dosyasını en güncel/güvenilir kaynak olarak sağladı. Pipeline'a
`OUTBOX/pipeline/parse_kilavuz.py` ile gerçek bir parser eklendi (`fetch.py`'nin
`_parse_osym_pdf` taslağı yerine) ve **kılavuz artık OTORİTER**:
`merge.py::_apply_guide()` kont2026/kosul/sure/puanTuru/akreditasyon/
sonSiralama/sonPuan/sonYil alanlarını kılavuz değeriyle ÜZERİNE YAZAR (K1'den
farklıysa `discrepancy_report.md`'ye kaydeder), `kosul_sozluk`'u kılavuzun resmî
metniyle yeniler, ve YENİ alanlar ekler: `ucret`/`ucret_aciklama` (vakıf/KKTC
öğrenim ücreti), `kont_sehit_gazi`, `kont_okul_birincisi`, `tyc`, `uni_web`
(schema v3, bkz. §6.6).

**Tablo 1B de otoriter (2026-07-25, aynı gün eklendi):** `baraj` tablosu (K-2
sert eleme kapısı) önceden YALNIZ K1'in per-program `minBasariSirasi` alanından
türetiliyordu — kılavuzun kendi "Tablo 1B: Hukuk/Mimarlık/Mühendislik/Tıp/
Öğretmenlik/Eczacılık/Diş Hekimliği İçin En Düşük Başarı Sırası" tablosuyla HİÇ
çapraz kontrol edilmiyordu. Kontrol edilince: **Hukuk (EA) DB'de 125.000
gösteriyordu, kılavuz açıkça 100.000 diyor** — 6 diğer kategori (Mühendislik
300k, Mimarlık 250k, Tıp 50k, Öğretmenlik 300k, Eczacılık 100k, Diş Hekimliği
80k) zaten uyumluydu. `parse_kilavuz.py::_parse_tablo1b()` + `merge.py::
_apply_tablo1b()` eklendi: Hukuk/Mimarlık/Tıp/Eczacılık/Diş Hekimliği (tek bir
grup_pattern'e karşılık gelen, belirsizlik olmayan 5 kategori) OTORİTER
üzerine yazılır; Mühendislik/Öğretmenlik (kılavuzda adı geçen istisnaları olan
GENİŞ kategoriler — ör. Orman/Ziraat/Su Ürünleri mühendislikleri hariç) yalnız
DOĞRULANIR (üzerine yazılmaz — istisna listesinin eksik olması yanlışlıkla
doğru bir K1 istisna değerini ezebilir). Sonuç: Hukuk/EA barajı 125.000→100.000
düzeltildi; bu artık 100.001-125.000 arası sırada olan kullanıcılara sihirbazın
Hukuk'u YANLIŞLIKLA UYGUN göstermesini engelliyor. **Dikkat:** "N bininci" =
N×1000 (ör. "100 bininci" = 100.000) — ilk sürümde bu çarpım unutulmuştu,
üzerine-yazma değerleri 100/250/50 gibi yanlış küçük sayılar üretiyordu; ikinci
tam koşuda yakalanıp düzeltildi.

**KAYNAK OTORİTESİ AYRIMI — sıralama bozulması olayı (2026-07-25, KRİTİK):**
İlk kılavuz-otoriter sürüm 2025 başarı sırası/puanını da kılavuzdan ÜZERİNE
yazıyordu. Kılavuz PDF'inin çapraz filigranı ("2026-YKS...") sayı bloklarını
İKİYE BÖLEBİLİYOR veya sayıya HARF YAPIŞTIRABİLİYOR: Erciyes Makine Müh'ün
gerçek sırası 154725, pdfplumber'da "1"+"54725" iki kelime çıktı; parser ilk
parçayı alıp son_siralama=1 yazdı → **sihirbazda 1. sıraya Kayseri Makine
Mühendisliği geldi, 90 kayıt bozuldu** (kullanıcı yakaladı). İki katmanlı
düzeltme: (a) `parse_kilavuz._digits_of()` bant token'larını birleştirir +
harfleri ayıklar; sarma satırları dolu alanı EZEMEZ (ilk-değer-kazanır);
(b) `merge.py` KAYNAK OTORİTESİ AYRIMI: **2026 kılavuz verisi** (kontenjan,
koşul, süre, puan türü, akreditasyon, ücret, baraj) → kılavuz otoriter,
üzerine yazar; **2025 yerleşme sonuçları** (başarı sırası, en küçük puan) →
YÖK Atlas'ın yayınladığı TARİHSEL OLGU, kılavuz aynı sonucu yeniden basar;
fark = parse hatası ⇒ ÇAKIŞMADA K1 KAZANIR, kılavuz yalnız K1 NULL ise
doldurur (rapora "K1 korundu" yazılır). Kalıcı sert kapılar: `validate.py`
+ `tests.py` — (1) son_siralama == yearly_stats(2025).sira birebir;
(2) elit tutarlılık: sıra ≤ 2000 ⇒ puan ≥ 400 (SÖZ tabanı 429'un altında,
gerçek dağılımdan kalibre). Bu veri düzeltmesi için schemaVersion 3→4
yükseltildi (şema değişmedi; cihazlardaki bozuk kopyanın zorunlu yeniden
kopyalanması için — §6.4 mekanizması).

**Evren tamamlama taraması (2026-07-25):** Canlı API'nin filtresiz toplamı
**21.482**; PT-filtreli 5 kombo yalnız 21.480 döndürüyor. Eksik 2 kayıt:
Kırgızistan-Türkiye Manas Üni. 2 Filoloji programı — API `puanTuru: null`
döndürüyor (kılavuzda DİL basılı), bu yüzden PT-filtreli hiçbir sorguya
girmiyorlar. `fetch.SEARCH_COMBOS`'a 2 TAMAMLAMA taraması eklendi
(pt=None × birim 46/47 → `raw/k1/ALL46|ALL47/`); dedup'ta PT-tagli kayıtlar
önce geldiğinden yalnız yeni kodlar eklenir; puan türlerini kılavuz doldurur
(_apply_guide), kılavuz da dolduramazsa kayıt güvenle atılır (yearly_stats
NOT NULL koruması). fetch_netler pt=None kombolarını atlar.

**Doğrulanmış kapsama** (2026-07-25 tam koşusu, bkz. `dist/discrepancy_report.md`):
program kod örtüşmesi ~%99.4, skaler alan bazında üzerine-yazma oranı her
alanda ~%1-2.6 (K1 ile kılavuz büyük ölçüde zaten uyumlu — beklenen, ikisi de
nihayetinde aynı ÖSYM/YÖK verisine dayanıyor). `kosul` (çok-değerli/liste alan)
~%15 oranında farklı — ayrı ve daha yüksek eşiği var (bkz. `validate.py`
`_GUIDE_DISCREPANCY_MAX_BY_FIELD`): küme karşılaştırması tek kod farkında bile
"sapma" sayar, ve örnekler incelendiğinde her iki taraf da GEÇERLİ kod içeriyor
(gerçek editöryal fark, sütun kayması değil). Kılavuzda olup DB'de olmayan
~1.248 kod ≈ tamamı **Tablo 5 özel yetenek** programları (puan türü/merkezi
sıra yok, sihirbaz modeli dışı) — BİLİNÇLİ OLARAK EKLENMEDİ.

**Kritik parser bulgusu (düzeltildi):** Tablo 3/4'ün başlık+sütun-etiket+numara
bloğu (ör. "ÖĞR. SÜRE PUAN TÜRÜ ... (12) (13)") yalnız İLK sayfada değil **HER
sayfada tekrarlıyor** (top≈15-52pt). İlk sürümde bu, önceki sayfanın SON
kaydına "devam satırı" sanılıp TYÇ/akreditasyon gibi kuyruk alanlarını marker
metniyle ("(12)","(17)") kirletiyordu — 793 sayfa × 1 kayıt = binlerce satırda.
`_rows_for_page(..., top_margin=56.0)` ile düzeltildi (gerçek içerik her
sayfada top=59'da başlıyor, doğrulandı). Bu yüzden `tyc` sütunu bu koşuda
**tamamen boş** çıktı (gerçek TYÇ değerleri kılavuzda seyrek/başka bir
konumda olabilir) — yapısal bir hata değil, sadece veri yok; nullable, UI/sorgu
etkilenmez.

**Bilinen sınırlamalar (v1 parser):**
- Kılavuzun bazı sayfalarında arka plan/filigran sızıntısı metne tek karakter
  serpiştiriyor (ör. "meslek Aokulu" — "A" fazladan, veya akreditasyon kodu
  "D50.449993"). İzole tek-karakterli token'lar filtrelenir ama kelime İÇİNE
  yapışan tek karakterler v1'de temizlenmiyor — yalnız görüntülenen METİN
  kalitesini etkiler, sayısal/yapısal alanlar ayrıca aralık doğrulamasından
  geçer (bkz. `parse_kilavuz._apply_fields`).
- Vakıf/KKTC öğrenim ücreti eşleşmesi ~%67 (üniversite adı 2 satıra sarınca
  bazı devam satırları kayboluyor) — NULL-güvenli (belirsiz/eşleşmeyen ücret
  YAZILMAZ), bkz. `discrepancy_report.md`.
- Tablo 4'ün MEB kontenjanı, öğretim üyesi (P.DR/D.DR/DR.ÖĞR.ÜYE/GRV) ve sınav
  ortalaması (TUS/DUS/AB AYP/KPSS) sütunları BİLİNÇLİ ATLANDI: GRV
  (Görevlendirme) "*" işaretli bir bayrak sütunu, DB'nin `ar_gor` (araştırma
  görevlisi, yokatlas kaynaklı) alanıyla semantik olarak FARKLI — yanlış
  eşleme riski onaylı kapsam dışında bırakıldı.
- Kılavuzun "1. Kısım" ve "2. Kısım" koşul sözlükleri AYRI numaralandırma
  havuzlarıdır (ikisi de "Bk. 1" ile başlıyor, farklı içerikle!). Çakışmada
  1. Kısım kazanır (DB'nin mevcut doğrulanmış kod '1' metniyle eşleşiyor).

**XLS çapraz kontrolü (2026-09-13):** ÖSYM aynı Tablo 3/4'ü XLS olarak da yayınlar
(`docs/tablo-3-*.xls` önlisans, `tablo-4-*.xls` lisans; 21.493 program, filigran yok).
`pipeline/parse_kilavuz_xls.py` bunları aynı `GuideProgram` yapısına çevirir;
`merge.cross_check_guide_xls` PDF parse'ıyla alan bazında karşılaştırır
(`discrepancy_report.md` "PDF ↔ XLS" bölümü; `validate` sayısal alanlarda >%2 farkta
yumuşak uyarı). **Karar: XLS yalnız çapraz kontrol, PDF otoriter** (kullanıcı,
2026-09-13). Bulgu: `sira/puan` (önceki yıl) %0 fark; `kosul` ~%15 fark ve
`kontenjanY34`/`kontOkulBirincisi`/`akreditasyon` tekil farklar — örnekler PDF
tarafında sarma satırının komşu programa yapışması ve filigran rakam/harf
yapışması ("1479129" vs 1, "FEDEDK" vs FEDEK). Yani §1.3'teki "kosul ~%15 gerçek
editöryal fark" yorumu büyük olasılıkla PDF parse hatasıydı. Tek bayrakla XLS
otoriter yapılabilir: `run.py --kilavuz-tablo-kaynak xls` (PDF yine sözlük/Tablo
1B/ücret/web sağlar; rapor PDF↔XLS karşılaştırmasını korur).

### 1.4 yokatlas-py tip modeli KKTC'de kırılıyor
Kütüphanenin `Program` pydantic modeli `universite_turu`'nda KKTC/YURTDISI
kabul etmiyor (ValidationError). Pipeline bu yüzden **ham JSON dict** işler;
kütüphaneden yalnız HTTP taşıma + `RateLimitError` kullanılır. Kütüphane
güncellemesinde bu kısıt yeniden değerlendirilebilir.

### 1.5 K3/K4 çapraz kaynak doğrulaması SKIPPED
basarisiralamalari.com ve kariyer.net programatik erişime kapalı. Otomatik
kapıların tamamı + altın referans seti geçti; yine de tercih dönemi öncesi
**20 programın elle karşılaştırılması** önerilir (brief §6.4).

### 1.6 Yıl geçişi prosedürü (her yıl Ağustos/Eylül, yerleştirme sonuçları YÖK Atlas'a düşünce)
1. Canlı API'de bir programın `minPuan`/`minPuan1` değerlerini önceki raw ile
   karşılaştır: current yeni yılı taşıyorsa geçiş zamanı (`raw/k1/{eski yıl}/`
   dokunulmaz; fetch yeni yıl dizinine yazar).
2. **Önce arşivi üret** (dist/ hâlâ eski, doğrulanmış build):
   `uv run python scripts/make_history_archive.py` → `archive/yearly_stats_*.json.gz`.
   `--kz-year-shift` yalnız kaynak DB'nin k/z etiketleri kaymışsa (Temmuz 2026
   build'i gibi) gerekir; iki çapalı `_extract_years` sonrası üretilen build'lerde 0.
   Eski arşiv dosyasını silme; `run.py --history-archive` ile yol seçilir
   (varsayılan `DEFAULT_HISTORY_ARCHIVE`, run.py). Birden çok arşiv birleştirmek
   gerekirse yeni build'den tek arşiv üretip eski dosyayı kaldır.
3. `pipeline/years.py` → `RESULT_YEAR` (ve yeni kılavuz geldiyse `CATALOG_YEAR`) +1.
   `ARCHIVE_MIN_YEAR` sabit kalır (2022). Başka yerde yıl literal'i olmamalı.
4. Yeni kılavuz: `run.py DEFAULT_KILAVUZ_PDF` + XLS glob'ları; `parse_kilavuz`
   sütun x-konumları (`_T3_MARKERS/_T4_MARKERS`) yeniden ölçülür; `kont2026`
   kolon adı tüketici sözleşmesidir (yeniden adlandırma = SCHEMA_VERSION artışı,
   iki tüketici repoda koordinasyon).
5. `uv run python run.py` → `validation_report.md` PASS; `discrepancy_report.md`
   "Arşiv ↔ API" çakışması ~0 olmalı (değilse çapa/etiket hatası — DÜŞÜRME, araştır).
6. Tüketici repolar: nos-academy `schema.ts` CHECK kümesi + `Yil` tipi +
   `engine.ts` bayat-yıl eşiği; nostercih yıl metinleri; iki `nos-data.json` pin'i.

## 2. Veri içeriği tuzakları

| Gerçek | Sayı | Anlamı |
|---|---|---|
| `yerlesen > kontenjan` satırları | 7.265 yıl-satırı | Hata DEĞİL — İÖ/ek kontenjan istisnası; loglanır, veri aynen korunur. |
| NULL `son_siralama` | ~%10 | "Son yıllarda hiç dolmadı" → motor bunları **Güven** bandına koyar, sıfır sanmaz. (2026-09 build'inde `son_yil` 2026 olmayanlar bir önceki dolu yıla düşer; uygulama `son_yil < RESULT_YEAR`'ı "eski veri" rozetiyle gösterir.) |
| Karma puan türü şüphesi (K-1) | 25 kayıt | Yıllar arası >5x sıra sıçraması; **trend hesabı dışı** bırakıldı. |
| AÖF/Uzaktan programlar | 219 (113 Açıköğretim + 106 Uzaktan) | Varsayılan olarak sonuç dışı; kullanıcı filtreyle açar (K-7). **Not:** kaynak K1 `Açıköğretim` değerini hiç göndermez; AÖF programları `ogrenimTuruAdi='UOLP'` (id 188) kovasında gelir (113 kaydın 112'si birim adında "(Açıköğretim)", 1'i gerçek UOLP: Manas Tıp). YÖK Atlas açıköğretim filtresi bu kovayı birlikte filtrelediği için merge.py UOLP→`Açıköğretim`e normalize eder (önceki UOLP→Örgün eşlemesi AÖF'leri örgün sonuçlara karıştırıyordu — 2026-07-26'da düzeltildi). |
| MTOK satırları | işaretli | Yalnız uygun lise türü profiline gösterilir (K-8). |
| KKTC-uyruklu kontenjan satırları | işaretli | TC kullanıcıya hiçbir sonuçta görünmez. |
| Yeni programlar (`yillar` boş) | var | Bantlara girmez; ayrı "Yeni Programlar" listesi + rozet (K-4). |

## 3. Teknik sözleşmeler (bozarsan veri katmanı sessizce yanlış çalışır)

### 3.1 Türkçe fold sözleşmesi — iki tarafta birebir aynı
`ı→i, İ→i, ş→s, ç→c, ö→o, ü→u, ğ→g` sonra ASCII lowercase.
Python: `OUTBOX/pipeline/turkish.py` · TS: `src/lib/turkish.ts`.
Ortak test vektörü: `OUTBOX/dist/fold_fixture.json` (40 vaka) — iki taraf da bu
fixture'a karşı assert edilir. `toLocaleLowerCase('tr')` KULLANMA; fold önce
tablo ile yapılır. SQLite `lower()`/NOCASE Türkçe bilmez — tüm arama
`*_norm` kolonları üzerinden.

### 3.2 FTS5: MATCH/bm25 tablo alias'ı ile ÇALIŞMAZ
`SELECT ... FROM program_fts f WHERE f MATCH ?` → "no such column" hatası.
FTS sorgularında tablo adını (`program_fts`) alias'sız kullan.

### 3.3 sha256_db ≠ sha256_json
`meta.json` iki hash içerir: `sha256_json` **içerik hash'idir** (idempotans
çapası — aynı kaynak veri → aynı değer); `sha256_db` SQLite dosya baytlarıdır ve
**her build'de değişir**. `sync-db` doğrulaması sha256_db'yi her koşuda güncel
`OUTBOX/dist/meta.json`'dan okumalıdır. Uzaktan güncelleme kararı
`sha256_json` karşılaştırmasıyla verilir.

### 3.4 Bundle edilen DB DELETE-journal olmalı, WAL cihazda açılır
`nos.db` asset olarak tek dosya gitmek zorunda (WAL'in -wal/-shm yan dosyaları
bundle'a giremez). Pipeline DELETE journal ile üretir; uygulama açılışta kendi
kopyası üzerinde `PRAGMA journal_mode = WAL` çalıştırır (`src/lib/db.tsx`).

**`OUTBOX/dist/nos.db`'yi ASLA yazılabilir modda açma** (WAL'e geçirme). Bir
kez WAL'de açılırsa header değişir → dosya hash'i `meta.sha256_db` ile uyuşmaz
ve `sync-db` haklı olarak reddeder (bu senaryo yaşandı: bir doğrulama süreci
dist DB'sini WAL'de açtı, sidecar'lar kaldı). İnceleme için:
`sqlite3 "file:OUTBOX/dist/nos.db?mode=ro"` kullan. Pipeline, promote öncesi
sidecar yokluğunu assert eder ve `sha256_db`'yi son adım olarak hesaplar;
dist çıktıları yazma-korumalıdır.

### 3.5 Bant eşikleri DB'dedir, hardcode edilemez (K-10)
`config` tablosu: `guven_carpan=0.85, denge_ust=1.10, hedef_ust=1.35` +
trend parametreleri. Motor (`src/lib/engine.ts`) eşikleri enjekte alır, eksikse
throw eder. Eşik değişikliği = pipeline'da config güncelle + yeni DB yayınla.

### 3.6 Baraj sert dışlaması bant matematiğinden ÖNCE (K-2)
Kullanıcının sırası ilgili program sınıfının resmi başarı sırası barajını
(Tıp/Hukuk/Müh/Mimarlık/Öğretmenlik/Diş/Ecz.) geçmiyorsa, program dolmamış veya
"ulaşılabilir" görünse bile SONUÇTA YER ALMAZ.

## 4. Operasyon

- **Tek komut:** `python OUTBOX/run.py` (uv ortamı) — fetch → merge → validate →
  build → test → report. Herhangi bir kapı FAIL → exit 1, `dist/` değişmez
  (atomik promote). Tam koşu ~76s, ~217 sayfa, sayfalar arası 300ms.
- **Rate limit:** kütüphane retry YAPMAZ; pipeline 418/429'da exponential
  backoff uygular (1→16s, 5 deneme).
- **Senkron:** `pnpm sync-db` → `OUTBOX/dist/nos.db`'yi `assets/db/nos.db`'ye
  kopyalar + sha256 doğrular. İnsan onayı olmadan (validation_report PASS +
  gözden geçirme) sync-db çalıştırılmaz.
- **Güncelleme döngüsü:** tercih döneminde günde 1 koşu; GitHub Release asset'i
  olarak **nos.db + meta.json** yüklenir (S-4: uygulama JSON'dan rebuild YAPMAZ,
  hazır DB indirir — programs.json config/alias içermediği için ondan çalışır DB
  kurulamaz; JSON yalnız arşiv/analiz amaçlı yayınlanabilir). Tespit
  `sha256_json`, dosya doğrulaması `sha256_db`. Repo henüz placeholder:
  `src/lib/schema.ts` içindeki RELEASE_* sabitleri gerçek repo ile
  değiştirilecek.

## 5. Cihazda doğrulanması gerekenler (Faz 9 — emülatör/cihaz ister)

1. İlk açılışta asset→cihaz DB kopyalama süresi (13MB) ve splash davranışı.
2. Ana sihirbaz sorgusu < 50ms, FTS < 30ms hedefleri (masaüstünde 5ms/0.1ms —
   rahat pay var, yine de ölçülmeli).
3. `SQLite.defaultDatabaseDirectory` gerçek yolu + `File.move`'un SQLite
   dizininde çalıştığı (uzaktan güncelleme takası).
4. OTA (expo-updates) sonrası cihaz DB'sinin kalıcılığı — dokümanlarda garanti
   yok; kayıp durumunda assetSource bundled kopyayı geri yükler.
5. Canlı GitHub Releases üzerinden uçtan uca güncelleme (bozuk sha256 → red).

## 6.5 Net verisi eşleşme oranı — yıl bazında değerlendirilir

`net_profiles` yayın kapısı, genel eşleşme oranını DEĞİL, yalnız **en güncel
yılın (2025)** eşleşme oranını hard-gate olarak kullanır (≥%90, gerçek %92.57).
Genel oran (%85.14) ve yıl bazında oranlar (2025 %92.57 / 2024 %85.71 / 2023
%77.33) yalnız görünürlük için loglanır — bunlar bug DEĞİL: geçmiş yıllara ait
`kilavuz_kodu` değerlerinin bir kısmı (özellikle vakıf/burs dilimi programları)
güncel 2026 kılavuzunda artık yok, bu YÖK Atlas'ın beklenen yıllık kod-kayması.
Eşleşmeyen tarihsel satırlar zaten sorgulanamaz (uygulama yalnız güncel
programların `kilavuz_kodu`'suyla `net_profiles` sorgular) — kullanıcıya hiçbir
olumsuz etkisi yok, tüm tarihsel veri yine de saklanır.

**`ydt_ydil_net` aralığı 0-80'dir, 0-40 DEĞİL** (YDT — Yabancı Dil Testi — 80
sorudur; TYT/AYT testleri 40 sorudur). Bu alana yanlışlıkla 0-40 aralık kontrolü
uygulanırsa DİL parkurunun en kritik alanı (75-80 gibi geçerli değerler) sessizce
NULL'lanır — bu gerçek bir hata olarak yaşandı ve düzeltildi.

## 6. Net Sihirbazı verisi + schema v2 (2026-07-24 genişletmesi)

### 6.1 DÜZELTİLDİ: yearly_stats yıl etiketleri 1 yıl kaymıştı (Task #14)
Kullanıcının "geçmiş yılları göremiyorum" şüphesi kısmen HAKLIYMIŞ — ama neden
sanılan değildi. yearly_stats satır SAYILARI eksiksizdi; sorun ETİKETLEMEDEYDİ:
`current` (gerçek 2025 sonucu) tamamen atlanıp suffix1/2/3 yanlışlıkla
2025/2024/2023 etiketlenmişti → tüm yearly_stats bir yıl BAYAT görünüyordu
(gösterilen "2025" aslında 2024'tü). Lider ham veri çapraz-kontrolüyle buldu
(net_profiles.taban_puan == yearly_stats.puan ama yıl 1 kaymış). Düzeltme:
current→2025, suffix1→2024, suffix2→2023, suffix3→2022 (2022 geri geldi). Fix
sonrası `son_yil` çoğu programda gerçek 2025 (dağılım: 2025 ağırlıklı, kalanlar
2024/2023/2022) ve net_profiles.yil ↔ yearly_stats.yil **%99.8** aynı takvimde
(aynı program-yıl-katsayı için taban==puan). UI hâlâ geçmiş yılları göstermiyor
(ileride sihirbaz/detay ekranı işi) ama artık DOĞRU etiketli veriye bakacak.

> **Uyumluluk notu (data-layer):** `engine.ts`/`queries.ts` bu değişimden
> etkilenmedi — kontenjan/yerlesen'in TEK tüketicisi `computeRozetler`'daki
> "tam_dolmadi" rozeti zaten `!= null` guard'lı; bant matematiği null-güvenli
> `son_siralama` kullanıyor; trend denormalize `program.trend`'den OKUNUYOR
> (motor 4 yılı ayrıca hesaplamıyor). Beklenen davranış kaymaları: "tam_dolmadi"
> rozeti daha AZ (son_yil=2025 satırında kontenjan/yerlesen NULL), "en güncel veri"
> rozeti daha ÇOK tetiklenir; G/D/H dağılımı gerçek 2025 sıralarına hizalanınca
> Hedef bandına doğru kayar (regresyon testinde doğrulandı, patoloji yok).

### 6.2 `net_profiles` sözleşmesi (schema v2 yeni tablo)
- **Kaynak:** `search_netler` uç noktası (`/api/netler/search`) — program tablosu
  ile aynı sayfalama sözleşmesi. `universite_id`/`birim_grup_id` filtreleri boş
  bırakılınca sunucu TÜM evreni döner (program-bazlı ~21.480 ayrı çağrı YOK).
- **Kırılım / dedup anahtarı:** `(kilavuz_kodu, yil, katsayi)`. `katsayi`
  **filtrelenmeden bırakılır**; yoksa aynı program-yıl için OBP katsayı
  varyantları (ör. 0.12 standart vs 0.0 ek yerleştirme) sessizce kaybolur. Bu
  yüzden PK üç parçalıdır ve bir program-yıl birden çok satır taşıyabilir.
- **Değer temizliği:** negatif net değerleri **NULL**'a çevrilir (brief §10);
  aralık dışı değerler loglanır. Net alanları sparse — SAY programında yalnız
  TYT + AYT-fen alanları dolar, sözel/dil AYT alanları NULL kalır.
- **FK:** `kilavuz_kodu → programs(id)`; `programs`'ta karşılığı olmayan kodlar
  insert öncesi filtrelenir (≥%90 eşleşme kuralı, `PRAGMA foreign_keys=ON`).
- **Uygulama erişimi:** `getNetProfiles(db, kilavuzKodu)` (`src/lib/queries.ts`)
  — `WHERE kilavuz_kodu=? ORDER BY yil DESC`. Tip: `NetProfile`
  (`src/types/program.ts`). UI bileşeni bu fazın kapsamında değil.

### 6.3 Ek Program alanları (schema v2, hepsi nullable/sparse)
yokatlas-py'den çekilip önceden atılan alanlar `programs`'a eklendi:
`prof/doc/dou/ar_gor` (akademik kadro), `kpss1` (istihdam %), `kontenjan_obs`/
`kontenjan_y34` (kontenjan alt-kırılımı), `osym_kilavuz_id` (kararlı birleştirme
anahtarı), `akreditasyon`/`akreditasyon_ack`/`uni_akreditasyon`. Gerçek veride
**%17-55 doluluk** (sparse). `kpss2`/`ogr_gor` eklenmedi (API'de ~%0). Mevcut
kayıtlar bozulmaz; tüm kolonlar nullable, CHECK'ler değişmedi.

### 6.4 `CURRENT_SCHEMA_VERSION` 1→2 ve gizli meta bug
`src/lib/schema.ts` `CURRENT_SCHEMA_VERSION` 1→2 oldu. Bu bump, cihazdaki eski v1
DB'nin (net_profiles tablosu olmadan) yeniden kopyalanmasını (`db.tsx`
`forceOverwrite` akışı) tetikler — aksi halde `getNetProfiles` "no such table"
ile patlar. Bump aynı zamanda gizli bir bug'ı kapatır: pipeline'ın `meta.json`'ı
`schemaVersion` alanını **hiç yazmıyordu**, bu da `update.ts`'in OTA sürüm
karşılaştırmasını sessizce bozuyordu; artık yazılıyor. **Senkron sözleşme:**
`src/lib/schema.ts`, `scripts/make-fixture-db.mjs` ve pipeline'ın
`build_sqlite.py`'sindeki DDL **birebir aynı** (anlamsal — yorum/boşluk fark
edebilir, kolon adı/tip/sıra AYNI) olmak zorunda.

### 6.6 Schema v3 — ÖSYM 2026 kılavuzu (K2, otoriter) ek alanları
`CURRENT_SCHEMA_VERSION` 2→3. `programs`'a 6 ek nullable kolon: `ucret` (REAL,
vakıf/KKTC yıllık öğrenim ücreti TL, DEVLET NULL), `ucret_aciklama` (TEXT),
`kont_sehit_gazi` (INTEGER), `kont_okul_birincisi` (INTEGER), `tyc` (TEXT,
Türkiye Yeterlilikler Çerçevesi düzeyi), `uni_web` (TEXT, denormalize üniversite
web adresi). **34-yaş kadın kontenjanı için YENİ kolon AÇILMADI** — mevcut
`kontenjan_y34` yeniden kullanıldı (aynı kavram, kılavuzdan artık otoriter
doldurulur). Kaynak: `OUTBOX/pipeline/parse_kilavuz.py` (bkz. §1.3). INSERT
kolon sayısı 36→42 (`build_sqlite.py` + `make-fixture-db.mjs` ikisinde de).
Sapma raporu `dist/discrepancy_report.md` — **AYRI dosyadır**, `sync-db`'nin
`validation_report.md` PASS kapısını etkilemez.
