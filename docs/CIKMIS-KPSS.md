# KPSS çıkmış soru dizini (pipeline/cikmis/kpss)

YKS hattının (`pipeline/cikmis`) birebir aynı biçimi. Bu tur YAYINLANMADI; çıktılar `dist/` altında hazır.

## Kapsam ve gerçek
- GENİŞLETME (2026-11-24, nosapp kararı): 2019-2026, YKS aralığıyla aynı. 2019-2021 TAM kitapçıklar (kapsam `tam`: GY ve GK 60'ar, EB 80 soru, cevap sondaki anahtar tablosundan) eklendi: Lisans GY-GK 2019/2020/2021, Eğitim Bilimleri 2019/2020/2021, Ön Lisans 2020, Ortaöğretim 2020 (2019 ve 2021'de Ön Lisans/Ortaöğretim sınavı yok). Toplam 24 kitapçık, 1016 soru (840 tam + 176 yüzde10). Aşağıdaki "yalnız %10" cümleleri 2022-2026 içindir.
- Son 5 KPSS yılı: 2022-2026. ÖSYM 2022'den beri soruların YALNIZ %10'unu yayımlar: GY ve GK'dan 6'şar, Eğitim Bilimleri'nden 8 soru, özgün numarasıyla; cevap sayfada "DOĞRU CEVAP: X" satırındadır. Bu yüzden `kapsam: yuzde10`, etiket dosyalarında yalnız yayımlanan numaralar vardır (denetim bunu kitapçıkla çapraz kontrol eder).
- 16 kitapçık: Lisans GY-GK 2022 temmuz, 2022 eylül, 2023, 2024, 2025, 2026; Eğitim Bilimleri 2022 temmuz, 2022 eylül, 2023, 2024 (2025'ten beri KPSS'de yok); Ön Lisans 2022, 2024, 2026; Ortaöğretim 2022, 2024, 2026. 176 soru.
- Alan bilgisi (A grubu) ve ÖABT bu turda yok. Belge kimlikleri nosakademi-web `cikmis-sorular-arsivi.ts` kayıt kimlikleriyle aynı.
- MEB çözüm bağlantısı KPSS için yok: `cozum_ekle` adımı yok, `cozumUrl` null.

## Konu kimliği: `kpss_<ders>.<konu>` (kalıcı)
Dersler: `kpss_tur`, `kpss_mat` (GY); `kpss_tar`, `kpss_cog`, `kpss_vat`, `kpss_gun` (GK); `kpss_eb` (Eğitim Bilimleri). Konu slug'ları nosakademi-web `data/kpss/konu-anahtarlari.ts` ile aynı (orada 11.512 soruluk dizin bu slug'larla etiketli). Katalog: `konular.json` (46 konu). Düzey (lisans/ön lisans/ortaöğretim) kimliğe girmez, belgenin `oturum`undadır. altKonu KPSS'de tanımlı değil (YKS'de de yalnız tyt_mat.problem).

## Dosyalar
`dist/cikmis-kpss.json`, `dist/cikmis-kpss-gorsel.json`, `dist/cikmis-kpss-gorsel-kpss_{tur,mat,tar,cog,vat,gun,eb}.bin`. Yayın: `scripts/release.sh --cikmis-kpss` (latest release'e EKLER, `--clobber` yok, YKS ve nos.db'ye dokunmaz).

## Hat
indir → metin → etiket_birlestir → denetle → paketle → kirp → gorsel_paketle (modül docstring'i: `pipeline/cikmis/kpss/__init__.py`). Kırpmada cevap satırı görsele girmez (denetim bunu da doğrular).

## İnsan denetimi bekleyen etiketler
Tüm 1016 etiket model kararıdır, insan denetimi bekliyor (`etiket` alanı `insan` olana dek). Öncelik: aşağıdaki 101 `hakem` kararı (iki etiketleyici uyuşmadı). Özellikle sınır sorular: şekil/formülü metne çıkmayan matematik (temel-kavramlar/cebir/kumeler ayrımı), Göbeklitepe ve Darülaceze, İbn Haldun, sözcükte-anlam / cümlede-anlam ayrımı (kural: boşluk doldurma ve "altı çizili sözle anlatılmak istenen" sozcukte-anlam, tek cümleden anlam cumlede-anlam), EB'de yıllık/ders planı (ogretim-ilke-ve-yontemleri) ile program-gelistirme ve taksonomi (program-gelistirme/ogrenme-psikolojisi). Etiket dosyalarındaki kimlik `<belge>-<test>-<no>`; karar `kimlik: seçilen konu`:

- 2019-egitim-bilimleri-eb-3: ogrenme-psikolojisi
- 2019-egitim-bilimleri-eb-7: ogretim-ilke-ve-yontemleri
- 2019-egitim-bilimleri-eb-18: ogretim-ilke-ve-yontemleri
- 2019-lisans-gygk-gk-11: osmanli-dagilma
- 2019-lisans-gygk-gk-12: osmanli-dagilma
- 2019-lisans-gygk-gk-20: kurtulus-savasi
- 2019-lisans-gygk-gk-35: nufus-yerlesme
- 2019-lisans-gygk-gk-39: iklim-bitki
- 2019-lisans-gygk-gk-48: yasama-yurutme-yargi
- 2019-lisans-gygk-gk-56: kurtulus-savasi
- 2019-lisans-gygk-gk-57: osmanli-dagilma
- 2019-lisans-gygk-gk-59: guncel-turkiye
- 2019-lisans-gygk-gy-33: cebir
- 2019-lisans-gygk-gy-35: oran-oranti
- 2019-lisans-gygk-gy-37: oran-oranti
- 2019-lisans-gygk-gy-39: temel-kavramlar
- 2019-lisans-gygk-gy-48: problemler
- 2019-lisans-gygk-gy-49: sayisal-mantik
- 2019-lisans-gygk-gy-50: kumeler-fonksiyonlar
- 2019-lisans-gygk-gy-54: geometri
- 2019-lisans-gygk-gy-55: geometri
- 2019-lisans-gygk-gy-56: geometri
- 2020-egitim-bilimleri-eb-21: ogrenme-psikolojisi
- 2020-egitim-bilimleri-eb-26: ogretim-ilke-ve-yontemleri
- 2020-egitim-bilimleri-eb-30: ogretim-teknolojileri
- 2020-lisans-gygk-gk-7: osmanli-kurulus-gerileme
- 2020-lisans-gygk-gk-14: kurtulus-savasi
- 2020-lisans-gygk-gk-47: anayasa-temel-haklar
- 2020-lisans-gygk-gk-48: yasama-yurutme-yargi
- 2020-lisans-gygk-gk-52: yasama-yurutme-yargi
- 2020-lisans-gygk-gk-56: turk-islam-devletleri
- 2020-lisans-gygk-gk-57: guncel-bilim-spor-kultur
- 2020-lisans-gygk-gy-2: sozcukte-anlam
- 2020-lisans-gygk-gy-32: cebir
- 2020-lisans-gygk-gy-33: cebir
- 2020-lisans-gygk-gy-35: oran-oranti
- 2020-lisans-gygk-gy-38: oran-oranti
- 2020-lisans-gygk-gy-41: oran-oranti
- 2020-lisans-gygk-gy-42: temel-kavramlar
- 2020-lisans-gygk-gy-45: temel-kavramlar
- 2020-lisans-gygk-gy-48: problemler
- 2020-lisans-gygk-gy-50: problemler
- 2020-onlisans-gk-13: osmanli-dagilma
- 2020-onlisans-gk-20: kurtulus-savasi
- 2020-onlisans-gk-43: cografi-konum
- 2020-onlisans-gk-48: yasama-yurutme-yargi
- 2020-onlisans-gk-49: yasama-yurutme-yargi
- 2020-onlisans-gy-5: paragraf
- 2020-onlisans-gy-6: paragraf
- 2020-onlisans-gy-36: oran-oranti
- 2020-onlisans-gy-43: temel-kavramlar
- 2020-ortaogretim-gk-8: osmanli-kurulus-gerileme
- 2020-ortaogretim-gk-13: osmanli-dagilma
- 2020-ortaogretim-gk-31: cografi-konum
- 2020-ortaogretim-gk-39: ulasim-ticaret-turizm
- 2020-ortaogretim-gk-41: ekonomik-cografya
- 2020-ortaogretim-gk-47: yasama-yurutme-yargi
- 2020-ortaogretim-gk-56: guncel-bilim-spor-kultur
- 2020-ortaogretim-gk-57: osmanli-dagilma
- 2020-ortaogretim-gk-58: guncel-bilim-spor-kultur
- 2020-ortaogretim-gk-60: guncel-turkiye
- 2020-ortaogretim-gy-3: paragraf
- 2020-ortaogretim-gy-23: paragraf
- 2020-ortaogretim-gy-32: cebir
- 2020-ortaogretim-gy-33: cebir
- 2020-ortaogretim-gy-48: sayisal-mantik
- 2021-egitim-bilimleri-eb-6: ogrenme-psikolojisi
- 2021-egitim-bilimleri-eb-23: sinif-yonetimi
- 2021-egitim-bilimleri-eb-73: rehberlik-ve-ozel-egitim
- 2021-egitim-bilimleri-eb-77: olcme-ve-degerlendirme
- 2021-lisans-gygk-gk-5: osmanli-kurulus-gerileme
- 2021-lisans-gygk-gk-20: ataturk-donemi
- 2021-lisans-gygk-gk-26: ataturk-donemi
- 2021-lisans-gygk-gk-59: guncel-bilim-spor-kultur
- 2021-lisans-gygk-gy-4: paragraf
- 2021-lisans-gygk-gy-25: sozcukte-anlam
- 2021-lisans-gygk-gy-32: cebir
- 2021-lisans-gygk-gy-33: cebir
- 2021-lisans-gygk-gy-34: cebir
- 2021-lisans-gygk-gy-41: oran-oranti
- 2021-lisans-gygk-gy-54: geometri
- 2021-lisans-gygk-gy-55: geometri
- 2021-lisans-gygk-gy-56: geometri
- 2022-egitim-bilimleri-eylul-eb-35: program-gelistirme
- 2022-lisans-gygk-eylul-gy-1: sozcukte-anlam
- 2022-onlisans-gy-4: cumlede-anlam
- 2022-ortaogretim-gk-40: cografi-konum (+ulasim-ticaret-turizm)
- 2022-ortaogretim-gy-1: sozcukte-anlam
- 2022-ortaogretim-gy-47: sayisal-mantik
- 2023-lisans-gygk-gy-1: sozcukte-anlam
- 2024-egitim-bilimleri-eb-3: ogretim-ilke-ve-yontemleri
- 2024-lisans-gygk-gk-21: kurtulus-savasi
- 2024-lisans-gygk-gy-1: sozcukte-anlam
- 2024-onlisans-gk-54: idare-hukuku
- 2024-onlisans-gy-1: sozcukte-anlam
- 2026-lisans-gygk-gk-46: yasama-yurutme-yargi
- 2026-lisans-gygk-gy-1: sozcukte-anlam
- 2026-onlisans-gk-11: osmanli-dagilma
- 2026-onlisans-gk-24: ataturk-donemi
- 2026-onlisans-gy-1: sozcukte-anlam
- 2026-ortaogretim-gy-1: sozcukte-anlam
