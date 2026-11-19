"""ÇIKMIŞ SORU DİZİNİ: ÖSYM temel soru kitapçıklarındaki soruların KÜNYESİ.

Tüketici: nos-academy (`assets/db/cikmis.json`, `pnpm sync-db`; tasarım
`nos-academy/docs/CIKMIS-SORULAR.md`). Çıktı `dist/cikmis.json`, release varlığı.

Kurallar (değişmez):
- Soru metni ve şık METİN olarak hiçbir yere girmez: telif ÖSYM'de, yazılı izin yok
  (ÖSYM 29.08.2013 duyurusu; 2026-YKS duyurusu). Etiket dosyalarında ve
  `cikmis.json`'da yalnız numara, sayfa, konu, cevap harfi ve bayraklar durur.
- İstisna, soru görselleri (proje sahibinin kararı, 2026-11-19; telif riski onda):
  `kirp` + `gorsel_paketle` → `dist/cikmis-gorsel.{bin,json}`, yalnız release
  varlığı olarak yayınlanır (`scripts/release.sh --cikmis`); repoya ve nos.db'ye girmez.
- PDF'ler, çıkarılan metin ve ham etiketleme yalnız yerelde, `pipeline/cikmis/yerel/` (gitignore);
  etiketleme için okunur, commit ve release edilmez.
- Cevap yalnız ÖSYM'nin kitapçık sonundaki anahtarından gelir; elle yazılmaz.
- Konu kimlikleri nos-academy `src/exams/yks/domain/konular.ts`'tendir;
  uygulamanın `pnpm test`i (scripts/test-cikmis.mjs) her kimliği denetler.
- Etiket: iki bağımsız etiketleme uyuşursa `cift-onay`; uyuşmazsa sayfa
  görselinden üçüncü karar `hakem`; insan kararı `insan`; kararsız `belirsiz`
  (yayımlanmaz).
- Literal yıl kodda yok; yıllar `belgeler.json` verisindedir.

Hat (nos-data kökünden):
  uv run --with pypdf python -m pipeline.cikmis.indir      # PDF -> pipeline/cikmis/yerel/pdf
  uv run --with pypdf python -m pipeline.cikmis.metin      # sayfa, anahtar, yerel metin -> pipeline/cikmis/yerel/metin
  # etiketleme: pipeline/cikmis/yerel/metin/<belge>.json okunur, pipeline/cikmis/etiket/<belge>-<test>.json yazılır
  uv run --with pypdf python -m pipeline.cikmis.denetle [--baglanti]
  uv run --with pypdf python -m pipeline.cikmis.paketle    # denetim -> dist/cikmis.json + sha256
  uv run python -m pipeline.cikmis.kirp                    # soru görselleri -> pipeline/cikmis/yerel/gorsel
  uv run python -m pipeline.cikmis.gorsel_paketle          # -> dist/cikmis-gorsel.{bin,json}

run.py ile birleştirilmedi: tam koşu bu hattı çağırmaz, release.sh dist/cikmis.json'ı
yüklemez (öneriler nos-academy docs/CIKMIS-SORULAR.md "Yayın adımları").
"""
