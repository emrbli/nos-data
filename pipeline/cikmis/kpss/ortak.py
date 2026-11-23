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
METIN_DIZINI = HAM / "metin"
GORSEL_DIZINI = HAM / "gorsel"
RAPOR = HAM / "kirp.json"
DIST = KOK / "dist"
DIZIN_ADI = "cikmis-kpss.json"
GORSEL_DIZIN_ADI = "cikmis-kpss-gorsel.json"
GORSEL_PAKET_ON_EKI = "cikmis-kpss-gorsel-"

# Oturum başına testler: (kod, basılı soru sayısı, sayfa üstbilgisindeki test deseni).
TESTLER: dict[str, list[tuple[str, int, str]]] = {
    "LISANS": [("gy", 60, r"KPSS[^\n/]*/GY\b"), ("gk", 60, r"KPSS[^\n/]*/GK\b")],
    "ONLISANS": [("gy", 60, r"KPSS[^\n/]*/GY\b"), ("gk", 60, r"KPSS[^\n/]*/GK\b")],
    "ORTAOGRETIM": [("gy", 60, r"KPSS[^\n/]*/GY\b"), ("gk", 60, r"KPSS[^\n/]*/GK\b")],
    "EB": [("eb", 80, r"KPSS[^\n/]*/EB\b")],
}
# Yayımlanan soru sayısı (yüzde 10): test başına.
YAYIMLANAN = {"gy": 6, "gk": 6, "eb": 8}

BELGE_ALANLARI = ("id", "yil", "oturum", "kapsam", "dersler", "kitapcikUrl", "yayimUrl", "cozumUrl")
SORU_ALANLARI = ("id", "belge", "test", "no", "sayfa", "konu", "altKonu", "ekKonu", "cevap", "iptal", "cevapDegisti", "etiket")

ETIKET_TURLERI = {"cift-onay", "hakem", "insan", "belirsiz"}
KONU_DESENI = re.compile(r"^kpss_[a-z]+\.[a-z0-9-]+$")
HARFLER = {"A", "B", "C", "D", "E"}


def belgeler() -> list[dict]:
    return json.loads(BELGELER.read_text(encoding="utf-8"))["belgeler"]


def konu_katalogu() -> dict[str, dict]:
    return json.loads(KONULAR.read_text(encoding="utf-8"))["dersler"]


def etiket_dosyalari() -> list[Path]:
    return sorted(ETIKET_DIZINI.glob("*.json"))


def oku(yol: Path) -> dict:
    return json.loads(yol.read_text(encoding="utf-8"))
