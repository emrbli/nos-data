"""Soru görselleri: ÖSYM kitapçığından her sorunun (kök ve şıklar) kırpılması.

Kullanıcı kararı (2026-11-19): sorular uygulamada görsel olarak gösterilebilir; telif
riski kararı kullanıcının. Görseller nos.db'ye ve uygulama paketine girmez; release
varlığı olarak iner (`gorsel_paketle.py`).

Yöntem (2019-2026 TYT sayfa düzeni: iki sütun, sütun ayırıcı dikey çizgi, altta yatay
çizgi; ilk test sayfasında üstte yönerge kutusu):
- İçerik alanı: dikey ayırıcının üst ucundan alt yatay çizgiye kadar. Sütunlar sol
  kenar 36 pt ile ayırıcı, ayırıcı ile 580 pt (sağ sütunun metni çizginin ucunu aşabiliyor).
- Soru etiketi: metni "N." olan, sütunun başına yaslı kelime (sol sütunda kenardan 0-10 pt,
  sağ sütunda ayırıcıdan 15-30 pt). Soru içi numaralı listeler ve yönerge bu banda düşmediği için karışmaz.
- Bölge: etiketin üstünden aynı sütundaki bir sonraki etiketin üstüne ya da içerik
  alanının altına kadar; alt sınır sorunun son kelimesi ve ona değen şekillerle daralır
  (sayfa süsleri girmez). 3x ölçekte çizilip kenarlardaki boşluk kırpılır.
- Denetim (geçmeyen yayımlanmaz, `kirp.json`'da nedeniyle durur):
  * etiket bulunmalı ve tek olmalı, sayfası etiket dosyasındakiyle aynı olmalı;
  * bölgede başka soru etiketi olmamalı (iki soru içeren kırpma);
  * sütundaki hiçbir kelime kutunun sağından ya da solundan taşmamalı (kesik kenar);
  * bölgede "A)" ve "E)" seçenek etiketleri bulunmalı (şıkları kesilmiş kırpma);
  * bölge yüksekliği en az 60 pt olmalı.

Çıktı (yerel, gitignore): pipeline/cikmis/yerel/gorsel/<soru kimliği>.webp ve
pipeline/cikmis/yerel/kirp.json (denetim raporu).
"""

from __future__ import annotations

import json
import re

import pdfplumber
import pypdfium2 as pdfium
from PIL import Image, ImageOps

from .ortak import HAM, PDF_DIZINI, belgeler, etiket_dosyalari, oku

GORSEL_DIZINI = HAM / "gorsel"
RAPOR = HAM / "kirp.json"
OLCEK = 3  # 216 dpi
# Sağ sütunun metni alt çizginin ucunu (553 pt) ~10 pt aşabiliyor; kırpma sınırı sayfa kenarına yakın.
SOL_KENAR, SAG_KENAR = 36.0, 580.0
SOL_CIZGI = 42.0  # sol sütun etiketlerinin hizalandığı kenar çizgisi
# Sütun başına göre etiketin x0 aralığı: sol sütun kenara, sağ sütun ayırıcıdan ~20 pt içeride.
ETIKET_BANDI = ((0.0, 10.0), (15.0, 30.0))
ETIKET = re.compile(r"^(\d{1,2})\.$")
KENAR_PX = 12
WEBP_KALITE = 60


def icerik_alani(sayfa) -> tuple[float, float, float]:
    """(ayırıcı x, içerik üstü, içerik altı)."""
    dikey = [l for l in sayfa.lines if abs(l["x0"] - l["x1"]) < 2 and (l["bottom"] - l["top"]) > 300]
    yatay = [l for l in sayfa.lines if abs(l["top"] - l["bottom"]) < 2 and (l["x1"] - l["x0"]) > 400]
    if not dikey or not yatay:
        raise ValueError("sayfa çizgileri bulunamadı")
    ayirici = dikey[0]
    alt = min(l["top"] for l in yatay if l["top"] > ayirici["top"] + 100)
    return ayirici["x0"], ayirici["top"], alt


def etiketler(kelimeler, ayirici: float, ust: float, alt: float) -> list[dict]:
    sonuc = []
    for w in kelimeler:
        m = ETIKET.match(w["text"])
        if not m or not (ust - 2 <= w["top"] <= alt):
            continue
        for sutun, bas in ((0, SOL_CIZGI), (1, ayirici)):
            if ETIKET_BANDI[sutun][0] <= w["x0"] - bas <= ETIKET_BANDI[sutun][1]:
                sonuc.append({"no": int(m.group(1)), "sutun": sutun, "top": w["top"], "x0": w["x0"]})
    return sonuc


def kirp_sayfa(pdf_yolu, sayfa_no: int, istenen: list[int], cizim) -> dict[int, dict]:
    """Bir sayfadaki istenen soruların bölgesi, denetimi ve görseli."""
    sonuc: dict[int, dict] = {}
    with pdfplumber.open(str(pdf_yolu)) as pdf:
        sayfa = pdf.pages[sayfa_no - 1]
        ayirici, ust, alt = icerik_alani(sayfa)
        kelimeler = sayfa.extract_words()
        tum = etiketler(kelimeler, ayirici, ust, alt)
        cizimler = list(sayfa.rects) + list(sayfa.curves) + list(sayfa.lines) + list(sayfa.images)
    for no in istenen:
        adaylar = [e for e in tum if e["no"] == no]
        if len(adaylar) != 1:
            sonuc[no] = {"durum": f"etiket {len(adaylar)} kez bulundu"}
            continue
        e = adaylar[0]
        sonraki = sorted(x["top"] for x in tum if x["sutun"] == e["sutun"] and x["top"] > e["top"] + 1)
        x0, x1 = (SOL_KENAR, ayirici - 3) if e["sutun"] == 0 else (ayirici + 3, SAG_KENAR)
        y0, y1 = e["top"] - 4, (sonraki[0] - 6 if sonraki else alt - 3)
        icerik = [w for w in kelimeler if x0 <= w["x0"] and w["x1"] <= x1 + 2 and y0 <= w["top"] and w["bottom"] <= y1 + 2]
        # Alt sınır sorunun kendi içeriğidir: son kelimenin altı, ona değen şekiller kadar
        # uzar. Sayfa süsleri (köşedeki gri şekil) sorudan sonra başladığı için girmez.
        if icerik:
            son = max(w["bottom"] for w in icerik)
            degisti = True
            while degisti:
                degisti = False
                for c in cizimler:
                    if x0 - 1 <= c["x0"] and c["x1"] <= x1 + 1 and y0 <= c["top"] <= son + 2 and c["bottom"] > son and c["bottom"] <= y1:
                        son, degisti = c["bottom"], True
            y1 = min(y1, son + 6)
        # Kesik kenar denetimi: sütundaki satırlardan hiçbiri kırpma kutusunun dışına taşmamalı.
        sutun_kelimeleri = [
            w for w in kelimeler
            if y0 <= w["top"] and w["bottom"] <= y1 + 2 and (w["x0"] < ayirici) == (e["sutun"] == 0)
        ]
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
        if y1 - y0 < 60:
            hatalar.append(f"bölge çok kısa ({y1 - y0:.0f} pt)")
        kutu = [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)]
        if hatalar:
            sonuc[no] = {"durum": "; ".join(hatalar), "kutu": kutu}
            continue
        gorsel = cizim.crop((int(x0 * OLCEK), int(y0 * OLCEK), int(x1 * OLCEK), int(y1 * OLCEK)))
        gri = gorsel.convert("L")
        sinir = ImageOps.invert(gri).point(lambda v: 255 if v > 24 else 0).getbbox()
        if not sinir:
            sonuc[no] = {"durum": "boş bölge", "kutu": kutu}
            continue
        l, t, r, b = sinir
        gri = gri.crop((max(0, l - KENAR_PX), max(0, t - KENAR_PX), min(gri.width, r + KENAR_PX), min(gri.height, b + KENAR_PX)))
        sonuc[no] = {"durum": "tamam", "kutu": kutu, "gorsel": gri}
    return sonuc


def main() -> None:
    GORSEL_DIZINI.mkdir(parents=True, exist_ok=True)
    for eski in GORSEL_DIZINI.glob("*.webp"):
        eski.unlink()
    bler = {b["id"]: b for b in belgeler()}
    rapor: dict[str, dict] = {}
    for yol in etiket_dosyalari():
        e = oku(yol)
        belge = bler[e["belge"]]
        pdf_yolu = PDF_DIZINI / f"{belge['id']}.pdf"
        sayfalar: dict[int, list[int]] = {}
        for s in e["sorular"]:
            sayfalar.setdefault(s["sayfa"], []).append(s["no"])
        belge_pdf = pdfium.PdfDocument(str(pdf_yolu))
        for sayfa_no, nolar in sorted(sayfalar.items()):
            cizim = belge_pdf[sayfa_no - 1].render(scale=OLCEK, grayscale=True).to_pil()
            for no, r in kirp_sayfa(pdf_yolu, sayfa_no, nolar, cizim).items():
                kimlik = f"{e['belge']}-{e['test']}-{no}"
                gorsel = r.pop("gorsel", None)
                if gorsel is not None:
                    dosya = GORSEL_DIZINI / f"{kimlik}.webp"
                    gorsel.save(dosya, "WEBP", quality=WEBP_KALITE, method=6)
                    r.update({"genislik": gorsel.width, "yukseklik": gorsel.height, "bayt": dosya.stat().st_size})
                rapor[kimlik] = {"sayfa": sayfa_no, **r}
        belge_pdf.close()
    RAPOR.write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    tamam = [k for k, r in rapor.items() if r["durum"] == "tamam"]
    toplam = sum(r.get("bayt", 0) for r in rapor.values())
    print(f"kirp: {len(tamam)}/{len(rapor)} soru kırpıldı, {toplam / 1024:.0f} KB")
    for k, r in rapor.items():
        if r["durum"] != "tamam":
            print(f"  YAYIMLANMAZ {k}: {r['durum']}")


if __name__ == "__main__":
    main()
