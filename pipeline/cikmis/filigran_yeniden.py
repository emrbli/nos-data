"""Yeni ÖSYM filigranı (anotasyon, ton < 170) olan belgeleri yeniden kırpar; kesintiden devam eder.

  uv run python -m pipeline.cikmis.filigran_yeniden [--liste]

Etkilenen belge = PDF'indeki filigran tonu `kirp.YENI_FILIGRAN_ESIGI` altında olan (YKS ve KPSS). Her belge bitince
`yerel/filigran-ilerleme.json`'a (atomik) yazılır; yeniden başlatınca biten belgeler atlanır. Kırpma ilgili modülün
`--belge` seçeneğiyle koşar (YKS: pipeline.cikmis.kirp, KPSS: pipeline.cikmis.kpss.kirp). Sonra paket adımları ayrıca koşar.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pypdfium2 as pdfium

from .kirp import FiligranCizici
from .ortak import HAM, PDF_DIZINI, belgeler as yks_belgeler
from .kpss.ortak import belgeler as kpss_belgeler, gruplar

DURUM = HAM / "filigran-ilerleme.json"


def etkilenenler() -> dict[str, list[str]]:
    yks = [b["id"] for b in yks_belgeler() if FiligranCizici(pdfium.PdfDocument(str(PDF_DIZINI / f"{b['id']}.pdf"))).yeni]
    kpss = [b["id"] for b in kpss_belgeler() if any(FiligranCizici(pdfium.PdfDocument(str(f))).yeni for f, _ in gruplar(b))]
    return {"yks": yks, "kpss": kpss}


def main() -> None:
    liste = etkilenenler()
    if "--liste" in sys.argv:
        print(json.dumps(liste, ensure_ascii=False))
        return
    biten = json.loads(DURUM.read_text(encoding="utf-8")) if DURUM.exists() else {"yks": [], "kpss": []}
    for aile, modul in (("yks", "pipeline.cikmis.kirp"), ("kpss", "pipeline.cikmis.kpss.kirp")):
        for b in liste[aile]:
            if b in biten[aile]:
                print(f"{aile} {b}: bitti, atlandı")
                continue
            r = subprocess.run([sys.executable, "-m", modul, "--belge", b], capture_output=True, text=True)
            print(f"{aile} {b}: {(r.stdout.strip().splitlines() or [''])[0]}", flush=True)
            if r.returncode != 0:
                raise SystemExit(f"{aile} {b}: kırpma hata verdi\n{r.stderr[-400:]}")
            biten[aile].append(b)
            gecici = DURUM.with_suffix(".swap")
            gecici.write_text(json.dumps(biten, indent=1), encoding="utf-8")
            gecici.replace(DURUM)


if __name__ == "__main__":
    main()
