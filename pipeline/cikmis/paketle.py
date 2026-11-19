"""dist/cikmis.json: uygulamanın okuduğu dizin (yalnız künye; soru metni yok).

Atomik: denetim geçerse dist/cikmis.json.swap yazılıp yerine taşınır (run.py'nin
dist.tmp/'ine dokunulmaz). `belirsiz`
etiketli soru yayımlanmaz. `veriSurumu` etiket dosyalarındaki en son etiketleme
tarihidir (aynı girdi aynı dosyayı üretir). Sonda uygulama pin'i için sha256 basılır.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

from .denetle import denetle
from .ortak import BELGE_ALANLARI, DIST, SORU_ALANLARI, belgeler, etiket_dosyalari, oku


def kur() -> dict:
    bler = belgeler()
    sira = {b["id"]: i for i, b in enumerate(bler)}
    sorular, tarihler = [], []
    for yol in etiket_dosyalari():
        e = oku(yol)
        tarihler.append(e["etiketleme"]["tarih"])
        for s in e["sorular"]:
            if s["etiket"] == "belirsiz":
                continue
            kayit = {
                "id": f"{e['belge']}-{e['test']}-{s['no']}",
                "belge": e["belge"],
                "test": e["test"],
                "no": s["no"],
                "sayfa": s["sayfa"],
                "konu": s["konu"],
                "altKonu": s.get("altKonu"),
                "ekKonu": s.get("ekKonu"),
                "cevap": s.get("cevap"),
                "iptal": bool(s.get("iptal")),
                "cevapDegisti": s.get("cevapDegisti"),
                "etiket": s["etiket"],
            }
            # Boyut için varsayılanlar yazılmaz (null, iptal false, etiket); uygulama eksik alanı varsayılanla okur.
            sorular.append({
                k: kayit[k] for k in SORU_ALANLARI
                if kayit[k] is not None and k != "etiket" and not (k == "iptal" and kayit[k] is False)
            })
    sorular.sort(key=lambda s: (sira[s["belge"]], s["test"], s["no"]))
    return {
        "surum": 1,
        "veriSurumu": max(tarihler) if tarihler else None,
        "belgeler": [{k: b.get(k) for k in BELGE_ALANLARI} for b in bler],
        "sorular": sorular,
    }


def main() -> None:
    hatalar = denetle()
    if hatalar:
        for h in hatalar:
            print("HATA", h)
        sys.exit("paketle: denetim geçmedi, dist/ değişmedi")
    veri = kur()
    icerik = (json.dumps(veri, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    DIST.mkdir(exist_ok=True)
    gecici = DIST / "cikmis.json.swap"
    gecici.write_bytes(icerik)
    os.replace(gecici, DIST / "cikmis.json")
    sha = hashlib.sha256(icerik).hexdigest()
    print(f"dist/cikmis.json: {len(veri['belgeler'])} belge, {len(veri['sorular'])} soru, {len(icerik)} bayt")
    print(f'nos-academy nos-data.json pin satırı: "sha256_cikmis": "{sha}"')


if __name__ == "__main__":
    main()
