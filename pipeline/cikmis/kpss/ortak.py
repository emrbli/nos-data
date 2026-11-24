"""KPSS çıkmış soru hattının yolları, sabitleri ve okuyucuları (YKS `ortak.py`'nin karşılığı)."""

from __future__ import annotations

import json
import re
from pathlib import Path

KOK = Path(__file__).resolve().parents[3]
BURASI = Path(__file__).resolve().parent
BELGELER = BURASI / "belgeler.json"
KONULAR = BURASI / "konular.json"
ETIKET_DIZINI = BURASI / "etiket"
# Yalnız yerel (gitignore: pipeline/cikmis/yerel/): PDF, çıkarılan metin, ham etiketleme, görseller.
HAM = BURASI.parent / "yerel" / "kpss"
PDF_DIZINI = HAM / "pdf"
PDF2_DIZINI = HAM / "pdf2"  # çok kitapçıklı belgeler (alan, DHBT): pdf2/<belge>/<ad>.pdf
ILERLEME = HAM / "ilerleme.json"
METIN_DIZINI = HAM / "metin"
GORSEL_DIZINI = HAM / "gorsel"
RAPOR = HAM / "kirp.json"
DIST = KOK / "dist"
DIZIN_ADI = "cikmis-kpss.json"
GORSEL_DIZIN_ADI = "cikmis-kpss-gorsel.json"
GORSEL_PAKET_ON_EKI = "cikmis-kpss-gorsel-"

# Oturum başına testler: (kod, basılı soru sayısı, sayfa üstbilgisindeki test deseni).
TESTLER: dict[str, list[tuple[str, int, str]]] = {
    "LISANS": [("gy", 60, r"KPSS[^\n]*?/GY\b"), ("gk", 60, r"KPSS[^\n]*?/GK\b")],
    "ONLISANS": [("gy", 60, r"KPSS[^\n]*?/GY\b"), ("gk", 60, r"KPSS[^\n]*?/GK\b")],
    "ORTAOGRETIM": [("gy", 60, r"KPSS[^\n]*?/GY\b"), ("gk", 60, r"KPSS[^\n]*?/GK\b")],
    "EB": [("eb", 80, r"KPSS[^\n]*?/EB\b")],
    # Alan Bilgisi (A grubu): her test ayrı PDF'tir, sayfa üstbilgisi aranmaz (desen None).
    "ALAN": [(k, 40, None) for k in ("huk", "ikt", "isl", "ist", "kamu", "mal", "muh", "ui", "ceei")],
    # DHBT: her düzey PDF'inde DHBT-1 (hepsinde aynı; lisans PDF'inden alınır) ve o düzeyin DHBT-2'si.
    "DHBT": [
        ("dhbt1", 20, r"DHBT-1"), ("dhbt2-lisans", 20, r"DHBT-2"),
        ("dhbt2-onlisans", 20, r"DHBT-2"), ("dhbt2-ortaogretim", 20, r"DHBT-2"),
    ],
}
# Yayımlanan soru sayısı (yüzde 10): test başına. Tam kapsamda (2019-2021) basılı adetin tamamı.
YAYIMLANAN = {
    "gy": 6, "gk": 6, "eb": 8,
    **{k: 4 for k in ("huk", "ikt", "isl", "ist", "kamu", "mal", "muh", "ui", "ceei")},
    "dhbt1": 2, "dhbt2-lisans": 2, "dhbt2-onlisans": 2, "dhbt2-ortaogretim": 2,
}


def beklenen(belge: dict, test: str, adet: int) -> int:
    return adet if belge["kapsam"] == "tam" else YAYIMLANAN[test]

# `kitapciklar` ({test: PDF adresi}) yalnız her testi ayrı PDF olan belgelerde (alan, DHBT) vardır; orada `kitapcikUrl` null'dır.
BELGE_ALANLARI = ("id", "yil", "oturum", "kapsam", "dersler", "kitapcikUrl", "kitapciklar", "yayimUrl", "cozumUrl")
SORU_ALANLARI = ("id", "belge", "test", "no", "sayfa", "konu", "altKonu", "ekKonu", "cevap", "iptal", "cevapDegisti", "etiket")

ETIKET_TURLERI = {"cift-onay", "hakem", "insan", "belirsiz"}
KONU_DESENI = re.compile(r"^kpss_[a-z0-9]+\.[a-z0-9-]+$")
HARFLER = {"A", "B", "C", "D", "E"}


def belgeler() -> list[dict]:
    return json.loads(BELGELER.read_text(encoding="utf-8"))["belgeler"]


def konu_katalogu() -> dict[str, dict]:
    return json.loads(KONULAR.read_text(encoding="utf-8"))["dersler"]


def etiket_dosyalari() -> list[Path]:
    return sorted(ETIKET_DIZINI.glob("*.json"))


def oku(yol: Path) -> dict:
    return json.loads(yol.read_text(encoding="utf-8"))


def belge_testleri(belge: dict) -> list[tuple[str, int, str | None]]:
    """Belgenin etiketlenen testleri: TESTLER[oturum] içinden `belge["testler"]` sırasıyla."""
    tanim = {k: (k, n, d) for k, n, d in TESTLER[belge["oturum"]]}
    return [tanim[t] for t in belge["testler"]]


def gruplar(belge: dict) -> list[tuple[Path, list[tuple[str, int, str | None]]]]:
    """(PDF yolu, o PDF'teki testler) listesi. Tek PDF'li belgede pdf/<id>.pdf, diğerlerinde `kaynaklar`."""
    tanim = {k: (k, n, d) for k, n, d in TESTLER[belge["oturum"]]}
    if "kaynaklar" not in belge:
        return [(PDF_DIZINI / f"{belge['id']}.pdf", belge_testleri(belge))]
    return [(PDF2_DIZINI / g["pdf"], [tanim[t] for t in g["testler"]]) for g in belge["kaynaklar"]]


def ders_testleri(ders: dict) -> list[str]:
    return ders.get("testler") or [ders["test"]]
