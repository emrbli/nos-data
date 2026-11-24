# KPSS çıkmış soru dizini (pipeline/cikmis/kpss)

YKS hattının (`pipeline/cikmis`) birebir aynı biçimi. Bu tur YAYINLANMADI; çıktılar `dist/` altında hazır.

## Kapsam ve gerçek
- Kapsam (2026-11-24, patron kararı): 2018-2026, nosakademi-web `cikmis-sorular-arsivi.ts` kayıtlarından Lisans GY-GK, Eğitim Bilimleri, Ön Lisans, Ortaöğretim, Alan Bilgisi (A grubu, 9 test: huk, ikt, isl, ist, kamu, mal, muh, ui, ceei) ve DHBT. ÖABT (18 branş, 2018-2024) 2026-11-24'te eklendi (aşağıda). Alan/GY-GK/EB/DHBT 41 belge, 3251 soru; ÖABT 7 belge, 5279 soru; toplam 48 belge, 8530 soru (içeriksiz iptal olan 4 soru yayımlanmaz: 2019 Alan Muhasebe 30, 2020 ÖABT Beden Eğitimi 55, Din Kültürü 74, Okul Öncesi 52). Belge kimlikleri sitedeki kayıt kimlikleriyle aynıdır.
- 2018-2021 TAM kitapçık (`kapsam: tam`: GY ve GK 60'ar, EB 80, Alan 40'ar, DHBT 20'şer soru; cevap sondaki anahtar tablosundan). 2022 sonrası ÖSYM yalnız %10 yayımlar (`yuzde10`: GY/GK 6'şar, EB 8, Alan 4'er, DHBT her testte 2; özgün numarayla, cevap sayfada "DOĞRU CEVAP: X"). Ön Lisans/Ortaöğretim yalnız 2018, 2020, 2022, 2024, 2026'da, DHBT 2018, 2020, 2022, 2024'te, EB 2025'ten beri yok.
- Aile × yıl soru sayıları (yayımlanan):

| Aile | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 | Toplam |
|---|---|---|---|---|---|---|---|---|---|---|
| Lisans GY-GK | 120 | 120 | 120 | 120 | 24 | 12 | 12 | 12 | 12 | 552 |
| Eğitim Bilimleri | 80 | 80 | 80 | 80 | 16 | 8 | 8 | - | - | 352 |
| Ön Lisans GY-GK | 120 | - | 120 | - | 12 | - | 12 | - | 12 | 276 |
| Ortaöğretim GY-GK | 120 | - | 120 | - | 12 | - | 12 | - | 12 | 276 |
| Alan Bilgisi (A grubu) | 360 | 359 | 360 | 360 | 36 | 36 | 36 | 36 | 36 | 1619 |
| DHBT | 80 | - | 80 | - | 8 | - | 8 | - | - | 176 |
| **Toplam** | 880 | 559 | 880 | 560 | 108 | 56 | 88 | 48 | 72 | 3251 |

- Alan ve DHBT belgelerinde her test ayrı PDF'tir: belgede `kitapcikUrl` null, `kitapciklar` ({test: PDF adresi}) vardır. DHBT PDF'i düzey başınadır (lisans, ön lisans, ortaöğretim) ve DHBT-1 üçünde aynıdır (üç PDF'te aynı numara ve anahtar olduğu doğrulanır, bir kez alınır); testler `dhbt1`, `dhbt2-lisans`, `dhbt2-onlisans`, `dhbt2-ortaogretim`.
- ÖSYM sonradan cevap düzeltmesi ya da iptal yaparsa kitapçık anahtarında görünür: 2019 Muhasebe 30 anahtarda "İPTAL" (kitapçıkta "Bu soru iptal edilmiştir", yayımlanmaz); 2018 GK 43 (C→A) ve 2018 Alan İstatistik 18 (A→C) ÖSYM'nin 29.08.2018 sonuç duyurusunda düzeltilen cevaplardır, kitapçık anahtarı düzeltilmiş harfi verir ve dizin buna uyar.
- MEB çözüm bağlantısı KPSS için yok: `cozumUrl` null.
- Bilinen not: nosakademi-web dizini 2018 Alan İşletme 9 ve 17, 2020 Alan İstatistik 12 ile 2018 GK 43 / Alan İstatistik 18'i `iptal` işaretler; ÖSYM kitapçık anahtarı bunlarda harf verir (ilk üçü için iptal kanıtı bulunamadı), bu hatta anahtardaki harf esastır.

## Konu kimliği: `kpss_<ders>.<konu>` (kalıcı)
Dersler: `kpss_tur`, `kpss_mat` (GY); `kpss_tar`, `kpss_cog`, `kpss_vat`, `kpss_gun` (GK); `kpss_eb` (Eğitim Bilimleri); Alan Bilgisi: `kpss_huk`, `kpss_ikt`, `kpss_isl`, `kpss_ist`, `kpss_kamu`, `kpss_mal`, `kpss_muh`, `kpss_ui`, `kpss_ceei` (ders kodu test koduyla aynı); DHBT: `kpss_dhbt1`, `kpss_dhbt2` (üç düzeyin DHBT-2'si); ÖABT: `kpss_oabt_<branş>` (18 ders). Konu slug'ları nosakademi-web `data/kpss/konu-anahtarlari.ts` (alan: `kapsam.ts` ALAN_KAPSAM, DHBT: DHBT_KAPSAM) ile aynı. Katalog: `konular.json` (36 ders). Aynı slug farklı derste olabilir (`temel-kavramlar`: kpss_mat ve kpss_isl): kimlik ders önekiyle tekildir. Düzey (lisans/ön lisans/ortaöğretim) kimliğe girmez, belgenin `oturum`undadır (alan: `ALAN`, DHBT: `DHBT`). altKonu KPSS'de tanımlı değil.

## Dosyalar
`dist/cikmis-kpss.json`, `dist/cikmis-kpss-gorsel.json`, `dist/cikmis-kpss-gorsel-<ders>.bin` (36 paket: 18 KPSS + 18 ÖABT, en büyüğü kpss_tur ≈ 17,4 MB, toplam ≈ 282 MB). Yayın: `scripts/release.sh --cikmis-kpss` (latest release'e EKLER, `--clobber` yok, YKS ve nos.db'ye dokunmaz).

## Hat
indir → metin → kirp → etiket_birlestir → denetle → paketle → gorsel_paketle (modül docstring'i: `pipeline/cikmis/kpss/__init__.py`). Kırpmada cevap satırı görsele girmez (denetim bunu da doğrular). Alan/DHBT PDF'leri `yerel/kpss/pdf2/<belge>/`, 2018 GY-GK/EB/Ön Lisans/Ortaöğretim `yerel/kpss/pdf/<belge>.pdf`.

## ÖABT (2018-2024, 18 branş)
- Kaynak: nosakademi-web arşivi 124 PDF, 7 belge (`2018-oabt` ... `2024-oabt`, oturum `OABT`). 2018: 16 branş × 50 soru, 2019-2021: 18 branş × 75 (tam), 2022-2024: 18 branş × 8 (yüzde 10). Her branş ayrı PDF: `kitapcikUrl` null, `kitapciklar` test başına. Soru adedi PDF'ten okunur (`metin.json` `adet`).
- Test kodu branş slug'ı (beden-egitimi, biyoloji, cografya, din-kulturu-ve-ahlak-bilgisi, fen-bilimleri, fizik, ilkogretim-matematik, imam-hatip-lisesi-meslek-dersleri, ingilizce, kimya, matematik-lise, okul-oncesi, rehberlik, sinif-ogretmenligi, sosyal-bilgiler, tarih, turk-dili-ve-edebiyati, turkce); soru kimliği `2019-oabt-fizik-12`. Ders `kpss_oabt_<branş slug, tire alt çizgi>` (örn. `kpss_oabt_din_kulturu_ve_ahlak_bilgisi`), konu yalnız `alan-bilgisi` ve `alan-egitimi` (ÖSYM yüzde 80/20; İngilizce ve Sınıf Öğretmenliğinde 60/40). Branş alt konuları (sitedeki sözlük) KPSS formatında altKonu olmadığı için alınmadı. 2018'de Beden Eğitimi ve İmam Hatip yok, Almanca yalnız 2016-2017'de.
- Kutu içindeki soru ya da bağlam parçası dahil soru, kendi etiketinin altındadır (2023 İngilizce 67, 2024 İngilizce 51, 2024 Tarih 66); numara/etiket geometrisi sayfa görüntüsüyle doğrulandı, sitedeki 5 numara hatası `NOSAKADEMI-CEVAP-DUZELTMELERI.md`'de.
- Etiket: A ve B 5.282 soruda %94,6 uyuştu (4.998); 284 uyuşmazlık hakemle karara bağlandı (238'inde B, 46'sında A seçildi). Uyuşmazlıkların çoğu Okul Öncesi (123) ve Rehberlik (58): bu branşlarda içerik zaten pedagojik olduğu için A (içerikten) alan-egitimi dedi, ÖSYM blok yapısı (ilk %80 alan bilgisi) alan-bilgisi; hakem bloğu ağırlıklı tuttu. Konu etiketi ÖSYM bloğunu yansıtır; bu yüzden final konu sitenin konusundan yalnız 46/5.278 (%0,9) farklıdır. ÖABT etiketlerinin tamamı model kararıdır, özellikle Okul Öncesi ve Rehberlik blok sınırları insan denetimi bekler.
- UYARI (bağımsızlık): ÖABT A ajanlarının bir kısmı (g1, g2, g5 raporlarına göre) etiketleri testin blok konumundan (son ~15 soru, 2018'de son 10 alan-egitimi) türetti ve betikle yazdı; bu yüzden A ile B arasındaki %94,6 uyuşma bağımsız doğrulama sayılmaz, ikisi de ÖSYM blok yapısını yansıtır. Hakemler de blok kanıtını esas aldı. Blok sınırı belirsizlikleri: 2022-2024 Sınıf Öğretmenliği (yalnız 8 örnek soru, sınır doğrulanamadı; 2022-oabt-sinif-ogretmenligi-43, 2023-...-44, 2024-...-44 drama soruları alan-egitimi), Türkçe 1-20 dil becerileri bloğu (alan-bilgisi sayıldı; sitenin 2018-2021 etiketleri bu bloğu alan-egitimi yapmıştı), 2018 İngilizce alan eğitimi bloğu yalnız 41-50, fizik son soruları (2018-50, 2019-75, 2020-75). İçeriksiz iptal soruların etiketi tahmindir ve yayımlanmaz.
- 2021 Kimya 13: sitede `iptal`, kitapçık anahtarı A (muhtemelen ÖSYM düzeltmesi C→A); anahtardaki harf esas.

## Kesintiden devam
`uv run python -m pipeline.cikmis.kpss.devam` her belge için adımları (indir, metin, kirp, A, B, birlestir, hakem, denetle, paketle) diskteki çıktıdan tarar ve `yerel/kpss/ilerleme.json`'u atomik yazar (bekliyor | bitti | hata). `--calistir` eksik indir/metin/kirp adımlarını koşturur, `--girdi` etiketsiz soruların ajan girdilerini `yerel/kpss/etiketleme/girdi/` altına yazar (`A-<belge>.json`, B2 gerekiyorsa `B2-<belge>.json`). Etiketleme soru düzeyindedir: ajanlar çıktıyı `etiketleme/tam-<belge>-A.json`'a 10-20 soruda bir ekler, yeniden başlayan yalnız etiketsiz kimlikleri alır. Sonra `etiket_birlestir` (etiket dosyası olan belgeyi atlar, `--yeniden` zorlar) → hakem girdileri → `denetle` → `paketle` → `gorsel_paketle`. Her aile bitince commit.

## İnsan denetimi bekleyen etiketler
Tüm 3251 etiket model kararıdır, insan denetimi bekliyor (`etiket` alanı `insan` olana dek). İki bağımsız etiketleyici (A: bu hat, B: nosakademi-web dizini) 2018-2026'da yeni 2.236 soruda %92,7 uyuştu; 164 uyuşmazlık hakemle karara bağlandı (aşağıda). Önceki 101 hakem kaydına üçüncü bağımsız etiket verildi: 71'inde üçüncü etiket hakem kararıyla aynı (doğrulandı), 26'sında 2-2 beraberlik, 4'ünde dört farklı konu; bu 30 kayıt AÇIK (aşağıda "⚠ açık" işaretli).

### Yeni hakem kararları (2018-2026, 164 soru; kimlik: seçilen konu)
- 2018-alan-ceei-19: calisma-ekonomisi (hakem A dedi)
- 2018-alan-ceei-21: calisma-ekonomisi (hakem A dedi)
- 2018-alan-ceei-22: calisma-ekonomisi (hakem A dedi)
- 2018-alan-ceei-26: calisma-ekonomisi (hakem A dedi)
- 2018-alan-ceei-32: calisma-ekonomisi (hakem A dedi)
- 2018-alan-ceei-33: calisma-ekonomisi (hakem A dedi)
- 2018-alan-ceei-39: calisma-psikolojisi-ve-calisma-sosyolojisi (hakem üçüncü seçim; A: calisma-ekonomisi, B: is-ve-sosyal-guvenlik-hukuku)
- 2018-alan-huk-30: ticaret-hukuku (hakem A dedi)
- 2018-alan-ikt-26: para-banka-kredi (hakem A dedi)
- 2018-alan-ikt-38: turkiye-ekonomisi (hakem B dedi)
- 2018-alan-isl-17: uretim-yonetimi (hakem A dedi)
- 2018-alan-isl-22: uretim-yonetimi (hakem A dedi)
- 2018-alan-kamu-18: yonetim-bilimleri (hakem B dedi)
- 2018-alan-mal-6: kamu-gelirleri (hakem A dedi)
- 2018-alan-mal-14: kamu-giderleri (hakem A dedi)
- 2018-alan-mal-21: kamu-borclari (hakem A dedi)
- 2018-alan-mal-36: maliye-politikasi (hakem A dedi)
- 2018-alan-muh-39: ihtisas-muhasebesi (hakem B dedi)
- 2018-alan-ui-27: uluslararasi-guncel-sorunlar (hakem A dedi)
- 2018-alan-ui-29: uluslararasi-guncel-sorunlar (hakem A dedi)
- 2018-alan-ui-30: uluslararasi-guncel-sorunlar (hakem A dedi)
- 2018-dhbt-dhbt2-lisans-20: dini-hitabet (hakem B dedi)
- 2018-dhbt-dhbt2-ortaogretim-8: islam-tarihi (hakem A dedi)
- 2018-egitim-bilimleri-eb-19: ogretim-ilke-ve-yontemleri (hakem A dedi)
- 2018-egitim-bilimleri-eb-28: ogretim-teknolojileri (hakem A dedi)
- 2018-egitim-bilimleri-eb-55: gelisim-psikolojisi (hakem A dedi)
- 2018-lisans-gygk-gk-8: osmanli-kurulus-gerileme (hakem A dedi)
- 2018-lisans-gygk-gk-14: kurtulus-savasi (hakem A dedi)
- 2018-lisans-gygk-gk-37: nufus-yerlesme (hakem üçüncü seçim; A: ulasim-ticaret-turizm, B: ekonomik-cografya)
- 2018-lisans-gygk-gk-38: bolgeler (hakem B dedi)
- 2018-lisans-gygk-gk-51: yasama-yurutme-yargi (hakem A dedi)
- 2018-lisans-gygk-gy-3: sozcukte-anlam (hakem B dedi)
- 2018-lisans-gygk-gy-4: cumlede-anlam (hakem B dedi)
- 2018-lisans-gygk-gy-10: ses-yapi-sozcuk-turleri (hakem B dedi)
- 2018-lisans-gygk-gy-25: paragraf (hakem A dedi)
- 2018-lisans-gygk-gy-33: cebir (hakem A dedi)
- 2018-lisans-gygk-gy-34: cebir (hakem A dedi)
- 2018-lisans-gygk-gy-37: oran-oranti (hakem A dedi)
- 2018-lisans-gygk-gy-38: oran-oranti (hakem A dedi)
- 2018-lisans-gygk-gy-50: problemler (hakem A dedi)
- 2018-onlisans-gk-13: osmanli-dagilma (hakem A dedi)
- 2018-onlisans-gk-19: ataturk-donemi (hakem B dedi)
- 2018-onlisans-gk-30: cografi-konum (hakem A dedi)
- 2018-onlisans-gk-50: yasama-yurutme-yargi (hakem A dedi)
- 2018-onlisans-gy-1: sozcukte-anlam (hakem B dedi)
- 2018-onlisans-gy-4: cumlede-anlam (hakem B dedi)
- 2018-onlisans-gy-11: ses-yapi-sozcuk-turleri (hakem B dedi)
- 2018-onlisans-gy-22: paragraf (hakem A dedi)
- 2018-onlisans-gy-25: paragraf (hakem A dedi)
- 2018-onlisans-gy-33: cebir (hakem A dedi)
- 2018-onlisans-gy-35: temel-kavramlar (hakem B dedi)
- 2018-onlisans-gy-47: sayisal-mantik (hakem A dedi)
- 2018-ortaogretim-gk-5: osmanli-kurulus-gerileme (hakem A dedi)
- 2018-ortaogretim-gk-12: osmanli-dagilma (hakem A dedi)
- 2018-ortaogretim-gk-14: kurtulus-savasi (hakem A dedi)
- 2018-ortaogretim-gk-27: cagdas-tarih (hakem A dedi)
- 2018-ortaogretim-gk-39: iklim-bitki (hakem B dedi)
- 2018-ortaogretim-gk-46: yasama-yurutme-yargi (hakem A dedi)
- 2018-ortaogretim-gk-48: yasama-yurutme-yargi (hakem A dedi)
- 2018-ortaogretim-gk-55: guncel-dunya (hakem üçüncü seçim; A: guncel-bilim-spor-kultur, B: cagdas-tarih)
- 2018-ortaogretim-gk-58: guncel-dunya (hakem B dedi)
- 2018-ortaogretim-gk-59: guncel-turkiye (hakem üçüncü seçim; A: guncel-bilim-spor-kultur, B: turk-islam-devletleri)
- 2018-ortaogretim-gy-2: cumlede-anlam (hakem B dedi)
- 2018-ortaogretim-gy-3: cumlede-anlam (hakem B dedi)
- 2018-ortaogretim-gy-4: cumlede-anlam (hakem B dedi)
- 2018-ortaogretim-gy-32: temel-kavramlar (hakem B dedi)
- 2018-ortaogretim-gy-34: cebir (hakem A dedi)
- 2018-ortaogretim-gy-35: cebir (hakem A dedi)
- 2018-ortaogretim-gy-38: cebir (hakem B dedi)
- 2018-ortaogretim-gy-39: oran-oranti (hakem A dedi)
- 2018-ortaogretim-gy-46: temel-kavramlar (hakem A dedi)
- 2019-alan-ceei-29: calisma-ekonomisi (hakem A dedi)
- 2019-alan-ikt-1: iktisadi-doktrinler-tarihi (hakem B dedi)
- 2019-alan-ikt-22: makro-iktisat (hakem A dedi)
- 2019-alan-isl-1: temel-kavramlar (hakem A dedi)
- 2019-alan-isl-22: uretim-yonetimi (hakem A dedi)
- 2019-alan-isl-34: finansal-yonetim (hakem A dedi)
- 2019-alan-ist-23: uygulamali-istatistik (hakem üçüncü seçim; A: matematiksel-istatistik, B: ornekleme)
- 2019-alan-ist-25: uygulamali-istatistik (hakem A dedi)
- 2019-alan-kamu-3: siyaset-bilimi (hakem A dedi)
- 2019-alan-kamu-7: siyaset-bilimi (hakem A dedi)
- 2019-alan-kamu-13: anayasa (hakem B dedi)
- 2019-alan-kamu-19: yonetim-bilimleri (hakem A dedi)
- 2019-alan-kamu-21: yonetim-bilimleri (hakem A dedi)
- 2019-alan-kamu-37: turk-siyasi-hayati (hakem A dedi)
- 2019-alan-mal-36: maliye-politikasi (hakem A dedi)
- 2019-alan-mal-38: maliye-politikasi (hakem A dedi)
- 2019-alan-mal-40: maliye-politikasi (hakem B dedi)
- 2019-alan-muh-24: genel-muhasebe (hakem A dedi)
- 2019-alan-muh-25: genel-muhasebe (hakem A dedi)
- 2019-alan-muh-26: genel-muhasebe (hakem A dedi)
- 2019-alan-muh-29: mali-tablolar-analizi (hakem B dedi)
- 2019-alan-ui-27: uluslararasi-guncel-sorunlar (hakem üçüncü seçim; A: uluslararasi-orgutler, B: turk-dis-politikasi)
- 2019-alan-ui-34: uluslararasi-orgutler (hakem üçüncü seçim; A: uluslararasi-guncel-sorunlar, B: uluslararasi-hukuk)
- 2019-alan-ui-39: turk-dis-politikasi (hakem A dedi)
- 2020-alan-ceei-20: calisma-ekonomisi (hakem A dedi)
- 2020-alan-ceei-21: calisma-ekonomisi (hakem A dedi)
- 2020-alan-ceei-27: calisma-ekonomisi (hakem A dedi)
- 2020-alan-ceei-29: calisma-ekonomisi (hakem A dedi)
- 2020-alan-huk-5: anayasa-hukuku (hakem A dedi)
- 2020-alan-huk-21: medeni-hukuk (hakem B dedi)
- 2020-alan-ikt-19: makro-iktisat (hakem A dedi)
- 2020-alan-isl-3: temel-kavramlar (hakem B dedi)
- 2020-alan-isl-16: isletme-yonetimi (hakem A dedi)
- 2020-alan-isl-20: uretim-yonetimi (hakem A dedi)
- 2020-alan-isl-27: pazarlama-yonetimi (hakem A dedi)
- 2020-alan-ist-2: olasilik-ve-stokastik-surecler (hakem A dedi)
- 2020-alan-ist-6: olasilik-ve-stokastik-surecler (hakem B dedi)
- 2020-alan-ist-8: olasilik-ve-stokastik-surecler (hakem A dedi)
- 2020-alan-ist-21: uygulamali-istatistik (hakem B dedi)
- 2020-alan-ist-22: uygulamali-istatistik (hakem B dedi)
- 2020-alan-ist-23: uygulamali-istatistik (hakem üçüncü seçim; A: matematiksel-istatistik, B: ornekleme)
- 2020-alan-ist-36: ornekleme (hakem A dedi)
- 2020-alan-ist-39: regresyon-analizi (hakem A dedi)
- 2020-alan-kamu-17: yonetim-bilimleri (hakem A dedi)
- 2020-alan-kamu-26: yonetim-hukuku (hakem B dedi)
- 2020-alan-mal-8: kamu-gelirleri (hakem B dedi)
- 2020-alan-mal-10: kamu-gelirleri (hakem B dedi)
- 2020-alan-mal-15: kamu-giderleri (hakem A dedi)
- 2020-alan-mal-35: maliye-politikasi (hakem A dedi)
- 2020-alan-muh-17: ihtisas-muhasebesi (hakem A dedi)
- 2020-alan-muh-18: ihtisas-muhasebesi (hakem A dedi)
- 2020-alan-muh-19: ihtisas-muhasebesi (hakem A dedi)
- 2020-alan-muh-20: ihtisas-muhasebesi (hakem A dedi)
- 2020-alan-muh-21: mali-tablolar-analizi (hakem B dedi)
- 2020-alan-muh-22: genel-muhasebe (hakem A dedi)
- 2020-alan-muh-23: genel-muhasebe (hakem A dedi)
- 2020-alan-muh-24: genel-muhasebe (hakem A dedi)
- 2020-alan-muh-32: mali-tablolar-analizi (hakem B dedi)
- 2020-alan-ui-30: uluslararasi-guncel-sorunlar (hakem A dedi)
- 2020-dhbt-dhbt1-9: kur-an-bilgisi (hakem B dedi)
- 2020-dhbt-dhbt1-12: kur-an-bilgisi (hakem B dedi)
- 2021-alan-ceei-29: calisma-ekonomisi (hakem A dedi)
- 2021-alan-ceei-30: calisma-ekonomisi (hakem A dedi)
- 2021-alan-ikt-24: para-banka-kredi (hakem A dedi)
- 2021-alan-ikt-26: para-banka-kredi (hakem A dedi)
- 2021-alan-ikt-27: para-banka-kredi (hakem A dedi)
- 2021-alan-ikt-33: kalkinma-ve-buyume (hakem A dedi)
- 2021-alan-isl-30: pazarlama-yonetimi (hakem A dedi)
- 2021-alan-ist-9: olasilik-ve-stokastik-surecler (hakem A dedi)
- 2021-alan-ist-11: olasilik-ve-stokastik-surecler (hakem A dedi)
- 2021-alan-ist-22: uygulamali-istatistik (hakem A dedi)
- 2021-alan-ist-23: uygulamali-istatistik (hakem B dedi)
- 2021-alan-ist-24: uygulamali-istatistik (hakem B dedi)
- 2021-alan-ist-25: uygulamali-istatistik (hakem üçüncü seçim; A: matematiksel-istatistik, B: ornekleme)
- 2021-alan-ist-26: uygulamali-istatistik (hakem üçüncü seçim; A: matematiksel-istatistik, B: ornekleme)
- 2021-alan-kamu-4: siyaset-bilimi (hakem A dedi)
- 2021-alan-kamu-9: anayasa (hakem B dedi)
- 2021-alan-kamu-12: anayasa (hakem A dedi)
- 2021-alan-mal-9: kamu-gelirleri (hakem A dedi)
- 2021-alan-mal-12: kamu-giderleri (hakem A dedi)
- 2021-alan-mal-40: maliye-politikasi (hakem A dedi)
- 2021-alan-muh-17: ihtisas-muhasebesi (hakem A dedi)
- 2021-alan-muh-20: ihtisas-muhasebesi (hakem A dedi)
- 2021-alan-muh-29: mali-tablolar-analizi (hakem A dedi)
- 2021-alan-muh-31: mali-tablolar-analizi (hakem A dedi)
- 2021-alan-ui-13: uluslararasi-hukuk (hakem A dedi)
- 2021-alan-ui-39: turk-dis-politikasi (hakem B dedi)
- 2022-alan-muh-22: genel-muhasebe (hakem A dedi)
- 2022-alan-muh-40: ihtisas-muhasebesi (hakem B dedi)
- 2023-alan-ceei-37: calisma-ekonomisi (hakem A dedi)
- 2023-alan-kamu-33: kentlesme-ve-cevre-sorunlari (hakem A dedi)
- 2025-alan-kamu-31: kentlesme-ve-cevre-sorunlari (hakem A dedi)
- 2026-alan-ikt-2: iktisadi-doktrinler-tarihi (hakem A dedi)

### Önceki 101 hakem kaydı (üçüncü bağımsız etiketle)
Doğrulanmış (T = hakem): 71 kayıt, listede işaretsiz. ⚠ açık (insan karar vermeli): beraberlik ya da dört farklı.

- 2019-egitim-bilimleri-eb-3: ogrenme-psikolojisi  ⚠ açık (beraberlik: A ogrenme-psikolojisi, B program-gelistirme, üçüncü program-gelistirme)
- 2019-egitim-bilimleri-eb-7: ogretim-ilke-ve-yontemleri
- 2019-egitim-bilimleri-eb-18: ogretim-ilke-ve-yontemleri
- 2019-lisans-gygk-gk-11: osmanli-dagilma
- 2019-lisans-gygk-gk-12: osmanli-dagilma
- 2019-lisans-gygk-gk-20: kurtulus-savasi  ⚠ açık (beraberlik: A ataturk-donemi, B kurtulus-savasi, üçüncü ataturk-donemi)
- 2019-lisans-gygk-gk-35: nufus-yerlesme  ⚠ açık (uc-farkli: A nufus-yerlesme, B guncel-bilim-spor-kultur, üçüncü islamiyet-oncesi)
- 2019-lisans-gygk-gk-39: iklim-bitki  ⚠ açık (beraberlik: A iklim-bitki, B ekonomik-cografya, üçüncü ekonomik-cografya)
- 2019-lisans-gygk-gk-48: yasama-yurutme-yargi
- 2019-lisans-gygk-gk-56: kurtulus-savasi
- 2019-lisans-gygk-gk-57: osmanli-dagilma
- 2019-lisans-gygk-gk-59: guncel-turkiye  ⚠ açık (beraberlik: A guncel-turkiye, B guncel-bilim-spor-kultur, üçüncü guncel-bilim-spor-kultur)
- 2019-lisans-gygk-gy-33: cebir
- 2019-lisans-gygk-gy-35: oran-oranti  ⚠ açık (beraberlik: A oran-oranti, B cebir, üçüncü cebir)
- 2019-lisans-gygk-gy-37: oran-oranti
- 2019-lisans-gygk-gy-39: temel-kavramlar
- 2019-lisans-gygk-gy-48: problemler
- 2019-lisans-gygk-gy-49: sayisal-mantik
- 2019-lisans-gygk-gy-50: kumeler-fonksiyonlar
- 2019-lisans-gygk-gy-54: geometri
- 2019-lisans-gygk-gy-55: geometri
- 2019-lisans-gygk-gy-56: geometri
- 2020-egitim-bilimleri-eb-21: ogrenme-psikolojisi  ⚠ açık (beraberlik: A ogrenme-psikolojisi, B ogretim-ilke-ve-yontemleri, üçüncü ogretim-ilke-ve-yontemleri)
- 2020-egitim-bilimleri-eb-26: ogretim-ilke-ve-yontemleri  ⚠ açık (beraberlik: A ogretim-ilke-ve-yontemleri, B ogretim-teknolojileri, üçüncü ogretim-teknolojileri)
- 2020-egitim-bilimleri-eb-30: ogretim-teknolojileri
- 2020-lisans-gygk-gk-7: osmanli-kurulus-gerileme
- 2020-lisans-gygk-gk-14: kurtulus-savasi  ⚠ açık (beraberlik: A kurtulus-savasi, B osmanli-dagilma, üçüncü osmanli-dagilma)
- 2020-lisans-gygk-gk-47: anayasa-temel-haklar
- 2020-lisans-gygk-gk-48: yasama-yurutme-yargi
- 2020-lisans-gygk-gk-52: yasama-yurutme-yargi
- 2020-lisans-gygk-gk-56: turk-islam-devletleri
- 2020-lisans-gygk-gk-57: guncel-bilim-spor-kultur
- 2020-lisans-gygk-gy-2: sozcukte-anlam
- 2020-lisans-gygk-gy-32: cebir
- 2020-lisans-gygk-gy-33: cebir
- 2020-lisans-gygk-gy-35: oran-oranti  ⚠ açık (beraberlik: A oran-oranti, B cebir, üçüncü cebir)
- 2020-lisans-gygk-gy-38: oran-oranti
- 2020-lisans-gygk-gy-41: oran-oranti  ⚠ açık (beraberlik: A oran-oranti, B cebir, üçüncü cebir)
- 2020-lisans-gygk-gy-42: temel-kavramlar
- 2020-lisans-gygk-gy-45: temel-kavramlar
- 2020-lisans-gygk-gy-48: problemler
- 2020-lisans-gygk-gy-50: problemler
- 2020-onlisans-gk-13: osmanli-dagilma
- 2020-onlisans-gk-20: kurtulus-savasi  ⚠ açık (beraberlik: A kurtulus-savasi, B ataturk-donemi, üçüncü ataturk-donemi)
- 2020-onlisans-gk-43: cografi-konum
- 2020-onlisans-gk-48: yasama-yurutme-yargi
- 2020-onlisans-gk-49: yasama-yurutme-yargi
- 2020-onlisans-gy-5: paragraf  ⚠ açık (beraberlik: A paragraf, B sozcukte-anlam, üçüncü sozcukte-anlam)
- 2020-onlisans-gy-6: paragraf
- 2020-onlisans-gy-36: oran-oranti
- 2020-onlisans-gy-43: temel-kavramlar  ⚠ açık (beraberlik: A temel-kavramlar, B cebir, üçüncü cebir)
- 2020-ortaogretim-gk-8: osmanli-kurulus-gerileme
- 2020-ortaogretim-gk-13: osmanli-dagilma
- 2020-ortaogretim-gk-31: cografi-konum
- 2020-ortaogretim-gk-39: ulasim-ticaret-turizm  ⚠ açık (uc-farkli: A ulasim-ticaret-turizm, B guncel-bilim-spor-kultur, üçüncü islamiyet-oncesi)
- 2020-ortaogretim-gk-41: ekonomik-cografya
- 2020-ortaogretim-gk-47: yasama-yurutme-yargi
- 2020-ortaogretim-gk-56: guncel-bilim-spor-kultur  ⚠ açık (uc-farkli: A guncel-turkiye, B guncel-bilim-spor-kultur, üçüncü kurtulus-savasi)
- 2020-ortaogretim-gk-57: osmanli-dagilma
- 2020-ortaogretim-gk-58: guncel-bilim-spor-kultur  ⚠ açık (beraberlik: A guncel-bilim-spor-kultur, B turk-islam-devletleri, üçüncü turk-islam-devletleri)
- 2020-ortaogretim-gk-60: guncel-turkiye
- 2020-ortaogretim-gy-3: paragraf
- 2020-ortaogretim-gy-23: paragraf
- 2020-ortaogretim-gy-32: cebir
- 2020-ortaogretim-gy-33: cebir
- 2020-ortaogretim-gy-48: sayisal-mantik
- 2021-egitim-bilimleri-eb-6: ogrenme-psikolojisi
- 2021-egitim-bilimleri-eb-23: sinif-yonetimi
- 2021-egitim-bilimleri-eb-73: rehberlik-ve-ozel-egitim  ⚠ açık (beraberlik: A rehberlik-ve-ozel-egitim, B sinif-yonetimi, üçüncü sinif-yonetimi)
- 2021-egitim-bilimleri-eb-77: olcme-ve-degerlendirme
- 2021-lisans-gygk-gk-5: osmanli-kurulus-gerileme
- 2021-lisans-gygk-gk-20: ataturk-donemi
- 2021-lisans-gygk-gk-26: ataturk-donemi  ⚠ açık (beraberlik: A ataturk-donemi, B cagdas-tarih, üçüncü cagdas-tarih)
- 2021-lisans-gygk-gk-59: guncel-bilim-spor-kultur  ⚠ açık (uc-farkli: A guncel-bilim-spor-kultur, B cografi-konum, üçüncü guncel-turkiye)
- 2021-lisans-gygk-gy-4: paragraf
- 2021-lisans-gygk-gy-25: sozcukte-anlam
- 2021-lisans-gygk-gy-32: cebir
- 2021-lisans-gygk-gy-33: cebir
- 2021-lisans-gygk-gy-34: cebir
- 2021-lisans-gygk-gy-41: oran-oranti  ⚠ açık (beraberlik: A oran-oranti, B cebir, üçüncü cebir)
- 2021-lisans-gygk-gy-54: geometri
- 2021-lisans-gygk-gy-55: geometri
- 2021-lisans-gygk-gy-56: geometri
- 2022-egitim-bilimleri-eylul-eb-35: program-gelistirme
- 2022-lisans-gygk-eylul-gy-1: sozcukte-anlam  ⚠ açık (beraberlik: A cumlede-anlam, B sozcukte-anlam, üçüncü cumlede-anlam)
- 2022-onlisans-gy-4: cumlede-anlam
- 2022-ortaogretim-gk-40: cografi-konum (+ulasim-ticaret-turizm)  ⚠ açık (beraberlik: A ulasim-ticaret-turizm, B cografi-konum, üçüncü ulasim-ticaret-turizm)
- 2022-ortaogretim-gy-1: sozcukte-anlam
- 2022-ortaogretim-gy-47: sayisal-mantik
- 2023-lisans-gygk-gy-1: sozcukte-anlam  ⚠ açık (beraberlik: A cumlede-anlam, B sozcukte-anlam, üçüncü cumlede-anlam)
- 2024-egitim-bilimleri-eb-3: ogretim-ilke-ve-yontemleri  ⚠ açık (beraberlik: A program-gelistirme, B ogretim-ilke-ve-yontemleri, üçüncü program-gelistirme)
- 2024-lisans-gygk-gk-21: kurtulus-savasi
- 2024-lisans-gygk-gy-1: sozcukte-anlam  ⚠ açık (beraberlik: A cumlede-anlam, B sozcukte-anlam, üçüncü cumlede-anlam)
- 2024-onlisans-gk-54: idare-hukuku
- 2024-onlisans-gy-1: sozcukte-anlam
- 2026-lisans-gygk-gk-46: yasama-yurutme-yargi  ⚠ açık (beraberlik: A anayasa-temel-haklar, B yasama-yurutme-yargi, üçüncü anayasa-temel-haklar)
- 2026-lisans-gygk-gy-1: sozcukte-anlam  ⚠ açık (beraberlik: A cumlede-anlam, B sozcukte-anlam, üçüncü cumlede-anlam)
- 2026-onlisans-gk-11: osmanli-dagilma
- 2026-onlisans-gk-24: ataturk-donemi
- 2026-onlisans-gy-1: sozcukte-anlam  ⚠ açık (beraberlik: A cumlede-anlam, B sozcukte-anlam, üçüncü cumlede-anlam)
- 2026-ortaogretim-gy-1: sozcukte-anlam  ⚠ açık (beraberlik: A cumlede-anlam, B sozcukte-anlam, üçüncü cumlede-anlam)

Sınır sorular (öncelik): şekil/formülü metne çıkmayan matematik ve istatistik, Göbeklitepe ve Darülaceze, İbn Haldun, sözcükte-anlam / cümlede-anlam, EB'de yıllık plan / program geliştirme / taksonomi, alan testlerinde komşu konular (örn. mikro/makro iktisat, genel muhasebe / mali tablolar).

### Etiketleyici ve hakem notları (ek sınır sorular)
- Alan testlerinde ÖSYM soruları konu bloklarına göre dizer (örn. UI: teori 1-8, hukuk 9-18, siyasi tarih 19-26, güncel sorunlar 27-30, örgütler 31-34, dış politika 35-40); hakemler içerik iki konuya uyduğunda bloğu esas aldı. %10 kitapçıklarda blok kanıtı zayıftır (örn. 2023-alan-ceei-37).
- Hakemin içerik ile blok arasında kaldığı sorular: 2018-alan-kamu-18, 2018-alan-muh-39, 2019-alan-kamu-13, 2019-alan-mal-40, 2020-alan-huk-5, 2020-alan-ist-6, 2020-alan-mal-8, 2020-alan-mal-10.
- Üçüncü konu seçilen alan soruları: 2018-alan-ceei-39, 2019-alan-ist-23, 2019-alan-ui-27 (ek: uluslararasi-orgutler), 2019-alan-ui-34, 2020-alan-ist-23, 2021-alan-ist-25, 2021-alan-ist-26.
- A etiketleyicinin kararsız kaldığı (hakeme gitmemiş, uyuşmuş olabilir) alan soruları: 2021-alan-isl-1, isl-2, muh-13, muh-14, muh-17, muh-19, muh-20, muh-21, muh-24, kamu-9, kamu-20, ikt-24, ui-27, ui-30, ui-39, ceei-20, ceei-33; 2018-alan-ikt-5, ikt-26, ikt-37, ikt-38, isl-15, isl-18, isl-19, ui-7, ui-8.
- Alan İstatistik'te formül ve şekil metne çıkmadığı için birçok soru (2018 ist 1-5, 8, 10-12, 14-18 gibi) soru kökünden etiketlendi; 2018 GY-GK matematik gy-31..45 aralığında da hata payı var.
- 2018 GY-GK: lisans gk-37 (yayla: nufus-yerlesme), ortaöğretim gk-55 (guncel-dunya), gk-59 (guncel-turkiye), gk-27 (cagdas-tarih), gk-29 (uluslararasi-kuruluslar) hakem/A kararıdır, tartışmalı.

## Filigran soluklaştırma (yeni ÖSYM kitapçıkları)
ÖSYM filigranı bazı kitapçıklarda sayfaya ANOTASYON olarak biner ve tonu 128-166'dır (eski: 179-205); `kirp.soluk_tablosu` eşlemesi bunu açamaz. `kirp.FiligranCizici` PDF'ten filigran tonunu ölçer (anotasyonlu ve anotasyonsuz çizimin farkının modu); ton < 170 ise sayfa iki kez çizilir (A anotasyonlu, B anotasyonsuz) ve sonuç `B - k*(B-A)` olur, k = (255-212)/(255-ton): filigran ~212'ye çıkar, metin siyah kalır, sorunun kendi gri şekilleri ve tabloları B'de olduğu için değişmez. Silinmez, soluklaşır. Ton >= 170 olan belgeler eski eşlemeyle aynen kalır. Etkilenen belgeleri bulup yeniden kırpan, kesintiden devam eden araç: `python -m pipeline.cikmis.filigran_yeniden` (`yerel/filigran-ilerleme.json`); sonra YKS ve KPSS `gorsel_paketle`. Etkilenen: KPSS 35 belge (2018-2021 tümü, 2022 Ortaöğretim ve DHBT, 2023-2026), YKS 2020 ve 2021 TYT/AYT/YDT ile 2026 YDT. Denetim ölçüsü: 100-199 gri bandı (140-199 değil; ton-128 filigranı 140 altındadır).

### Etiketleyici yöntem raporları (2026-11-24)
- ÖABT kör A turu (8 ajan): hepsi her soruyu içerikten tek tek etiketlediğini bildirdi; konumdan/numaradan türetme yok. Sapmalar: çıktı dosyası 20 yerine 40-100 soruda bir yazıldı, b5 600 karakterden uzun sorularda yalnız baş ve son kısmı gördü, b6 ve b8 elle yazdıkları parça dosyalarını betikle birleştirdi (etiket üretmedi). ÖABT hakem turu (3 ajan, 273 soru, görselle): 78 kararda blok konumu tie-break olarak kullanıldı (h1 7, h2 42, h3 29); h3 blok sınırını bu belgede grep'ledi.
- Önceki 41 belgenin A etiketleyicileri (yayında): 2019-alan ve 2020-alan A ajanları etiketleri soru numarası aralıklarına ("no a-b => konu") göre, testin konu bloklarından kurup Python betiğiyle toplu yazdı; yalnız sınır sorularında içeriğe baktı. DHBT A ajanı etiketleri blok sırasına göre dizip betikle yazdı (2018, 2020; 2022 ve 2024 tek tek). 2018 GY-GK/EB A ajanı kısmen sıra bloğuna baktı. 2018-alan, 2021-alan ve 2022-2026 alan A ajanları içerikten etiketledi (2022-2026 elle yazılan sözlükleri betikle JSON'a döktü). Bu dört grubun A etiketi bağımsız sayılamaz: 2019-alan (360), 2020-alan (360), DHBT (176), 2018 GY-GK/EB (440 soru, kısmen).
