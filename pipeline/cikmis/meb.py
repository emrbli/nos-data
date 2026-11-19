"""MEB çözüm videoları: ÖSYM sorusu başına çözüm bağlantısı.

Kaynak: MEB Ortaöğretim Genel Müdürlüğü "YKS Çıkmış Sorular - 2018-2026 - TYT" kitabı
(OGM Materyal, ogmmateryal.eba.gov.tr/yks-cikmis-soru-kitaplari). Kitapta sorular konu
bazında, her sorunun altında kaynak etiketi ("2025-TYT") ve yanında çözüm videosuna
giden QR ile aynı adresli bağlantı (https://meb.ai/<kod>) var. Kısa adres
mebi.eba.gov.tr/question/show-answer/<kimlik> üzerinden ogm-large-cdn'deki mp4'e
yönlenir; giriş istemez (2026-11-19'da denendi).

Kitap ÖSYM numarasını yazmaz; eşleme içerikle yapılır:
- Kitaptan: her sorunun bölgesi (numara etiketinden kaynak etiketine, aynı sütun), metni,
  yılı ve kaynak etiketinin yanındaki bağlantı.
- ÖSYM tarafı: `metin.py`'nin çıkardığı soru parçaları (aynı yıl, aynı test).
- Benzerlik: harf ve rakam dizisine indirgenmiş metinlerin sözcük kümeleri (Jaccard) ve
  karakter dizisi oranı; en iyi aday en az BENZERLIK_ESIGI ve ikinciden en az FARK_ESIGI
  önde olmalı; eşleme bire birdir (aynı ÖSYM sorusu iki kez alınmaz).
- Eşleşmeyen soru bağlantısız kalır (uygulamada kitap düzeyindeki bağlantı yedektir).

Çıktı (commit edilir): pipeline/cikmis/cozum/<belge>-<test>.json
  {"kaynak": kitap adresi, "tarih", "sorular": {"<no>": {"url": "https://meb.ai/...", "skor": 0.83}}}
Yerel: pipeline/cikmis/yerel/meb/ (kitap PDF'i, eşleme raporu).

  uv run --with pypdf python -m pipeline.cikmis.meb [--indir]
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

KITAP_URL = "https://ogm-small-cdn.eba.gov.tr/ogm-test-images/6aba49d35748c605dd7fe9e8/CS_TYT_2018_2026.pdf"
KITAP_SAYFASI = "https://ogmmateryal.eba.gov.tr/yks-cikmis-soru-kitaplari"
KITAP = HAM / "meb" / "CS_TYT_2018_2026.pdf"
RAPOR = HAM / "meb" / "eslesme.json"
COZUM_DIZINI = BURASI / "cozum"
BOLUM = re.compile(r"MATEMAT[İI]K\s+TYT")  # kitabın matematik bölümü (geometri dahil)
ETIKET = re.compile(r"^(20\d\d)-TYT$")
NUMARA = re.compile(r"^(\d{1,3})\.$")
SUTUN_BASLARI = (36.0, 287.0)  # kitapta soru numaralarının x0'ı (sol, sağ sütun)
BENZERLIK_ESIGI = 0.35
FARK_ESIGI = 0.08


def indir() -> None:
    KITAP.parent.mkdir(parents=True, exist_ok=True)
    y = httpx.get(KITAP_URL, timeout=600, follow_redirects=True)
    if y.status_code != 200 or y.content[:5] != b"%PDF-":
        raise SystemExit(f"kitap indirilemedi: {y.status_code}")
    KITAP.write_bytes(y.content)
    print(f"kitap: {len(y.content) / 1024 / 1024:.0f} MB")


def sade(metin: str) -> str:
    metin = metin.lower().replace("ı", "i").replace("İ", "i")
    return re.sub(r"[^0-9a-zçğıöşü]+", " ", metin).strip()


def kitap_sorulari() -> list[dict]:
    """Kitabın matematik bölümündeki sorular: yıl, metin, bağlantı, sayfa."""
    sonuc = []
    with pdfplumber.open(str(KITAP)) as pdf:
        bolumde = False
        for i, sayfa in enumerate(pdf.pages):
            metin = sayfa.extract_text() or ""
            # Sayfa başlığı "<DERS>\nTYT" (pdfplumber metni); bölüm ayırıcı sayfalar durumu değiştirmez.
            baslik = re.match(r"\s*([^\n]+)\nTYT\n", metin)
            if baslik:
                bolumde = bool(BOLUM.search(f"{baslik.group(1)} TYT"))
            if not bolumde:
                continue
            orta = sayfa.width / 2
            kelimeler = sayfa.extract_words()
            etiketler = [w for w in kelimeler if ETIKET.match(w["text"])]
            numaralar = [
                w for w in kelimeler
                if NUMARA.match(w["text"]) and any(abs(w["x0"] - x) <= 3 for x in SUTUN_BASLARI)
            ]
            baglantilar = [h for h in sayfa.hyperlinks if "meb.ai/" in (h.get("uri") or "")]
            for e in etiketler:
                sutun = e["x0"] >= orta
                # Bağlantı (QR) kaynak etiketinin hemen yanında, aynı sütunda.
                yakin = [h for h in baglantilar if (h["x0"] >= orta) == sutun and abs(h["top"] - e["top"]) < 30]
                ustler = [n for n in numaralar if (n["x0"] >= orta) == sutun and n["top"] < e["top"]]
                if len(yakin) != 1 or not ustler:
                    sonuc.append({"sayfa": i + 1, "yil": int(ETIKET.match(e["text"]).group(1)), "hata": "bağlantı ya da numara yok"})
                    continue
                numara = max(ustler, key=lambda n: n["top"])
                ust = numara["top"]
                x0, x1 = (orta, sayfa.width) if sutun else (0, orta)
                bolge = [w["text"] for w in kelimeler if x0 <= w["x0"] < x1 and ust - 1 <= w["top"] < e["top"] - 1]
                sonuc.append({
                    "sayfa": i + 1,
                    "yil": int(ETIKET.match(e["text"]).group(1)),
                    "kitapNo": int(NUMARA.match(numara["text"]).group(1)),
                    "url": yakin[0]["uri"],
                    "metin": " ".join(bolge),
                })
    return sonuc


def kitap_anahtari() -> dict[int, str]:
    """Kitabın sonundaki cevap anahtarında MATEMATİK bölümü: kitap numarası -> harf."""
    with pdfplumber.open(str(KITAP)) as pdf:
        metin = "\n".join((p.extract_text() or "") for p in pdf.pages[-6:])
    i = metin.find("MATEMATIK")
    if i < 0:
        i = metin.find("MATEMATİK")
    j = min([k for k in (metin.find(x, i + 1) for x in ("FIZIK", "FİZİK")) if k > 0] or [len(metin)])
    return {int(n): h for n, h in re.findall(r"(\d{1,3})\.([A-E])", metin[i:j])}


def osym_metinleri(belge: dict) -> dict[int, str]:
    """ÖSYM kitapçığında her sorunun metni, kırpma kutusundan (`kirp.py` raporu)."""
    rapor = json.loads((HAM / "kirp.json").read_text(encoding="utf-8"))
    sonuc: dict[int, str] = {}
    with pdfplumber.open(str(PDF_DIZINI / f"{belge['id']}.pdf")) as pdf:
        for kimlik, r in rapor.items():
            if not kimlik.startswith(f"{belge['id']}-mat-") or "kutu" not in r:
                continue
            x0, y0, x1, y1 = r["kutu"]
            sayfa = pdf.pages[r["sayfa"] - 1]
            kelimeler = [w["text"] for w in sayfa.extract_words() if x0 <= w["x0"] < x1 and y0 <= w["top"] < y1]
            sonuc[int(kimlik.rsplit("-", 1)[1])] = sade(" ".join(kelimeler))
    return sonuc


def benzerlik(a: str, b: str) -> float:
    sa, sb = set(a.split()), set(b.split())
    if not sa or not sb:
        return 0.0
    jaccard = len(sa & sb) / len(sa | sb)
    oran = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
    return round(0.5 * jaccard + 0.5 * oran, 3)


def main() -> None:
    if "--indir" in sys.argv or not KITAP.exists():
        indir()
    kitap = kitap_sorulari()
    anahtar = kitap_anahtari()
    rapor = {"kitap": len(kitap), "anahtar": len(anahtar), "hatali": [k for k in kitap if "hata" in k], "belgeler": {}}
    COZUM_DIZINI.mkdir(exist_ok=True)
    toplam = 0
    for b in belgeler():
        if b["oturum"] != "TYT" or "mat" not in b.get("testler", []):
            continue
        metin = json.loads((METIN_DIZINI / f"{b['id']}.json").read_text(encoding="utf-8"))
        osym_anahtar = {int(n): h for n, h in metin["anahtar"]["mat"].items()}
        osym = osym_metinleri(b)
        adaylar = [k for k in kitap if k.get("yil") == b["yil"] and "url" in k]
        # Aday çiftler: kitaptaki cevap ÖSYM anahtarıyla aynı olmalı (iptal soruda harf yok, şart aranmaz).
        ciftler = []
        for ki, k in enumerate(adaylar):
            ks = sade(k["metin"])
            kh = anahtar.get(k["kitapNo"])
            for no, o in osym.items():
                oh = osym_anahtar.get(no)
                if oh is not None and kh is not None and oh != kh:
                    continue
                ciftler.append((benzerlik(ks, o), ki, no))
        eslesme, alinan_no, alinan_kitap, reddedilen = {}, set(), set(), []
        for skor, ki, no in sorted(ciftler, reverse=True):
            if ki in alinan_kitap or no in alinan_no:
                continue
            # Aynı kitap sorusu için boşta kalan ikinci en iyi aday.
            ikinci = max((sk for sk, k2, n2 in ciftler if k2 == ki and n2 != no and n2 not in alinan_no), default=0.0)
            if skor < BENZERLIK_ESIGI or skor - ikinci < FARK_ESIGI:
                reddedilen.append({"no": no, "kitapNo": adaylar[ki]["kitapNo"], "skor": skor, "fark": round(skor - ikinci, 3)})
                continue
            eslesme[str(no)] = {"url": adaylar[ki]["url"], "skor": skor, "kitapNo": adaylar[ki]["kitapNo"]}
            alinan_no.add(no)
            alinan_kitap.add(ki)
        dosya = COZUM_DIZINI / f"{b['id']}-mat.json"
        dosya.write_text(
            json.dumps(
                {"kaynak": KITAP_SAYFASI, "tarih": datetime.date.today().isoformat(),
                 "sorular": dict(sorted(eslesme.items(), key=lambda x: int(x[0])))},
                ensure_ascii=False, indent=1,
            ) + "\n",
            encoding="utf-8",
        )
        toplam += len(eslesme)
        rapor["belgeler"][b["id"]] = {"kitapta": len(adaylar), "eslesen": len(eslesme), "reddedilen": reddedilen}
        print(f"{b['id']}: kitapta {len(adaylar)} soru, eşleşen {len(eslesme)}/40, reddedilen {len(reddedilen)}")
    RAPOR.write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"meb: kitapta {len(kitap)} matematik sorusu ({len(rapor['hatali'])} hatalı), toplam eşleşen {toplam}")


if __name__ == "__main__":
    main()
