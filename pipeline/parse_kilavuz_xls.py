"""ÖSYM kılavuzu Tablo 3/4 — XLS (BIFF, ÖSYM sitesi) parser'ı. YALNIZ ÇAPRAZ KONTROL.

PDF parser (`parse_kilavuz.py`) OTORİTER kalır; bu modül aynı tabloların ÖSYM'nin
yayınladığı XLS sürümünü okuyup `GuideProgram` üretir; `merge.cross_check_guide_xls`
ikisini alan bazında karşılaştırır (discrepancy_report.md + validate yumuşak uyarı).
Veriye YAZILMAZ (karar 2026-09-13: "yalnız çapraz kontrol").

Dosya düzeni (2026 kılavuzu, doğrulandı):
  Tablo 3 (önlisans, tek sayfa "Sayfa1", 13 sütun):
    0 kod | 1 program adı | 2 süre | 3 puan türü | 4 genel kont | 5 okul birincisi |
    6 şehit/gazi | 7 34 yaş üstü kadın | 8 koşullar | 9 önceki yıl başarı sırası |
    10 önceki yıl en küçük puan | 11 TYÇ | 12 akreditasyon
  Tablo 4 (lisans, tek sayfa "sayfa", 24 sütun):
    0 kod | 1 ad | 2 süre | 3 PT | 4 kont | 5 ok.bir | 6 MEB (atla) | 7 şehit | 8 34 yaş |
    9 koşul | 10 sıra | 11 puan | 12-15 öğr. üyesi/GRV (atla) | 16 TYÇ | 17 akreditasyon |
    18-23 TUS/DUS/AB/KPSS (atla)
  İlk 3 satır başlık. Kod hücresi 9 haneli değilse üniversite/fakülte başlık satırıdır
  (ad 1. sütunda; akreditasyon sütununda "YÖKAK" gibi üniversite akreditasyonu olabilir).
Atlanan sütunlar VERI_NOTLARI §1.3 "bilinçli kapsam dışı" listesiyle aynıdır.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from .parse_kilavuz import GuideProgram

_CODE_RE = re.compile(r"^\d{9}$")
_HEADER_ROWS = 3
_PUAN_LO, _PUAN_HI = 100.0, 560.0
_SIRA_MAX = 5_000_000
_PT_NORMALIZE = {"SOZ": "SÖZ", "DIL": "DİL"}

# tablo -> {sütun indeksi: GuideProgram alanı}
_FIELDS: dict[int, dict[int, str]] = {
    3: {2: "sure", 3: "puan_turu", 4: "kont_genel", 5: "kont_okul_birincisi",
        6: "kont_sehit_gazi", 7: "kont_34yas", 8: "kosul", 9: "sira", 10: "puan",
        11: "tyc", 12: "akreditasyon"},
    4: {2: "sure", 3: "puan_turu", 4: "kont_genel", 5: "kont_okul_birincisi",
        7: "kont_sehit_gazi", 8: "kont_34yas", 9: "kosul", 10: "sira", 11: "puan",
        16: "tyc", 17: "akreditasyon"},
}


def _log(logf: Callable[[str], None] | None, msg: str) -> None:
    if logf:
        logf(msg)


def _cell(sheet: Any, r: int, c: int) -> str:
    if c >= sheet.ncols:
        return ""
    v = sheet.cell_value(r, c)
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _int(text: str) -> int | None:
    t = re.sub(r"[^\d]", "", text)
    return int(t) if t else None


def _float(text: str) -> float | None:
    t = text.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def _parse_sheet(path: Path, tablo: int, logf: Callable[[str], None] | None) -> dict[int, GuideProgram]:
    import xlrd  # local import: yalnız bu modül xlrd gerektirir

    wb = xlrd.open_workbook(str(path), formatting_info=False)
    sheet = wb.sheet_by_index(0)
    fields = _FIELDS[tablo]
    out: dict[int, GuideProgram] = {}
    current_uni: str | None = None
    skipped_rows = 0
    for r in range(_HEADER_ROWS, sheet.nrows):
        code_txt = _cell(sheet, r, 0)
        name = _cell(sheet, r, 1)
        if not _CODE_RE.match(code_txt):
            # Başlık satırı: üniversite adı BÜYÜK harf ve "ÜNİVERSİTESİ"/"YÜKSEKOKULU" içerir;
            # fakülte satırları da buraya düşer — uni_ad yalnız üniversite satırında güncellenir.
            if name and re.search(r"ÜNİVERSİTE|YÜKSEK TEKNOLOJİ|HARP OKULU|AKADEMİ", name.upper()) \
                    and not re.search(r"FAKÜLTE|YÜKSEKOKUL|MESLEK|ENSTİTÜ|KONSERVATUVAR", name.upper()):
                current_uni = name
            elif code_txt:
                skipped_rows += 1
            continue
        gp = GuideProgram(kod=int(code_txt), prog_ad=name.strip(), tablo=tablo, uni_ad=current_uni)
        for col, fname in fields.items():
            txt = _cell(sheet, r, col)
            if not txt:
                continue
            if fname == "sure":
                gp.sure = _int(txt)
            elif fname == "puan_turu":
                pt = txt.upper()
                gp.puan_turu = _PT_NORMALIZE.get(pt, pt)
            elif fname in ("kont_genel", "kont_okul_birincisi", "kont_sehit_gazi", "kont_34yas"):
                setattr(gp, fname, _int(txt))
            elif fname == "kosul":
                gp.kosul_kodlari = [c.strip() for c in txt.split(",") if c.strip()]
            elif fname == "sira":
                v = _int(txt)
                gp.basari_sirasi_onceki = v if v is not None and 0 < v <= _SIRA_MAX else None
            elif fname == "puan":
                v = _float(txt)
                gp.en_kucuk_puan_onceki = v if v is not None and _PUAN_LO <= v <= _PUAN_HI else None
            elif fname == "tyc":
                gp.tyc = txt
            elif fname == "akreditasyon":
                gp.akreditasyon = txt
        out[gp.kod] = gp
    _log(logf, f"  [xls] Tablo {tablo}: {path.name} -> {len(out)} program "
               f"({sheet.nrows} satır, {sheet.ncols} sütun, atlanan kodsuz-metin {skipped_rows})")
    return out


def parse_kilavuz_xls(
    t3_path: str | Path | None,
    t4_path: str | Path | None,
    *,
    logf: Callable[[str], None] | None = None,
) -> dict[int, GuideProgram]:
    """Tablo 3 ve/veya Tablo 4 XLS'ini parse eder; {kilavuz_kodu: GuideProgram} döner."""
    programs: dict[int, GuideProgram] = {}
    if t3_path:
        programs.update(_parse_sheet(Path(t3_path), 3, logf))
    if t4_path:
        programs.update(_parse_sheet(Path(t4_path), 4, logf))
    _log(logf, f"  [xls] TOPLAM {len(programs)} program (yalnız çapraz kontrol, PDF otoriter)")
    return programs
