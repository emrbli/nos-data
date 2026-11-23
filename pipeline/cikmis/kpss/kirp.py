"""KPSS soru görselleri: ÖSYM kitapçığından her yayımlanan sorunun kırpılması (YKS `kirp.py` yöntemi).

Aynı sayfa düzeni (iki sütun, ayırıcı, alt çizgi) ve aynı denetimler; farklar:
- Alt sınır sorunun "DOĞRU CEVAP: X" satırının ÜSTÜdür: cevap görsele GİRMEZ.
- Yalnız yayımlanan sorular kırpılır (metin.py çıktısı); yayımlanmayan sorunun boş etiketi sonraki
  etiket olarak bölgeyi sınırlar.
- Tam kapsamda (2019-2021) cevap satırı yoktur, alt sınır sonraki etikettir ve ortak parçalar ("N. ve M. soruları") YKS gibi üste eklenir; yüzde 10'da ortak parça eklenmez (ÖSYM o parçayı da yayımlamıyor).
Filigran soluklaştırma YKS ile aynı (`kirp.soluklastir`, standart eğri; `dolgu` eğrisi KPSS test kodlarına uygulanmaz).
Çıktı (yerel): yerel/kpss/gorsel/<soru kimliği>.webp ve yerel/kpss/kirp.json.
"""

from __future__ import annotations

import json
import sys

import pdfplumber
import pypdfium2 as pdfium

from ..kirp import (
    KENAR_PX, OLCEK, SAG_KENAR, SOL_KENAR, WEBP_KALITE, etiketler, icerik_alani, kirp_gorsel, ortak_parcalar, soluklastir, ust_uste,
)
from .metin import CEVAP
from .ortak import GORSEL_DIZINI, METIN_DIZINI, PDF_DIZINI, RAPOR, belgeler, oku


def kirp_sayfa(pdf_yolu, sayfa_no: int, istenen: list[int], cizim, cevapli: bool = True) -> dict[int, dict]:
    sonuc: dict[int, dict] = {}
    with pdfplumber.open(str(pdf_yolu)) as pdf:
        sayfa = pdf.pages[sayfa_no - 1]
        ayirici, ust, alt = icerik_alani(sayfa)
        kelimeler = sayfa.extract_words()
        tum = etiketler(kelimeler, ayirici, ust, alt)
        cevaplar = [s for s in sayfa.extract_text_lines() if CEVAP.search(s["text"])]
        cizimler = list(sayfa.rects) + list(sayfa.curves) + list(sayfa.lines) + list(sayfa.images)
    for no in istenen:
        adaylar = [e for e in tum if e["no"] == no]
        if len(adaylar) != 1:
            sonuc[no] = {"durum": f"etiket {len(adaylar)} kez bulundu"}
            continue
        e = adaylar[0]
        sonraki = sorted(x["top"] for x in tum if x["sutun"] == e["sutun"] and x["top"] > e["top"] + 1)
        x0, x1 = (SOL_KENAR, ayirici - 3) if e["sutun"] == 0 else (ayirici + 3, SAG_KENAR)
        y0, y1 = e["top"] - 4, (sonraki[0] - 6) if sonraki else alt - 3
        if cevapli:  # yüzde 10 kitapçık: "DOĞRU CEVAP" satırının üstünde kes
            benim = [c for c in cevaplar if (c["x0"] < ayirici) == (e["sutun"] == 0) and c["top"] > e["top"]]
            if not benim:
                sonuc[no] = {"durum": "cevap satırı bulunamadı"}
                continue
            y1 = min(y1, min(c["top"] for c in benim) - 2)
        icerik = [w for w in kelimeler if x0 <= w["x0"] and w["x1"] <= x1 + 2 and y0 <= w["top"] and w["bottom"] <= y1 + 2]
        if icerik:
            son = max(w["bottom"] for w in icerik)
            degisti = True
            while degisti:
                degisti = False
                for c in cizimler:
                    if x0 - 1 <= c["x0"] and c["x1"] <= x1 + 1 and y0 <= c["top"] <= son + 2 and c["bottom"] > son and c["bottom"] <= y1:
                        son, degisti = c["bottom"], True
            y1 = min(y1, son + 6)
        sutun_kelimeleri = [w for w in kelimeler if y0 <= w["top"] and w["bottom"] <= y1 + 2 and (w["x0"] < ayirici) == (e["sutun"] == 0)]
        tasan = [w["text"] for w in sutun_kelimeleri if w["x1"] > x1 + 0.5 or w["x0"] < x0 - 0.5]
        baska = [x["no"] for x in tum if x is not e and x0 - 2 <= x["x0"] <= x1 and y0 <= x["top"] <= y1]
        seceneklar = {w["text"][:2] for w in icerik if w["text"][:2] in ("A)", "B)", "C)", "D)", "E)")}
        hatalar = []
        if baska:
            hatalar.append(f"bölgede başka etiket {baska}")
        if tasan:
            hatalar.append(f"kenardan taşan {len(tasan)} kelime")
        if not {"A)", "E)"} <= seceneklar:
            hatalar.append(f"seçenek etiketi eksik ({''.join(sorted(seceneklar)) or 'yok'})")
        if any(CEVAP.search(w["text"]) or w["text"].startswith("DOĞRU") for w in icerik):
            hatalar.append("cevap satırı bölgeye girdi")
        if y1 - y0 < 40:  # tek satırlık kısa sorular ~44 pt
            hatalar.append(f"bölge çok kısa ({y1 - y0:.0f} pt)")
        kutu = [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)]
        if hatalar:
            sonuc[no] = {"durum": "; ".join(hatalar), "kutu": kutu}
            continue
        gri = kirp_gorsel(cizim, (x0, y0, x1, y1))
        if gri is None:
            sonuc[no] = {"durum": "boş bölge", "kutu": kutu}
            continue
        sonuc[no] = {"durum": "tamam", "kutu": kutu, "gorsel": gri}
    return sonuc


def main() -> None:
    GORSEL_DIZINI.mkdir(parents=True, exist_ok=True)
    tek = sys.argv[sys.argv.index("--belge") + 1] if "--belge" in sys.argv else None
    rapor: dict[str, dict] = json.loads(RAPOR.read_text(encoding="utf-8")) if tek and RAPOR.exists() else {}
    for b in belgeler():
        if tek and b["id"] != tek:
            continue
        for eski in GORSEL_DIZINI.glob(f"{b['id']}-*.webp"):
            eski.unlink()
        for k in [k for k in rapor if k.startswith(f"{b['id']}-")]:
            del rapor[k]
        metin = oku(METIN_DIZINI / f"{b['id']}.json")
        pdf_yolu = PDF_DIZINI / f"{b['id']}.pdf"
        belge_pdf = pdfium.PdfDocument(str(pdf_yolu))
        cizimler: dict = {}

        def cizim(n: int):
            if n not in cizimler:
                cizimler[n] = belge_pdf[n - 1].render(scale=OLCEK, grayscale=True).to_pil()
            return cizimler[n]

        for test in b["testler"]:
            sayfalar: dict[int, list[int]] = {}
            for q in metin["sorular"].get(test, []):
                sayfalar.setdefault(q["sayfa"], []).append(q["no"])
            tam = b["kapsam"] == "tam"
            # Ortak parçalar yalnız tam kapsamda ("N. ve M. soruları aşağıdaki parçaya göre"): YKS ile aynı.
            parcalar: dict[int, dict] = {}
            if tam:
                for sayfa_no, nolar in sayfalar.items():
                    for p in ortak_parcalar(pdf_yolu, sayfa_no):
                        a, b2 = p["aralik"]
                        if a not in nolar:
                            continue
                        g = kirp_gorsel(cizim(sayfa_no), p["kutu"])
                        for n in range(a, b2 + 1):
                            parcalar[n] = {**p, "gorsel": g}
            for sayfa_no, nolar in sorted(sayfalar.items()):
                for no, r in kirp_sayfa(pdf_yolu, sayfa_no, nolar, cizim(sayfa_no), cevapli=not tam).items():
                    kimlik = f"{b['id']}-{test}-{no}"
                    gorsel = r.pop("gorsel", None)
                    parca = parcalar.get(no)
                    if gorsel is not None and parca:
                        if parca["gorsel"] is None:
                            r["durum"] = "ortak parça boş"
                            gorsel = None
                        else:
                            gorsel = ust_uste(parca["gorsel"], gorsel)
                            r["ortak"] = [parca["aralik"][0], parca["aralik"][1], parca["sayfa"]]
                    if gorsel is not None:
                        dosya = GORSEL_DIZINI / f"{kimlik}.webp"
                        gorsel = soluklastir(gorsel, test)
                        gorsel.save(dosya, "WEBP", quality=WEBP_KALITE, method=6)
                        r.update({"genislik": gorsel.width, "yukseklik": gorsel.height, "bayt": dosya.stat().st_size})
                    rapor[kimlik] = {"sayfa": sayfa_no, **r}
        belge_pdf.close()
    RAPOR.write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    tamam = [k for k, r in rapor.items() if r["durum"] == "tamam"]
    toplam = sum(r.get("bayt", 0) for r in rapor.values())
    print(f"kirp: {len(tamam)}/{len(rapor)} soru kırpıldı, {toplam / 1024 / 1024:.2f} MB")
    for k, r in rapor.items():
        if r["durum"] != "tamam":
            print(f"  YAYIMLANMAZ {k}: {r['durum']}")


if __name__ == "__main__":
    main()
