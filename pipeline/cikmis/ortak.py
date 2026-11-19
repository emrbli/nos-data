"""Çıkmış soru dizini hattının ortak yolları, sabitleri ve okuyucuları."""

from __future__ import annotations

import json
import re
from pathlib import Path

KOK = Path(__file__).resolve().parents[2]
BURASI = Path(__file__).resolve().parent
BELGELER = BURASI / "belgeler.json"
ETIKET_DIZINI = BURASI / "etiket"
# Yalnız yerel (gitignore): PDF, çıkarılan metin, ham etiketleme.
HAM = BURASI / "yerel"
PDF_DIZINI = HAM / "pdf"
METIN_DIZINI = HAM / "metin"
DIST = KOK / "dist"

# Oturum başına testler: (kod, basılı soru sayısı, anahtar sayfasındaki başlık deseni). Sıra kitapçık sırasıdır.
TESTLER: dict[str, list[tuple[str, int, str]]] = {
    "TYT": [
        ("trk", 40, r"TÜRKÇE"),
        ("sos", 25, r"SOSYAL\s+B[İI]L[İI]MLER[İI]?"),
        ("mat", 40, r"TEMEL\s+MATEMAT[İI]K"),
        ("fen", 20, r"FEN\s+B[İI]L[İI]MLER[İI]?"),
    ],
    "AYT": [
        ("tde-sos1", 40, r"T[ÜU]RK\s+D[İI]L[İI]\s+(?:VE|ve)\s+EDEB[İI]YATI-SOSYAL\s+B[İI]L[İI]MLER-1"),
        ("sos2", 46, r"SOSYAL\s+B[İI]L[İI]MLER-2"),
        ("mat", 40, r"(?<!TEMEL )MATEMAT[İI]K"),
        ("fen", 40, r"FEN\s+B[İI]L[İI]MLER[İI]?"),
    ],
    "YDT": [
        ("ing", 80, r"[İI]NG[İI]L[İI]ZCE"),
    ],
}

# Uygulamaya giden alanlar (nos-academy scripts/sync-db.mjs aynı listeyi denetler).
BELGE_ALANLARI = ("id", "yil", "oturum", "kapsam", "dersler", "kitapcikUrl", "yayimUrl", "cozumUrl")
SORU_ALANLARI = ("id", "belge", "test", "no", "sayfa", "konu", "altKonu", "ekKonu", "cevap", "iptal", "cevapDegisti", "etiket")

ETIKET_TURLERI = {"cift-onay", "hakem", "insan", "belirsiz"}
ALT_KONULAR = {
    "tyt_mat.problem": {"sayi", "kesir", "yas", "yuzde", "kar-zarar", "karisim", "hareket", "isci-havuz", "rutin-olmayan", "diger"},
}
KONU_DESENI = re.compile(r"^(tyt|ayt|ydt)_[a-z0-9]+\.[a-z0-9-]+$")
HARFLER = {"A", "B", "C", "D", "E"}


def belgeler() -> list[dict]:
    return json.loads(BELGELER.read_text(encoding="utf-8"))["belgeler"]


def etiket_dosyalari() -> list[Path]:
    return sorted(ETIKET_DIZINI.glob("*.json"))


def oku(yol: Path) -> dict:
    return json.loads(yol.read_text(encoding="utf-8"))
