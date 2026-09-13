"""Türkçe-duyarsız arama için fold() sözleşmesi (Plan K-13).

Bu fonksiyon TS tarafındaki `src/lib/turkish.ts` ile BİREBİR aynı davranmalıdır.
Sözleşme `dist/fold_fixture.json` dosyasıyla iki tarafta da test edilir.

Kural (TS `src/lib/turkish.ts` ile BİREBİR):
  - Türkçe'ye özgü harfler ASCII karşılıklarına eşlenir:
      İ,I,ı -> i   Ş,ş -> s   Ç,ç -> c   Ö,ö -> o   Ü,ü -> u   Ğ,ğ -> g
  - Eşleme lower()'dan ÖNCE yapılır (Python str.lower() Türkçe 'İ'yi
    'i̇' -- i + combining dot -- yapar; bunu engellemek için önce map ederiz).
  - Kalan harfler ASCII-güvenli lower() ile küçültülür.
  - Boşluk NORMALİZE EDİLMEZ / trim YAPILMAZ: TS fold() de yapmaz (tokenizasyon
    ayrı bir adımdır; FTS5 zaten boşluktan böler). Fixture bu davranışı test eder.
"""

from __future__ import annotations

import json
from pathlib import Path

# Türkçe -> ASCII fold tablosu. Sıra önemli değildir (karakter-karakter uygulanır).
_FOLD_MAP = {
    "İ": "i",
    "I": "i",
    "ı": "i",
    "Ş": "s",
    "ş": "s",
    "Ç": "c",
    "ç": "c",
    "Ö": "o",
    "ö": "o",
    "Ü": "u",
    "ü": "u",
    "Ğ": "g",
    "ğ": "g",
    # Şapkalı harfler ("Bezm-i Âlem"): katlanmazsa TS tokenizer 'â'yı sınır
    # sayıp kelimeyi böler; FTS unicode61 remove_diacritics ile de hizalanır.
    "Â": "a",
    "â": "a",
    "Î": "i",
    "î": "i",
    "Û": "u",
    "û": "u",
}

def fold(text: str | None) -> str:
    """Bir metni Türkçe-duyarsız forma indirger (TS fold() ile birebir)."""
    if not text:
        return ""
    out = [_FOLD_MAP.get(ch, ch) for ch in text]
    return "".join(out).lower()


# Fixture: TS tarafının aynı fixture ile test edeceği en az 30 vaka.
# İ/ı/Ş/Ç/Ö/Ü/Ğ ve büyük/küçük harf kombinasyonlarını kapsar.
_FIXTURE_INPUTS = [
    "İSTANBUL",
    "İstanbul",
    "istanbul",
    "ISPARTA",
    "Işık Üniversitesi",
    "IŞIK",
    "ığdır",
    "IĞDIR",
    "Iğdır Üniversitesi",
    "ODTÜ",
    "BOĞAZİÇİ ÜNİVERSİTESİ",
    "Boğaziçi",
    "Çankaya",
    "ÇANKAYA",
    "Şırnak",
    "ŞIRNAK",
    "Gaziantep",
    "GAZİANTEP",
    "Bilgisayar Mühendisliği",
    "BİLGİSAYAR MÜHENDİSLİĞİ",
    "Mühendislik",
    "Öğretmenlik",
    "ÖĞRETMENLİK",
    "İngilizce Öğretmenliği",
    "Eczacılık",
    "ECZACILIK",
    "Diş Hekimliği",
    "DİŞ HEKİMLİĞİ",
    "Uçak Mühendisliği",
    "Çağ Üniversitesi",
    "  Çift   Boşluk  ",
    "Hemşirelik",
    "HEMŞİRELİK",
    "Güzel Sanatlar",
    "GÜZEL SANATLAR",
    "Türk Dili ve Edebiyatı",
    "Uluslararası İlişkiler",
    "Yıldız Teknik Üniversitesi",
    "Şişli",
    "İnönü Üniversitesi",
    "Bezm-i Âlem Vakıf Üniversitesi",
    "BEZM-İ ÂLEM",
    "Kâtip Çelebi",
]


def build_fixture() -> list[dict[str, str]]:
    """[{"in": <girdi>, "out": <fold(girdi)>}] listesi üretir."""
    return [{"in": s, "out": fold(s)} for s in _FIXTURE_INPUTS]


# TS `src/lib/turkish.ts` fold()'unun BAĞIMSIZ Python aynası (çapraz-doğrulama için).
# Bu tablo/mantık turkish.ts'ten birebir kopyalanmıştır; buradaki `fold()` ile
# aynı sonucu vermeli. Eğer biri değişip diğeri değişmezse verify_fixture yakalar.
_TS_FOLD_MAP = {
    "ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g", "ı": "i", "İ": "i", "I": "i",
    "ö": "o", "Ö": "o", "ş": "s", "Ş": "s", "ü": "u", "Ü": "u",
    "â": "a", "Â": "a", "î": "i", "Î": "i", "û": "u", "Û": "u",
}


def _ts_reference_fold(text: str) -> str:
    """TS fold() ile birebir: char-map + toLowerCase, boşluk/trim YOK."""
    return "".join(_TS_FOLD_MAP.get(ch, ch) for ch in text).lower()


def verify_fixture(fixture: list[dict[str, str]]) -> None:
    """Her vektörün beklenen çıktısının HEM Python fold() HEM TS-referans fold ile
    uyumlu olduğunu doğrular. Uyumsuzlukta AssertionError fırlatır."""
    mismatches: list[str] = []
    for case in fixture:
        py = fold(case["in"])
        ts = _ts_reference_fold(case["in"])
        if case["out"] != py:
            mismatches.append(f"{case['in']!r}: fixture={case['out']!r} != python_fold={py!r}")
        if case["out"] != ts:
            mismatches.append(f"{case['in']!r}: fixture={case['out']!r} != ts_ref_fold={ts!r}")
    if mismatches:
        raise AssertionError(
            f"fold_fixture tutarsız ({len(mismatches)} uyumsuzluk):\n  " + "\n  ".join(mismatches)
        )


def write_fixture(path: str | Path) -> Path:
    """Fold fixture'ını üretir, Python+TS fold ile tutarlılığını ASSERT eder, yazar."""
    fixture = build_fixture()
    verify_fixture(fixture)  # fail-fast: fold/fixture/TS ayrışırsa yazmadan durur
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":  # pragma: no cover - manuel fixture üretimi
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "dist/fold_fixture.json"
    p = write_fixture(target)
    n = len(build_fixture())
    print(f"fold_fixture yazıldı: {p} ({n}/{n} vaka Python+TS fold ile doğrulandı)")
