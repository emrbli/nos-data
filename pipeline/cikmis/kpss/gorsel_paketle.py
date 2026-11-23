"""KPSS soru görselleri, ders başına paket: dist/cikmis-kpss-gorsel-<ders>.bin + dist/cikmis-kpss-gorsel.json.

YKS `gorsel_paketle.py` ile aynı biçim (surum 2 dizin, ofset/uzunluk/genişlik/yükseklik, sha256, atomik, dizin en son).
Fark yalnız adlar: `cikmis-kpss-gorsel*` (YKS `cikmis-gorsel*` ile çakışmaz; YKS paketlerine dokunulmaz).
Ders, konu kimliğinin önekidir (`kpss_tur.paragraf` -> `kpss_tur`). Yalnız `dist/cikmis-kpss.json`'da olan
ve `kirp.json`'da "tamam" olan sorular girer.
"""

from __future__ import annotations

import datetime
import hashlib
import json

from ..gorsel_paketle import yaz
from .ortak import DIST, DIZIN_ADI, GORSEL_DIZIN_ADI, GORSEL_DIZINI, GORSEL_PAKET_ON_EKI, RAPOR, oku


def main() -> None:
    cikmis = oku(DIST / DIZIN_ADI)
    rapor = oku(RAPOR)
    dersler: dict[str, list[dict]] = {}
    eksik = []
    for s in cikmis["sorular"]:
        r = rapor.get(s["id"])
        if not r or r["durum"] != "tamam":
            eksik.append(s["id"])
            continue
        dersler.setdefault(s["konu"].split(".")[0], []).append({**s, "_r": r})
    for eski in DIST.glob(f"{GORSEL_PAKET_ON_EKI}*.bin"):
        eski.unlink()
    paketler, toplam = {}, 0
    for ders, sorular in sorted(dersler.items()):
        parcalar, dizin, ofset = [], {}, 0
        for s in sorular:
            veri = (GORSEL_DIZINI / f"{s['id']}.webp").read_bytes()
            dizin[s["id"]] = [ofset, len(veri), s["_r"]["genislik"], s["_r"]["yukseklik"]]
            parcalar.append(veri)
            ofset += len(veri)
        paket = b"".join(parcalar)
        dosya = f"{GORSEL_PAKET_ON_EKI}{ders}.bin"
        yaz(dosya, paket)
        paketler[ders] = {"dosya": dosya, "sha256": hashlib.sha256(paket).hexdigest(), "bayt": len(paket), "sorular": dizin}
        toplam += len(paket)
        print(f"{dosya}: {len(dizin)} görsel, {len(paket) / 1024:.0f} KB")
    ozet = {"surum": 2, "veriSurumu": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M"), "paketler": paketler}
    yaz(GORSEL_DIZIN_ADI, (json.dumps(ozet, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
    print(f"dist/{GORSEL_DIZIN_ADI}: {len(paketler)} paket, toplam {toplam / 1024 / 1024:.2f} MB, dizin {(DIST / GORSEL_DIZIN_ADI).stat().st_size / 1024:.0f} KB")
    if eksik:
        print(f"görselsiz: {len(eksik)} soru: {', '.join(eksik[:10])}")


if __name__ == "__main__":
    main()
