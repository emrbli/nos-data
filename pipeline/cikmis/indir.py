"""ÖSYM kitapçıklarını pipeline/cikmis/yerel/pdf/<belge>.pdf'e indirir (var olanı atlar).

dokuman.osym.gov.tr güvenlik duvarı bazı isteklere 200 koduyla "Erişim Engellendi"
HTML'i döndürür; `%PDF` imzası yoksa bekleyip yeniden denenir. Tarayıcı
User-Agent'ı verilmez (nosakademi-web scripts/cikmis-dizin/osym-getir.ts deneyimi).
"""

from __future__ import annotations

import time

import httpx

from .ortak import PDF_DIZINI, belgeler


def getir(url: str, deneme: int = 3) -> bytes:
    son = ""
    for k in range(deneme):
        try:
            yanit = httpx.get(url, timeout=120, follow_redirects=True)
            if yanit.status_code == 200 and yanit.content[:5] == b"%PDF-":
                return yanit.content
            son = f"{yanit.status_code}, PDF değil ({len(yanit.content)} bayt)"
        except httpx.HTTPError as e:
            son = f"ağ hatası: {e}"
        if k < deneme - 1:
            time.sleep(30)
    raise SystemExit(f"{url}: {son}")


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
