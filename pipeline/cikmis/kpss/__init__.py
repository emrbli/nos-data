"""KPSS ÇIKMIŞ SORU DİZİNİ: YKS hattının (`pipeline/cikmis`) birebir aynı biçimi.

Çıktı (release varlığı, bu tur YAYINLANMADI): `dist/cikmis-kpss.json` (künye dizini),
`dist/cikmis-kpss-gorsel.json` + `dist/cikmis-kpss-gorsel-<ders>.bin` (soru görselleri).
Adlar YKS'nin `cikmis*.{json,bin}` adlarıyla çakışmaz; YKS dosyalarına ve nos.db'ye dokunulmaz.

Kapsam: 2019-2026. 2019-2021 TAM kitapçıklar (`kapsam: tam`; GY/GK 60, EB 80 soru; cevap sondaki anahtar tablosunda). 2022-2026: ÖSYM 2022'den beri yalnız yüzde 10'unu
yayımlar: GY ve GK testlerinden 6'şar, Eğitim Bilimleri'nden 8 soru, özgün soru numarasıyla; yayımlanan
soruların cevabı sayfada "DOĞRU CEVAP: X" satırındadır (ayrı anahtar sayfası yok). Bu yüzden kapsam
`yuzde10`, etiket dosyalarında yalnız yayımlanan numaralar bulunur.

Kurallar YKS ile aynı (bkz. pipeline/cikmis/__init__.py): soru metni künyeye girmez; PDF, metin ve
ham etiketleme yalnız yerel (`pipeline/cikmis/yerel/kpss/`, gitignore); cevap yalnız ÖSYM'nin
sayfadaki "DOĞRU CEVAP" satırından; konu kimlikleri `konular.json`'dan (`kpss_<ders>.<konu>`).
Etiket: nosakademi-web'in bağımsız konu dizini ile bu hattaki ayrı etiketleme uyuşursa `cift-onay`,
uyuşmazsa sayfa görselinden üçüncü karar `hakem`, kararsız `belirsiz` (yayımlanmaz).
MEB çözüm bağlantısı KPSS için yok: `cozum_ekle` adımı yoktur, `cozumUrl` null.

Hat (nos-data kökünden):
  uv run --with httpx python -m pipeline.cikmis.kpss.indir
  uv run --with pdfplumber --with pypdf python -m pipeline.cikmis.kpss.metin    # sayfa, cevap, yerel metin
  # etiketleme: yerel/kpss/metin/<belge>.json okunur; kpss/etiket_birlestir.py etiket/*.json yazar
  uv run --with pdfplumber --with pypdf python -m pipeline.cikmis.kpss.denetle [--baglanti]
  uv run --with pdfplumber --with pypdf python -m pipeline.cikmis.kpss.paketle    # -> dist/cikmis-kpss.json
  uv run --with pdfplumber --with pypdfium2 --with pillow python -m pipeline.cikmis.kpss.kirp
  uv run python -m pipeline.cikmis.kpss.gorsel_paketle
  scripts/release.sh --cikmis-kpss [--dry-run]   # YAYIN: bu tur çalıştırılmadı
"""
