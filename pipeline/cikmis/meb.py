"""MEB çözüm videoları: ÖSYM sorusu başına çözüm bağlantısı.

Kaynak: MEB Ortaöğretim Genel Müdürlüğü "YKS Çıkmış Sorular - 2018-2026" kitapları (OGM
Materyal, ogmmateryal.eba.gov.tr/yks-cikmis-soru-kitaplari): TYT, Din TYT, AYT Sayısal,
Eşit Ağırlık, Sözel, Din Sözel ve YDT. Sorular konu bazında; her sorunun altında kaynak
etiketi ("2025-TYT") ve yanında çözüm videosuna giden QR. Çoğu kitapta QR'ın adresi PDF
bağlantısı olarak da durur (https://meb.ai/<kod>); AYT Sayısal kitabında bağlantı yok, QR
sayfa çizilip OpenCV ile çözülür. Kısa adres mebi.eba.gov.tr/question/show-answer/<kimlik>
üzerinden ogm-large-cdn'deki mp4'e yönlenir; giriş istemez (2026-11-19'da denendi).

Kitap ÖSYM numarasını yazmaz; eşleme içerikle yapılır:
- Kitaptan: her sorunun bölgesi (numara etiketinden kaynak etiketine, aynı sütun), metni,
  yılı, bölümü (ders), kitap numarası, kitabın cevap anahtarındaki harfi ve bağlantısı.
- ÖSYM tarafı: kırpma kutusundaki (`kirp.json`) kelimeler, aynı yıl ve oturumun bütün testleri.
- Harf biliniyorsa aynı cevap harfi şart; benzerlik (sözcük kümesi ve karakter dizisi)
  ESIK_HARFLI, harf yoksa daha sıkı ESIK_HARFSIZ; bire bir açgözlü atama. Aynı soru iki
  kitapta varsa (AYT Matematik: Sayısal ve Eşit Ağırlık) yüksek skorlu bağlantı kalır.
- Eşleşmeyen soru bağlantısız kalır (uygulamada kitap düzeyindeki bağlantı yedektir).

Çıktı (commit edilir): pipeline/cikmis/cozum/<belge>-<test>.json
  {"kaynak", "tarih", "sorular": {"<no>": {"url", "skor", "kitap", "kitapNo"}}}
Yerel: pipeline/cikmis/yerel/meb/ (kitap PDF'leri, eşleme raporu).

  uv run --with opencv-python-headless python -m pipeline.cikmis.meb
"""

from __future__ import annotations

import datetime
import difflib
import json
import re
import sys

import httpx
import pdfplumber

from .ortak import BURASI, HAM, METIN_DIZINI, PDF_DIZINI, belgeler

KITAP_SAYFASI = "https://ogmmateryal.eba.gov.tr/yks-cikmis-soru-kitaplari"
KITAP_TABANI = "https://ogm-small-cdn.eba.gov.tr/ogm-test-images"
# (dosya, CDN klasörü, oturum): OGM Materyal "YKS Çıkmış Soru Kitapları" (2018-2026).
KITAPLAR = [
    ("CS_TYT_2018_2026.pdf", "6aba49d35748c605dd7fe9e8", "TYT"),
    ("CS_DIIN_TYT_2018_2026.pdf", "6abc1f3410f5ec2735b7c59d", "TYT"),
    ("CS_AYT_SAY_2018_2026.pdf", "6abbe07510f5ec2735b6cda6", "AYT"),
    ("CS_AYT_EA_2018_2026.pdf", "6abbfce510f5ec2735b743a2", "AYT"),
    ("CS_AYT_SOZ_2018_2026.pdf", "6abb8789b98f4c074f5d3271", "AYT"),
    ("CS_AYT_DIIN_SOZ_2018_2026.pdf", "6abc1cb910f5ec2735b7be59", "AYT"),
    ("CS_YDT_2018_2026.pdf", "6abae76e5748c605dd819d0a", "YDT"),
]
KITAP_DIZINI = HAM / "meb"
RAPOR = KITAP_DIZINI / "eslesme.json"
COZUM_DIZINI = BURASI / "cozum"
ETIKET = re.compile(r"^(20\d\d)-(TYT|AYT|YDT)$")
NUMARA = re.compile(r"^(\d{1,3})\.$")
SUTUN_BASLARI = (36.0, 287.0)  # kitapta soru numaralarının x0'ı (sol, sağ sütun)
DERSLER = re.compile(
    r"TÜRKÇE|TÜRK DİLİ VE EDEBİYATI|TARİH(?:-\d)?|COĞRAFYA(?:-\d)?|FELSEFE|PSİKOLOJİ|SOSYOLOJİ|MANTIK|DİN KÜLTÜRÜ|"
    r"MATEMATİK|GEOMETRİ|FİZİK|KİMYA|BİYOLOJİ|İNGİLİZCE"
)
# Harf şartıyla (kitabın cevap anahtarı biliniyorsa) ve şartsız eşik.
ESIK_HARFLI = (0.35, 0.08)
ESIK_HARFSIZ = (0.50, 0.15)


def indir() -> None:
    KITAP_DIZINI.mkdir(parents=True, exist_ok=True)
    for dosya, klasor, _ in KITAPLAR:
        yol = KITAP_DIZINI / dosya
        if yol.exists():
            continue
        y = httpx.get(f"{KITAP_TABANI}/{klasor}/{dosya}", timeout=900, follow_redirects=True)
        if y.status_code != 200 or y.content[:5] != b"%PDF-":
            raise SystemExit(f"{dosya} indirilemedi: {y.status_code}")
        yol.write_bytes(y.content)
        print(f"{dosya}: {len(y.content) / 1024 / 1024:.0f} MB")


def sade(metin: str) -> str:
    metin = metin.lower().replace("ı", "i").replace("İ", "i")
    return re.sub(r"[^0-9a-zçğıöşü]+", " ", metin).strip()


def bolum_adi(metin: str) -> str:
    """Bölüm (ders) adı, harf ve rakama indirgenmiş: "COĞRAFYA-1" -> "cografya1"."""
    tablo = str.maketrans("ÇĞİIÖŞÜçğıiöşü", "CGIIOSUcgiiosu")
    return re.sub(r"[^a-z0-9]", "", metin.translate(tablo).lower())


def kitap_anahtari(pdf) -> dict[str, dict[int, str]]:
    """Kitabın sonundaki cevap anahtarı: bölüm adı -> {kitap numarası: harf}."""
    sonuc: dict[str, dict[int, str]] = {}
    bolum = None
    for sayfa in pdf.pages[-8:]:
        for satir in (sayfa.extract_text() or "").split("\n"):
            ciftler = re.findall(r"(\d{1,3})\.([A-E])", satir)
            if ciftler and bolum:
                sonuc.setdefault(bolum, {}).update({int(n): h for n, h in ciftler})
            elif not ciftler and re.fullmatch(r"[A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜa-zçğıöşü \-0-9]{3,40}", satir.strip()):
                bolum = bolum_adi(satir.strip())
    return sonuc


def qr_coz(cizim, kelime) -> str | None:
    """Kaynak etiketinin altındaki QR'ı çözer (bağlantı açıklaması olmayan kitaplar)."""
    import cv2  # noqa: PLC0415  (yalnız bu yolda: uv run --with opencv-python-headless)
    import numpy as np  # noqa: PLC0415

    o = 8
    x0, y0 = int((kelime["x1"] - 40) * o), int(kelime["bottom"] * o)
    x1, y1 = int((kelime["x1"] + 5) * o), int((kelime["bottom"] + 40) * o)
    kes = np.array(cizim)[y0:y1, x0:x1]
    kes = cv2.copyMakeBorder(kes, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)
    for det in (cv2.QRCodeDetector(), cv2.QRCodeDetectorAruco()):
        metin, _, _ = det.detectAndDecode(kes)
        if metin:
            return metin
    return None


def kitap_sorulari(dosya: str, oturum: str) -> list[dict]:
    """Kitaptaki sorular: yıl, bölüm, kitap numarası, metin, bağlantı (QR ya da açıklama)."""
    import pypdfium2 as pdfium  # noqa: PLC0415

    yol = KITAP_DIZINI / dosya
    sonuc = []
    belge_pdf = None
    with pdfplumber.open(str(yol)) as pdf:
        bolum = ""
        for i, sayfa in enumerate(pdf.pages):
            metin = sayfa.extract_text() or ""
            ust = "\n".join(metin.split("\n")[:4])
            m = DERSLER.search(ust)
            if m:
                bolum = bolum_adi(m.group(0))
            kelimeler = sayfa.extract_words()
            etiketler = [w for w in kelimeler if ETIKET.match(w["text"]) and ETIKET.match(w["text"]).group(2) == oturum]
            if not etiketler:
                continue
            orta = sayfa.width / 2
            numaralar = [
                w for w in kelimeler
                if NUMARA.match(w["text"]) and any(abs(w["x0"] - x) <= 3 for x in SUTUN_BASLARI)
            ]
            baglantilar = [h for h in sayfa.hyperlinks if "meb.ai/" in (h.get("uri") or "")]
            cizim = None
            for e in etiketler:
                sutun = e["x0"] >= orta
                ustler = [n for n in numaralar if (n["x0"] >= orta) == sutun and n["top"] < e["top"]]
                yakin = [h for h in baglantilar if (h["x0"] >= orta) == sutun and abs(h["top"] - e["top"]) < 30]
                url = yakin[0]["uri"] if len(yakin) == 1 else None
                if url is None and not baglantilar:
                    if belge_pdf is None:
                        belge_pdf = pdfium.PdfDocument(str(yol))
                    if cizim is None:
                        cizim = belge_pdf[i].render(scale=8, grayscale=True).to_pil()
                    url = qr_coz(cizim, e)
                if not url or not ustler:
                    sonuc.append({"sayfa": i + 1, "yil": int(ETIKET.match(e["text"]).group(1)), "hata": "bağlantı ya da numara yok"})
                    continue
                numara = max(ustler, key=lambda n: n["top"])
                x0, x1 = (orta, sayfa.width) if sutun else (0, orta)
                bolge = [w["text"] for w in kelimeler if x0 <= w["x0"] < x1 and numara["top"] - 1 <= w["top"] < e["top"] - 1]
                sonuc.append({
                    "sayfa": i + 1,
                    "yil": int(ETIKET.match(e["text"]).group(1)),
                    "bolum": bolum,
                    "kitapNo": int(NUMARA.match(numara["text"]).group(1)),
                    "url": url.replace("http://", "https://"),
                    "metin": " ".join(bolge),
                })
        anahtar = kitap_anahtari(pdf)
    if belge_pdf is not None:
        belge_pdf.close()
    for k in sonuc:
        if "bolum" in k:
            k["harf"] = anahtar.get(k["bolum"], {}).get(k["kitapNo"])
    return sonuc


_OSYM: dict[str, dict[str, str]] = {}


def osym_metinleri(belge: dict) -> dict[str, str]:
    """ÖSYM kitapçığında her sorunun metni, kırpma kutusundan (`kirp.py` raporu); anahtar soru kimliği."""
    if belge["id"] in _OSYM:
        return _OSYM[belge["id"]]
    rapor = json.loads((HAM / "kirp.json").read_text(encoding="utf-8"))
    sonuc: dict[str, str] = {}
    with pdfplumber.open(str(PDF_DIZINI / f"{belge['id']}.pdf")) as pdf:
        kelime_onbellek: dict[int, list] = {}
        for kimlik, r in rapor.items():
            if not kimlik.startswith(f"{belge['id']}-") or "kutu" not in r:
                continue
            if r["sayfa"] not in kelime_onbellek:
                kelime_onbellek[r["sayfa"]] = pdf.pages[r["sayfa"] - 1].extract_words()
            x0, y0, x1, y1 = r["kutu"]
            sonuc[kimlik] = sade(" ".join(w["text"] for w in kelime_onbellek[r["sayfa"]] if x0 <= w["x0"] < x1 and y0 <= w["top"] < y1))
    _OSYM[belge["id"]] = sonuc
    return sonuc


def benzerlik(a: str, b: str) -> float:
    sa, sb = set(a.split()), set(b.split())
    if not sa or not sb:
        return 0.0
    jaccard = len(sa & sb) / len(sa | sb)
    oran = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
    return round(0.5 * jaccard + 0.5 * oran, 3)


def esle(adaylar: list[dict], osym: dict[str, str], osym_harf: dict[str, str | None]) -> tuple[dict, list]:
    """Bire bir açgözlü eşleme: kitap sorusu -> ÖSYM sorusu (aynı yıl ve oturum)."""
    ciftler = []
    for ki, k in enumerate(adaylar):
        ks = sade(k["metin"])
        for kimlik, o in osym.items():
            oh = osym_harf.get(kimlik)
            if k.get("harf") and oh and oh != k["harf"]:
                continue
            ciftler.append((benzerlik(ks, o), ki, kimlik))
    sonuc, alinan_o, alinan_k, red = {}, set(), set(), []
    for skor, ki, kimlik in sorted(ciftler, reverse=True):
        if ki in alinan_k or kimlik in alinan_o:
            continue
        esik, fark_esigi = ESIK_HARFLI if adaylar[ki].get("harf") else ESIK_HARFSIZ
        ikinci = max((sk for sk, k2, o2 in ciftler if k2 == ki and o2 != kimlik and o2 not in alinan_o), default=0.0)
        if skor < esik or skor - ikinci < fark_esigi:
            red.append({"kimlik": kimlik, "sayfa": adaylar[ki]["sayfa"], "skor": skor, "fark": round(skor - ikinci, 3)})
            continue
        sonuc[kimlik] = {"url": adaylar[ki]["url"], "skor": skor, "kitapNo": adaylar[ki]["kitapNo"]}
        alinan_o.add(kimlik)
        alinan_k.add(ki)
    return sonuc, red


def main() -> None:
    indir()
    bler = belgeler()
    eslesme: dict[str, dict] = {}
    rapor: dict = {"kitaplar": {}}
    for dosya, _, oturum in KITAPLAR:
        kitap = kitap_sorulari(dosya, oturum)
        bulunan = [k for k in kitap if "url" in k]
        r = {"soru": len(kitap), "baglantili": len(bulunan), "harfli": sum(1 for k in bulunan if k.get("harf")), "eslesen": 0, "hatali": [k for k in kitap if "hata" in k][:20]}
        for b in bler:
            if b["oturum"] != oturum:
                continue
            metin = json.loads((METIN_DIZINI / f"{b['id']}.json").read_text(encoding="utf-8"))
            osym = osym_metinleri(b)
            harf = {f"{b['id']}-{t}-{n}": h for t, a in metin["anahtar"].items() for n, h in a.items()}
            adaylar = [k for k in bulunan if k["yil"] == b["yil"]]
            sonuc, red = esle(adaylar, osym, harf)
            r["eslesen"] += len(sonuc)
            for kimlik, v in sonuc.items():
                if kimlik not in eslesme or v["skor"] > eslesme[kimlik]["skor"]:
                    eslesme[kimlik] = {**v, "kitap": dosya}
        rapor["kitaplar"][dosya] = r
        print(f"{dosya}: {r['soru']} soru, {r['baglantili']} bağlantılı ({r['harfli']} harfli), eşleşen {r['eslesen']}")
    # Belge ve test başına çıktı (commit edilir).
    COZUM_DIZINI.mkdir(exist_ok=True)
    gruplar: dict[str, dict] = {}
    for kimlik, v in eslesme.items():
        on_ek, no = kimlik.rsplit("-", 1)
        gruplar.setdefault(on_ek, {})[no] = {"url": v["url"], "skor": v["skor"], "kitap": v["kitap"], "kitapNo": v["kitapNo"]}
    for on_ek, sorular in sorted(gruplar.items()):
        (COZUM_DIZINI / f"{on_ek}.json").write_text(
            json.dumps({"kaynak": KITAP_SAYFASI, "tarih": datetime.date.today().isoformat(),
                        "sorular": dict(sorted(sorular.items(), key=lambda x: int(x[0])))}, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
        )
    rapor["toplam"] = len(eslesme)
    RAPOR.write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"meb: toplam eşleşen {len(eslesme)} soru, {len(gruplar)} belge-test dosyası")


if __name__ == "__main__":
    main()
