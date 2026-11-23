"""KPSS kitapçıklarını pipeline/cikmis/yerel/kpss/pdf/<belge>.pdf'e indirir (var olanı atlar).

YKS `indir.getir` ile aynı: güvenlik duvarı 200 koduyla HTML döndürürse `%PDF` imzası aranır.
"""

from __future__ import annotations

import time

from ..indir import getir
from .ortak import PDF_DIZINI, belgeler


def main() -> None:
    PDF_DIZINI.mkdir(parents=True, exist_ok=True)
    for b in belgeler():
        hedef = PDF_DIZINI / f"{b['id']}.pdf"
        if hedef.exists() and hedef.read_bytes()[:5] == b"%PDF-":
            print(f"{b['id']}: var, atlandı")
            continue
        hedef.write_bytes(getir(b["kitapcikUrl"]))
        print(f"{b['id']}: indirildi ({hedef.stat().st_size} bayt)")
        time.sleep(1.5)


if __name__ == "__main__":
    main()
