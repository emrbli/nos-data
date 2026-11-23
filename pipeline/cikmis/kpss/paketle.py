"""dist/cikmis-kpss.json: uygulamanın okuyacağı KPSS künye dizini (YKS `paketle.py` ile aynı biçim; soru metni yok).

Atomik (`.swap` -> yerine taşı); denetim geçmezse dist/ değişmez. `belirsiz` etiketli soru yayımlanmaz.
`veriSurumu` paketleme anıdır ("2026-11-24T01:30"), YKS `cozum_ekle` ile aynı kural. Sonda pin için sha256.
KPSS'de MEB çözüm bağlantısı olmadığı için `cozumUrl` yalnız belge düzeyinde (null) ve soruda yoktur.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys

from .denetle import denetle
from .ortak import BELGE_ALANLARI, DIST, DIZIN_ADI, SORU_ALANLARI, belgeler, etiket_dosyalari, oku


def kur() -> dict:
    bler = belgeler()
    sira = {b["id"]: i for i, b in enumerate(bler)}
    sorular = []
    for yol in etiket_dosyalari():
        e = oku(yol)
        for s in e["sorular"]:
            if s["etiket"] == "belirsiz":
                continue
            kayit = {
                "id": f"{e['belge']}-{e['test']}-{s['no']}", "belge": e["belge"], "test": e["test"], "no": s["no"],
                "sayfa": s["sayfa"], "konu": s["konu"], "altKonu": s.get("altKonu"), "ekKonu": s.get("ekKonu"),
                "cevap": s.get("cevap"), "iptal": bool(s.get("iptal")), "cevapDegisti": s.get("cevapDegisti"), "etiket": s["etiket"],
            }
            # YKS ile aynı: null alanlar, iptal false ve etiket türü yazılmaz (boyut).
            sorular.append({
                k: kayit[k] for k in SORU_ALANLARI
                if kayit[k] is not None and k != "etiket" and not (k == "iptal" and kayit[k] is False)
            })
    sorular.sort(key=lambda s: (sira[s["belge"]], s["test"], s["no"]))
    return {
        "surum": 1,
        "veriSurumu": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M"),
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
    gecici = DIST / f"{DIZIN_ADI}.swap"
    gecici.write_bytes(icerik)
    os.replace(gecici, DIST / DIZIN_ADI)
    print(f"dist/{DIZIN_ADI}: {len(veri['belgeler'])} belge, {len(veri['sorular'])} soru, {len(icerik)} bayt")
    print(f'nos-academy nos-data.json pin satırı: "sha256_cikmis_kpss": "{hashlib.sha256(icerik).hexdigest()}"')


if __name__ == "__main__":
    main()
