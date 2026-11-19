"""Soru görselleri, ders başına paket: dist/cikmis-gorsel-<ders>.bin + dist/cikmis-gorsel.json.

- `cikmis-gorsel-<ders>.bin` (ör. `cikmis-gorsel-tyt_mat.bin`): o dersin webp'leri uç uca
  (başlık yok). Ders, sorunun konu kimliğinin önekidir (`tyt_mat.problem` -> `tyt_mat`).
- `cikmis-gorsel.json` (dizin, surum 2):
  {"surum": 2, "veriSurumu", "paketler": {"<ders>": {"dosya", "sha256", "bayt",
   "sorular": {"<soru kimliği>": [ofset, uzunluk, genişlik, yükseklik]}}}}
  Uygulama modüle ilk girişte bu küçük dizini, öğrenci bir derse girince o dersin paketini
  indirir; paketin sha256'sı dizindekiyle aynı değilse reddeder ve sonra yeniden dener.
- Yalnız `dist/cikmis.json`'da yayımlanan ve `kirp.json`'da "tamam" olan sorular girer;
  görseli olmayan soru uygulamada künye ve bağlantı görünümünde kalır.
- Atomik: her dosya `.swap`'a yazılıp yerine taşınır; dizin EN SON yazılır.

Release varlık adları: `cikmis-gorsel.json` ve her ders için `cikmis-gorsel-<ders>.bin`.
"""

from __future__ import annotations

import hashlib
import json
import os

from .kirp import GORSEL_DIZINI, RAPOR
from .ortak import DIST, oku


def yaz(ad: str, icerik: bytes) -> None:
    gecici = DIST / f"{ad}.swap"
    gecici.write_bytes(icerik)
    os.replace(gecici, DIST / ad)


def main() -> None:
    cikmis = oku(DIST / "cikmis.json")
    rapor = oku(RAPOR)
    dersler: dict[str, list[dict]] = {}
    eksik = []
    for s in cikmis["sorular"]:
        r = rapor.get(s["id"])
        if not r or r["durum"] != "tamam":
            eksik.append(s["id"])
            continue
        dersler.setdefault(s["konu"].split(".")[0], []).append({**s, "_r": r})
    for eski in DIST.glob("cikmis-gorsel-*.bin"):
        eski.unlink()
    paketler = {}
    toplam = 0
    for ders, sorular in sorted(dersler.items()):
        parcalar, dizin, ofset = [], {}, 0
        for s in sorular:
            veri = (GORSEL_DIZINI / f"{s['id']}.webp").read_bytes()
            dizin[s["id"]] = [ofset, len(veri), s["_r"]["genislik"], s["_r"]["yukseklik"]]
            parcalar.append(veri)
            ofset += len(veri)
        paket = b"".join(parcalar)
        dosya = f"cikmis-gorsel-{ders}.bin"
        yaz(dosya, paket)
        paketler[ders] = {"dosya": dosya, "sha256": hashlib.sha256(paket).hexdigest(), "bayt": len(paket), "sorular": dizin}
        toplam += len(paket)
        print(f"{dosya}: {len(dizin)} görsel, {len(paket) / 1024 / 1024:.1f} MB")
    ozet = {"surum": 2, "veriSurumu": cikmis["veriSurumu"], "paketler": paketler}
    yaz("cikmis-gorsel.json", (json.dumps(ozet, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
    print(f"dist/cikmis-gorsel.json: {len(paketler)} paket, toplam {toplam / 1024 / 1024:.1f} MB, dizin {(DIST / 'cikmis-gorsel.json').stat().st_size / 1024:.0f} KB")
    if eksik:
        print(f"görselsiz (künye görünümünde kalır): {len(eksik)} soru: {', '.join(eksik[:10])}")


if __name__ == "__main__":
    main()
