#!/usr/bin/env python3
"""Mevcut dist/nos.db'deki yearly_stats'ı git-izli tarihsel arşive dondurur.

YÖK Atlas API yalnız current + 3 suffix (4 yıl) döndürür; her yıl geçişinde en
eski yıl API'den DÜŞER (2026 geçişinde 2022 düştü) ve bazı tarihsel alanlar
kaybolabilir (2026'da gkY1 -> tarihsel yerleşen kayboldu). Bu script, doğrulanmış
bir build'in yearly_stats tablosunu `archive/yearly_stats_*.json.gz` olarak
saklar; merge.py bunu YALNIZ DOLDURMA amaçlı kullanır (API kazanır, bkz.
merge.apply_history_archive).

Kullanım:
  uv run python scripts/make_history_archive.py                 # dist/nos.db -> archive/
  uv run python scripts/make_history_archive.py --db path.db --out archive/x.json.gz
"""
from __future__ import annotations

import argparse
import gzip
import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(HERE / "dist" / "nos.db"))
    ap.add_argument("--out", default=None,
                    help="Çıktı (varsayılan archive/yearly_stats_{min}_{max}.json.gz)")
    ap.add_argument("--kz-year-shift", type=int, default=0,
                    help="Kaynak DB'de kontenjan/yerleşen (k/z) etiketleri N yıl ESKİ ise düzelt: "
                         "yıl Y'nin k/z'si Y+N'e taşınır, puan/sıra (p/s) yerinde kalır. Temmuz 2026 "
                         "build'i için 1 (gk{N} kılavuz yılına, minPuan{N} sonuç yılına çapalıydı; "
                         "bkz. merge._extract_years).")
    args = ap.parse_args(argv)

    db = Path(args.db)
    if not db.exists():
        print(f"HATA: {db} yok", file=sys.stderr)
        return 2
    # SALT OKUNUR aç: dist/nos.db WAL'e geçirilmemeli (docs §3.4).
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    meta = {r["key"]: r["value"] for r in conn.execute("SELECT key,value FROM meta")}
    rows = conn.execute(
        "SELECT program_id, yil, puan_turu, kontenjan, yerlesen, puan, sira "
        "FROM yearly_stats ORDER BY program_id, yil DESC").fetchall()
    conn.close()

    shift = args.kz_year_shift
    # (program, yıl) -> satır; k/z kaydırması için önce p/s, sonra k/z birleştirilir.
    cells: dict[tuple[str, int], dict] = {}
    pt_by_prog: dict[str, str] = {}

    def cell(pid: str, y: int) -> dict:
        return cells.setdefault((pid, y), {"y": y, "pt": None, "k": None, "z": None, "p": None, "s": None})

    for r in rows:
        pid, y = str(r["program_id"]), int(r["yil"])
        pt_by_prog.setdefault(pid, r["puan_turu"])
        c = cell(pid, y)
        c["pt"], c["p"], c["s"] = r["puan_turu"], r["puan"], r["sira"]
        if r["kontenjan"] is not None or r["yerlesen"] is not None:
            kz = cell(pid, y + shift)
            kz["k"], kz["z"] = r["kontenjan"], r["yerlesen"]
    by_prog: dict[str, list[dict]] = {}
    years: set[int] = set()
    dropped_empty = 0
    for (pid, y), c in sorted(cells.items(), key=lambda kv: (kv[0][0], -kv[0][1])):
        if c["k"] is None and c["z"] is None and c["p"] is None and c["s"] is None:
            dropped_empty += 1
            continue
        c["pt"] = c["pt"] or pt_by_prog.get(pid)
        years.add(y)
        by_prog.setdefault(pid, []).append(c)
    ymin, ymax = min(years), max(years)
    out = Path(args.out) if args.out else HERE / "archive" / f"yearly_stats_{ymin}_{ymax}.json.gz"
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "meta": {
            "sourceDb": str(db.relative_to(HERE)) if db.is_relative_to(HERE) else str(db),
            "sourceExportedAt": meta.get("exportedAt"),
            "sourceSha256Json": meta.get("sha256_json"),
            "sourceSchemaVersion": meta.get("schemaVersion"),
            "sourceDataYear": meta.get("dataYear"),
            "years": sorted(years),
            "programCount": len(by_prog),
            "rowCount": sum(len(v) for v in by_prog.values()),
            "sourceRowCount": len(rows),
            "kzYearShift": shift,
            "note": ("k/z (kontenjan/yerleşen) etiketleri kaynak DB'ye göre "
                     f"+{shift} yıl kaydırıldı; p/s yerinde." if shift else
                     "k/z etiketleri kaynak DB ile aynı."),
        },
        "programs": by_prog,
    }
    with gzip.open(out, "wt", encoding="utf-8", compresslevel=9) as fh:
        json.dump(doc, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"yazıldı: {out} ({out.stat().st_size/1024:.0f} KB) — {len(by_prog)} program, "
          f"{doc['meta']['rowCount']} yıl-satırı (kaynak {len(rows)}), yıllar {sorted(years)}, "
          f"k/z kaydırma={shift}, kaynak exportedAt={meta.get('exportedAt')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
