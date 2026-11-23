"""Kitapçıktan künye, cevap ve yerel metin: pipeline/cikmis/yerel/kpss/metin/<belge>.json.

KPSS yüzde 10 kitapçığı YKS'den farklıdır: sayfa düzeni özgün kitapçıkla aynıdır (iki sütun,
dikey ayırıcı), yayımlanmayan sorunun yalnız "N." etiketi basılıdır; yayımlanan sorunun altında
"DOĞRU CEVAP: X" satırı vardır. Yöntem:
- Test, sayfa üstbilgisinden ("2024-KPSS/GY", "2022-KPSS Ön Lisans/GK", "2024-KPSS OÖ/GK") bilinir.
- Her "DOĞRU CEVAP" satırı, aynı sütunda üstündeki en yakın "N." etiketinin sorusuna aittir.
- Soru metni: etiketin üstünden cevap satırına kadar olan sütun bölgesi (cevap satırı metne girmez).
Çıktı biçimi YKS `metin.py` ile aynıdır (`anahtar`, `sorular`); yalnız yayımlanan sorular bulunur.
Tutarlılık: test başına beklenen sayıda (YAYIMLANAN) tekil numara, numara <= basılı adet.
"""

from __future__ import annotations

import json
import re

import pdfplumber

from ..kirp import etiketler, icerik_alani
from .ortak import METIN_DIZINI, PDF_DIZINI, TESTLER, YAYIMLANAN, belgeler

CEVAP = re.compile(r"DOĞRU\s+CEVAP:\s*([A-E])\b")


def sayfa_testi(metin: str, testler) -> str | None:
    ust = "\n".join(metin.split("\n")[:8])
    for kod, _, desen in testler:
        if re.search(desen, ust):
            return kod
    return None


def isle(belge: dict) -> dict:
    testler = TESTLER[belge["oturum"]]
    adet = {kod: n for kod, n, _ in testler}
    anahtar: dict[str, dict[str, str]] = {kod: {} for kod, _, _ in testler}
    sorular: dict[str, list[dict]] = {kod: [] for kod, _, _ in testler}
    with pdfplumber.open(str(PDF_DIZINI / f"{belge['id']}.pdf")) as pdf:
        for i, sayfa in enumerate(pdf.pages):
            cevaplar = [s for s in sayfa.extract_text_lines() if CEVAP.search(s["text"])]
            if not cevaplar:
                continue
            kod = sayfa_testi(sayfa.extract_text() or "", testler)
            if kod is None:
                raise SystemExit(f"{belge['id']} s.{i + 1}: test üstbilgisi bulunamadı")
            ayirici, ust, alt = icerik_alani(sayfa)
            tum = etiketler(sayfa.extract_words(), ayirici, ust, alt)
            for c in cevaplar:
                sutun = 0 if c["x0"] < ayirici else 1
                ustte = [e for e in tum if e["sutun"] == sutun and e["top"] < c["top"]]
                if not ustte:
                    raise SystemExit(f"{belge['id']} s.{i + 1}: cevap satırının etiketi yok")
                e = max(ustte, key=lambda x: x["top"])
                x0, x1 = (36.0, ayirici - 3) if sutun == 0 else (ayirici + 3, 580.0)
                parca = sayfa.crop((x0, e["top"] - 4, x1, c["top"] - 1)).extract_text() or ""
                no = e["no"]
                if no in anahtar[kod]:
                    raise SystemExit(f"{belge['id']} {kod} #{no}: iki kez")
                anahtar[kod][str(no)] = CEVAP.search(c["text"]).group(1)
                sorular[kod].append({"no": no, "sayfa": i + 1, "bolundu": True, "metin": parca})
    for kod in sorular:
        sorular[kod].sort(key=lambda q: q["no"])
        nolar = [q["no"] for q in sorular[kod]]
        if len(nolar) != YAYIMLANAN[kod] or max(nolar, default=0) > adet[kod]:
            raise SystemExit(f"{belge['id']} {kod}: {len(nolar)} soru {nolar}, beklenen {YAYIMLANAN[kod]}")
    return {"belge": belge["id"], "anahtar": anahtar, "sorular": sorular}


def main() -> None:
    METIN_DIZINI.mkdir(parents=True, exist_ok=True)
    for b in belgeler():
        sonuc = isle(b)
        (METIN_DIZINI / f"{b['id']}.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
        ozet = ", ".join(f"{k}: {[q['no'] for q in v]}" for k, v in sonuc["sorular"].items())
        print(f"{b['id']}: {ozet}")


if __name__ == "__main__":
    main()
