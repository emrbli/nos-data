"""Kitapçıktan künye, cevap ve yerel metin: pipeline/cikmis/yerel/kpss/metin/<belge>.json.

KPSS yüzde 10 kitapçığı YKS'den farklıdır: sayfa düzeni özgün kitapçıkla aynıdır (iki sütun,
dikey ayırıcı), yayımlanmayan sorunun yalnız "N." etiketi basılıdır; yayımlanan sorunun altında
"DOĞRU CEVAP: X" satırı vardır. Yöntem:
- Test, sayfa üstbilgisinden ("2024-KPSS/GY", "2022-KPSS Ön Lisans/GK", "2024-KPSS OÖ/GK") bilinir.
- Her "DOĞRU CEVAP" satırı, aynı sütunda üstündeki en yakın "N." etiketinin sorusuna aittir.
- Soru metni: etiketin üstünden cevap satırına kadar olan sütun bölgesi (cevap satırı metne girmez).
Çıktı biçimi YKS `metin.py` ile aynıdır (`anahtar`, `sorular`); yalnız yayımlanan sorular bulunur.
Tutarlılık: test başına beklenen sayıda (YAYIMLANAN) tekil numara, numara <= basılı adet.

Tam kapsam (2019-2021, `kapsam: tam`): sayfada cevap satırı yoktur. Tüm sorular yayımlıdır; her "N."
etiketinin bölgesi bir sonraki etiketin (aynı sütun) üstüne ya da içerik alanının altına kadardır. Cevap,
son sayfadaki anahtar tablosundandır (GY/GK için dört sütun: GY 1-47, GY 48-60, GK 1-47, GK 48-60; EB için iki).
Anahtarda İPTAL yoktur; ÖSYM'nin sonradan yaptığı değişiklikler (varsa) kitapçık anahtarında görünmez.
"""

from __future__ import annotations

import json
import re

import pdfplumber

from ..kirp import etiketler, icerik_alani
from .ortak import METIN_DIZINI, PDF_DIZINI, TESTLER, YAYIMLANAN, belgeler, beklenen

CEVAP = re.compile(r"DOĞRU\s+CEVAP:\s*([A-E])\b")


def sayfa_testi(metin: str, testler) -> str | None:
    ust = "\n".join(metin.split("\n")[:8])
    for kod, _, desen in testler:
        if re.search(desen, ust):
            return kod
    return None


def tam_anahtar(sayfa, testler) -> dict[str, dict[str, str]]:
    """Son sayfa anahtar tablosu: "N." sözcüğünü izleyen harf; sütun, N. sözcüklerin x kümesinden."""
    kel = sayfa.extract_words()
    sayilar = sorted((w for w in kel if re.fullmatch(r"\d{1,2}\.", w["text"])), key=lambda w: w["x0"])
    kumeler: list[list[dict]] = []
    for w in sayilar:
        if kumeler and w["x0"] - kumeler[-1][-1]["x0"] < 40:
            kumeler[-1].append(w)
        else:
            kumeler.append([w])
    sutun_sayisi = 4 if len(testler) == 2 else 2
    if len(kumeler) != sutun_sayisi:
        raise SystemExit(f"anahtar sayfasında {len(kumeler)} sütun bulundu, beklenen {sutun_sayisi}")
    sonuc: dict[str, dict[str, str]] = {kod: {} for kod, _, _ in testler}
    for i, kume in enumerate(kumeler):
        kod = testler[i // 2][0] if len(testler) == 2 else testler[0][0]
        for w in kume:
            ayni = [x for x in kel if abs(x["top"] - w["top"]) < 3 and x["x0"] > w["x1"] and re.fullmatch(r"[A-E]", x["text"])]
            if not ayni:
                raise SystemExit(f"anahtar: {w['text']} için harf yok")
            h = min(ayni, key=lambda x: x["x0"])["text"]
            n = w["text"].rstrip(".")
            if n in sonuc[kod]:
                raise SystemExit(f"anahtar: {kod} {n} iki kez")
            sonuc[kod][n] = h
    return sonuc


def tam_isle(belge: dict) -> dict:
    testler = TESTLER[belge["oturum"]]
    adet = {kod: n for kod, n, _ in testler}
    sorular: dict[str, list[dict]] = {kod: [] for kod, _, _ in testler}
    with pdfplumber.open(str(PDF_DIZINI / f"{belge['id']}.pdf")) as pdf:
        anahtar = tam_anahtar(pdf.pages[-1], testler)
        for i, sayfa in enumerate(pdf.pages[:-1]):
            try:
                ayirici, ust, alt = icerik_alani(sayfa)
            except ValueError:
                continue
            kod = sayfa_testi(sayfa.extract_text() or "", testler)
            tum = etiketler(sayfa.extract_words(), ayirici, ust, alt)
            if tum and kod is None:
                raise SystemExit(f"{belge['id']} s.{i + 1}: test üstbilgisi bulunamadı")
            for e in tum:
                sonraki = sorted(x["top"] for x in tum if x["sutun"] == e["sutun"] and x["top"] > e["top"] + 1)
                x0, x1 = (36.0, ayirici - 3) if e["sutun"] == 0 else (ayirici + 3, 580.0)
                y1 = (sonraki[0] - 2) if sonraki else alt - 2
                parca = sayfa.crop((x0, e["top"] - 4, x1, y1)).extract_text() or ""
                sorular[kod].append({"no": e["no"], "sayfa": i + 1, "bolundu": True, "metin": parca})
    for kod in sorular:
        sorular[kod].sort(key=lambda q: q["no"])
        nolar = [q["no"] for q in sorular[kod]]
        if nolar != list(range(1, adet[kod] + 1)):
            raise SystemExit(f"{belge['id']} {kod}: numaralar 1..{adet[kod]} değil: {nolar}")
        if sorted(int(n) for n in anahtar[kod]) != nolar:
            raise SystemExit(f"{belge['id']} {kod}: anahtar numaraları sorularla uyuşmuyor")
    return {"belge": belge["id"], "anahtar": anahtar, "sorular": sorular}


def isle(belge: dict) -> dict:
    if belge["kapsam"] == "tam":
        return tam_isle(belge)
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
