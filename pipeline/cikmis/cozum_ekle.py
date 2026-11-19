"""dist/cikmis.json'a soru başına MEB çözüm bağlantısı (`cozumUrl`) ekler.

Kaynak: `meb.py`'nin yazdığı pipeline/cikmis/cozum/<belge>-<test>.json (commit edilir).
`paketle.py`'den SONRA koşulur (paketle dosyayı baştan yazar; bu adım alanı ekler).
Eşleşmeyen soruda alan yoktur; uygulama belge düzeyindeki `cozumUrl`'e düşer.
Atomik: `.swap` dosyasına yazılıp yerine taşınır. Sonda pin için sha256 basılır.

  uv run --with pypdf python -m pipeline.cikmis.paketle && uv run python -m pipeline.cikmis.cozum_ekle

Not: kalıcı yeri `paketle.py` ve `ortak.SORU_ALANLARI`; bu adım o dosyalara dokunmadan
eklendi (nos-data'da yalnız yeni dosya kuralı, 2026-11-19).
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os

from .meb import COZUM_DIZINI
from .ortak import DIST


def main() -> None:
    yol = DIST / "cikmis.json"
    veri = json.loads(yol.read_text(encoding="utf-8"))
    baglantilar: dict[str, str] = {}
    for dosya in sorted(COZUM_DIZINI.glob("*.json")):
        on_ek = dosya.stem  # 2025-tyt-mat
        cozum = json.loads(dosya.read_text(encoding="utf-8"))
        for no, kayit in cozum["sorular"].items():
            if str(kayit.get("url", "")).startswith("https://"):
                baglantilar[f"{on_ek}-{no}"] = kayit["url"]
    eklenen = 0
    for s in veri["sorular"]:
        s.pop("cozumUrl", None)
        url = baglantilar.get(s["id"])
        if url:
            s["cozumUrl"] = url
            eklenen += 1
    # Uygulamanın uzak güncellemesi yalnız daha yeni `veriSurumu`'nu alır (dizgi karşılaştırması).
    # Aynı gün birden çok yayım olabildiği için sürüm paketleme anıdır: "2026-11-19T17:20"
    # ("+cozum" ekli eski biçimden ve gün biçiminden büyüktür).
    veri["veriSurumu"] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M")
    icerik = (json.dumps(veri, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    gecici = DIST / "cikmis.json.swap"
    gecici.write_bytes(icerik)
    os.replace(gecici, yol)
    print(f"dist/cikmis.json: {eklenen}/{len(veri['sorular'])} soruya çözüm bağlantısı, {len(icerik)} bayt")
    print(f'nos-academy nos-data.json pin satırı: "sha256_cikmis": "{hashlib.sha256(icerik).hexdigest()}"')


if __name__ == "__main__":
    main()
