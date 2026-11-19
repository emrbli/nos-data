"""Soru görsellerinin tek pakette toplanması: dist/cikmis-gorsel.bin + dist/cikmis-gorsel.json.

- `.bin`: `kirp.py`'nin denetimden geçirdiği webp dosyaları uç uca (başlık yok).
- `.json` (dizin): {"surum": 1, "veriSurumu", "sha256", "bayt", "sorular": {"<soru kimliği>":
  [ofset, uzunluk, genişlik, yükseklik]}}. Uygulama önce bu küçük dosyayı indirir;
  `sha256` önbellektekinden farklıysa `.bin`'i indirip doğrular ve parçalara ayırır.
- Yalnız `dist/cikmis.json`'da yayımlanan ve `kirp.json`'da "tamam" olan sorular girer;
  görseli olmayan soru uygulamada künye ve bağlantı görünümünde kalır.
- Atomik: `.swap` dosyalarına yazılıp yerine taşınır.
"""

from __future__ import annotations

import hashlib
import json
import os

from .kirp import GORSEL_DIZINI, RAPOR
from .ortak import DIST, oku


def main() -> None:
    cikmis = oku(DIST / "cikmis.json")
    rapor = oku(RAPOR)
    parcalar, dizin, ofset = [], {}, 0
    eksik = []
    for s in cikmis["sorular"]:
        r = rapor.get(s["id"])
        if not r or r["durum"] != "tamam":
            eksik.append(s["id"])
            continue
        veri = (GORSEL_DIZINI / f"{s['id']}.webp").read_bytes()
        dizin[s["id"]] = [ofset, len(veri), r["genislik"], r["yukseklik"]]
        parcalar.append(veri)
        ofset += len(veri)
    paket = b"".join(parcalar)
    sha = hashlib.sha256(paket).hexdigest()
    ozet = {"surum": 1, "veriSurumu": cikmis["veriSurumu"], "sha256": sha, "bayt": len(paket), "sorular": dizin}
    for ad, icerik in (
        ("cikmis-gorsel.bin", paket),
        ("cikmis-gorsel.json", (json.dumps(ozet, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")),
    ):
        gecici = DIST / f"{ad}.swap"
        gecici.write_bytes(icerik)
        os.replace(gecici, DIST / ad)
    print(f"dist/cikmis-gorsel.bin: {len(dizin)} görsel, {len(paket) / 1024 / 1024:.1f} MB, sha256 {sha[:16]}…")
    print(f"dist/cikmis-gorsel.json: {(DIST / 'cikmis-gorsel.json').stat().st_size / 1024:.0f} KB")
    if eksik:
        print(f"görselsiz (künye görünümünde kalır): {len(eksik)} soru: {', '.join(eksik[:10])}")


if __name__ == "__main__":
    main()
