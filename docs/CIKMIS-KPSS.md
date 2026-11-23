# KPSS çıkmış soru dizini (pipeline/cikmis/kpss)

YKS hattının (`pipeline/cikmis`) birebir aynı biçimi. Bu tur YAYINLANMADI; çıktılar `dist/` altında hazır.

## Kapsam ve gerçek
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
