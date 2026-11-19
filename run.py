#!/usr/bin/env python3
"""NOS veri pipeline — tek giriş noktası (brief §9, plan §5).

Sıra: FETCH -> MERGE -> VALIDATE -> BUILD SQLITE -> TEST -> REPORT.
Atomik yazma: tüm artefaktlar önce dist.tmp/ altında üretilir; VALIDATE ve TEST
geçmeden dist/ DOKUNULMAZ. Herhangi bir kapı FAIL -> exit 1, dist/ değişmez.

Kullanım:
  uv run python run.py                 # tam koşu (tüm evren, tüm fazlar)
  uv run python run.py --until merge    # yalnız fetch+merge (Faz 0–2, Task #1)
  uv run python run.py --only DİL       # tek puan türü (hızlı bounded test)
  uv run python run.py --max-pages 2    # kombo başına 2 sayfa (bounded test)
  uv run python run.py --skip-fetch     # raw/'tan yeniden merge (idempotans testi)
  uv run python run.py --skip-netler    # net çekimini atla (net_profiles boş, hızlı dev)
  uv run python run.py --fetch-netler-only  # K1 raw'dan, ağdan yalnız eksik net yılları
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from pipeline.years import RESULT_YEAR

HERE = Path(__file__).resolve().parent
RAW_DIR = HERE / "raw"
LOGS_DIR = HERE / "logs"
DIST_DIR = HERE / "dist"
DIST_TMP = HERE / "dist.tmp"

# Fazlar sıralı; --until bu sıraya göre keser.
_PHASE_ORDER = ["fetch", "merge", "validate", "build", "test"]

# Şema sürümü. 1→2: net_profiles tablosu + ek nullable program kolonları eklendi.
# 2→3: ÖSYM 2026 kılavuzu (K2) OTORİTER kaynak oldu — ucret/ucret_aciklama/
# kont_sehit_gazi/kont_okul_birincisi/tyc/uni_web eklendi (bkz. parse_kilavuz.py).
# meta.json'a schemaVersion olarak yazılır; update.ts OTA karşılaştırmasında kullanır
# (bu alan v1'de meta.json'a HİÇ yazılmıyordu — bu koşuda düzeltildi).
# 6→7: net_katsayi + net_katsayi_meta tabloları eklendi (Net Sihirbazı
# "Sıralamamı Bul" — net_profiles ground-truth'una oturtulmuş net→puan
# regresyon katsayıları, bkz. pipeline/net_katsayi.py).
# 7→8: alias temizliği (K-13, bkz. build_sqlite.py ALIAS yorumu) — corpus
# kelimesi kaçıran satırlar kaldırıldı; DDL değişmedi. Uygulama tarafındaki
# CURRENT_SCHEMA_VERSION (src/lib/schema.ts) ile senkron tutulmalı.
# 2026-09 (v8 KORUNDU): 2026 yerleştirme sonuçları eklendi; yearly_stats.yil
# CHECK kümesi 2022..2026'ya GENİŞLEDİ (kolon/tip değişmedi -> sürüm artmaz;
# uygulama yeni DB'yi OTA ile alır). Yıl konfigürasyonu: pipeline/years.py.
SCHEMA_VERSION = 8

# Kılavuz PDF'inin varsayılan konumu: bu reponun docs/ klasörü (git-izli, kanonik).
# --kilavuz-pdf ile değiştirilebilir; --skip-kilavuz ile tamamen atlanabilir.
DEFAULT_KILAVUZ_PDF = HERE / "docs" / "kontkilavuz_yktd21072026.pdf"
# Kılavuz Tablo 3/4 XLS'leri (ÖSYM sitesinden; YALNIZ çapraz kontrol, PDF otoriter).
DEFAULT_KILAVUZ_XLS_T3_GLOB = "docs/tablo-3-*.xls"
DEFAULT_KILAVUZ_XLS_T4_GLOB = "docs/tablo-4-*.xls"
# Tarihsel arşiv (git-izli): API'den düşen yıllar buradan dolar (years.py, merge.py).
DEFAULT_HISTORY_ARCHIVE = HERE / "archive" / "yearly_stats_2022_2025.json.gz"


class Logger:
    """Konsol + tarihli log dosyasına yazar."""

    def __init__(self, logfile: Path) -> None:
        logfile.parent.mkdir(parents=True, exist_ok=True)
        self._fh = logfile.open("w", encoding="utf-8")
        self.logfile = logfile

    def __call__(self, msg: str) -> None:
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        self._fh.write(line + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


def _load_raw_k1(raw_dir: Path, log: Logger) -> list[dict[str, Any]]:
    """--skip-fetch: raw/k1/{RESULT_YEAR}/**/*.json sayfalarını geri okuyup program listesi kurar.

    Dizin düzeni: PT-tagli kombolar (SAY/EA/SOZ/DIL/TYT) + tamamlama taramaları
    (ALL46/ALL47 — puanTuru NULL kayıtlar için, bkz. fetch.SEARCH_COMBOS).
    PT-tagli dizinler ÖNCE yüklenir ki merge dedup'ında ("ilk kayıt kazanır")
    PT izi taşıyan kayıtlar kazansın — glob sıralaması buna yetmez (ALL46
    alfabetik olarak DIL'den önce gelir), açıkça sıralanır."""
    from pipeline.fetch import _PT_DIR, k1_raw_dir

    programs: list[dict[str, Any]] = []
    inv = {v: k for k, v in _PT_DIR.items()}
    files = 0
    k1_dir = k1_raw_dir(raw_dir)
    if not k1_dir.exists():
        raise FileNotFoundError(f"{k1_dir} yok — bu sonuç yılı için önce ağdan fetch gerekir")
    dirs = [d for d in sorted(k1_dir.glob("*")) if d.is_dir()]
    dirs.sort(key=lambda d: d.name.startswith("ALL"))  # ALL* dizinleri EN SONA
    for combo_dir in dirs:
        is_all = combo_dir.name.startswith("ALL")
        puan_turu = None if is_all else inv.get(combo_dir.name, combo_dir.name)
        if is_all:
            birim_turu_id = 47 if combo_dir.name == "ALL47" else 46
        else:
            birim_turu_id = 47 if puan_turu == "TYT" else 46
        for page_file in sorted(combo_dir.glob("*.json")):
            files += 1
            raw = json.loads(page_file.read_text(encoding="utf-8"))
            for item in raw.get("content") or []:
                if puan_turu is not None:
                    item.setdefault("_fetch_puan_turu", puan_turu)
                item.setdefault("_fetch_birim_turu_id", birim_turu_id)
                programs.append(item)
    log(f"  raw/'tan {files} sayfa, {len(programs)} kayıt yüklendi")
    return programs


def _load_raw_netler(raw_dir: Path, log: Logger) -> list[dict[str, Any]]:
    """--skip-fetch: raw/netler/{PT}/{yil}/*.json sayfalarını geri okur (ağsız)."""
    from pipeline.fetch import _PT_DIR

    inv = {v: k for k, v in _PT_DIR.items()}
    rows: list[dict[str, Any]] = []
    files = 0
    netler_dir = raw_dir / "netler"
    if not netler_dir.exists():
        log("  raw/netler/ yok — net satırı yüklenmedi (net_profiles boş kalacak)")
        return rows
    for pt_dir in sorted(netler_dir.glob("*")):
        if not pt_dir.is_dir():
            continue
        puan_turu = inv.get(pt_dir.name, pt_dir.name)
        for year_dir in sorted(pt_dir.glob("*")):
            if not year_dir.is_dir():
                continue
            try:
                yil = int(year_dir.name)
            except ValueError:
                continue
            for page_file in sorted(year_dir.glob("*.json")):
                files += 1
                raw = json.loads(page_file.read_text(encoding="utf-8"))
                for item in raw.get("content") or []:
                    item.setdefault("_fetch_puan_turu", puan_turu)
                    item.setdefault("_fetch_yil", yil)
                    rows.append(item)
    log(f"  raw/netler/'ten {files} sayfa, {len(rows)} net satırı yüklendi")
    return rows


def _resolve_single(explicit: str | None, glob_pattern: str, log: Logger, label: str) -> Path | None:
    """Açık yol verilmişse onu, yoksa HERE altındaki glob'un TEK eşleşmesini döner."""
    if explicit:
        p = Path(explicit)
        if not p.exists():
            log(f"  [uyarı] {label} bulunamadı: {p}")
            return None
        return p
    matches = sorted(HERE.glob(glob_pattern))
    if not matches:
        log(f"  [uyarı] {label} yok ({glob_pattern}) — çapraz kontrol atlanır")
        return None
    if len(matches) > 1:
        log(f"  [uyarı] {label} için {len(matches)} eşleşme, en yenisi kullanılıyor: {matches[-1].name}")
        return max(matches, key=lambda m: m.stat().st_mtime)
    return matches[0]


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _promote(dist_tmp: Path, dist: Path, log: Logger) -> None:
    """dist.tmp/ artefaktlarını atomik biçimde dist/'e taşır (fold_fixture korunur).
    nos.db promote sonrası yazma-korumalı (0o444) yapılır: kazara WAL açılmasını
    engeller (sqlite3 read-only açar), böylece dosya hash'i sabit kalır (docs §3.4)."""
    dist.mkdir(parents=True, exist_ok=True)
    for artifact in ("programs.json", "nos.db", "meta.json", "validation_report.md",
                     "discrepancy_report.md"):
        src = dist_tmp / artifact
        if src.exists():
            dst = dist / artifact
            if dst.exists() and not os.access(dst, os.W_OK):
                dst.chmod(0o644)  # önceki koşudan 0o444 kalmışsa replace için aç
            tmp = dist / (artifact + ".swap")
            tmp.write_bytes(src.read_bytes())
            tmp.replace(dst)  # aynı dosya sistemi -> atomik rename
            if artifact == "nos.db":
                # Bayat WAL/journal yan dosyalarını temizle: yeni DB'ye BAŞKA bir
                # DB'nin -wal'ı uygulanırsa bozulma olur (bir verify süreci açmıştı).
                for suf in ("-wal", "-shm", "-journal"):
                    side = dist / (artifact + suf)
                    if side.exists():
                        side.unlink()
                        log(f"  bayat yan dosya silindi: {artifact}{suf}")
            if artifact in ("nos.db", "meta.json"):
                dst.chmod(0o444)  # yazma-korumalı (docs §3.4): nos.db WAL geçişini,
                                  # meta.json kazara değişikliği engeller
            log(f"  promoted: {artifact}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NOS veri pipeline")
    parser.add_argument("--until", choices=_PHASE_ORDER, default="test",
                        help="Bu faza kadar koş (dahil). Varsayılan: test (tam koşu).")
    parser.add_argument("--only", default=None,
                        help="Yalnız bu puan türünü çek (SAY/EA/SÖZ/DİL/TYT) — bounded test.")
    parser.add_argument("--max-pages", type=int, default=None,
                        help="Kombo başına maksimum sayfa — bounded test.")
    parser.add_argument("--skip-fetch", action="store_true",
                        help="Ağ yerine raw/'tan yükle (idempotans testi).")
    parser.add_argument("--skip-netler", action="store_true",
                        help="Net çekimini atla (net_profiles boş kalır; dev iterasyonu).")
    parser.add_argument("--fetch-netler-only", action="store_true",
                        help="K1'i raw/'tan yükle, ağdan YALNIZ eksik net yıllarını çek "
                             "(tamamlanmış yıllar önbellekten gelir). Yerleştirme yılı aynı kalıp "
                             "netler sonradan yayınlandığında kullanılır; YÖK Atlas'a en az istek "
                             "(netler hâlâ yoksa puan türü başına 1).")
    parser.add_argument("--allow-missing-k2", action="store_true",
                        help="K2 (ÖSYM kılavuzu) yoksa/parse hata verirse rapor amaçlı devam "
                             "(guideCoveragePct kapısı atlanır; dist yine gerçek PASS ile üretilir).")
    parser.add_argument("--kilavuz-pdf", default=None,
                        help=f"ÖSYM kılavuz PDF yolu (varsayılan: {DEFAULT_KILAVUZ_PDF}).")
    parser.add_argument("--skip-kilavuz", action="store_true",
                        help="Kılavuz parse'ını tamamen atla (K1-only; dev iterasyonu, 793 "
                             "sayfa parse ~1dk sürer).")
    parser.add_argument("--kilavuz-xls-t3", default=None,
                        help=f"Kılavuz Tablo 3 (önlisans) XLS yolu (varsayılan glob: {DEFAULT_KILAVUZ_XLS_T3_GLOB}).")
    parser.add_argument("--kilavuz-xls-t4", default=None,
                        help=f"Kılavuz Tablo 4 (lisans) XLS yolu (varsayılan glob: {DEFAULT_KILAVUZ_XLS_T4_GLOB}).")
    parser.add_argument("--skip-xls", action="store_true",
                        help="Kılavuz XLS çapraz kontrolünü atla (yalnız rapor etkilenir).")
    parser.add_argument("--kilavuz-tablo-kaynak", choices=("pdf", "xls"), default="pdf",
                        help="Tablo 3/4 program alanları (kontenjan/koşul/süre/PT/ok.birincisi/şehit-gazi/"
                             "34 yaş/TYÇ/akreditasyon/önceki yıl sıra-puan) için otoriter kaynak. "
                             "Varsayılan pdf (karar 2026-09-13); xls seçilirse XLS yazılır, PDF yalnız "
                             "koşul sözlüğü/Tablo 1B/ücret/web adresi sağlar ve PDF↔XLS raporu yine üretilir.")
    parser.add_argument("--history-archive", default=None,
                        help=f"Tarihsel yearly_stats arşivi (varsayılan: {DEFAULT_HISTORY_ARCHIVE}).")
    parser.add_argument("--skip-archive", action="store_true",
                        help="Arşiv doldurmasını atla (API'den düşen yıllar — ör. 2022 — DB'ye girmez).")
    args = parser.parse_args(argv)

    until_idx = _PHASE_ORDER.index(args.until)
    run_ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    log = Logger(LOGS_DIR / f"run-{run_ts}.log")
    t0 = time.time()
    log(f"=== NOS pipeline başladı (until={args.until}, only={args.only}, "
        f"max_pages={args.max_pages}, skip_fetch={args.skip_fetch}) ===")

    DIST_TMP.mkdir(parents=True, exist_ok=True)
    timings: dict[str, float] = {}

    try:
        # --- fold fixture (statik sözleşme, ağdan bağımsız) ---
        from pipeline.turkish import write_fixture
        fx = write_fixture(DIST_DIR / "fold_fixture.json")
        log(f"  fold_fixture hazır: {fx}")

        # --- FETCH ---
        from pipeline.fetch import fetch_k1, SEARCH_COMBOS
        from pipeline.fetch_netler import fetch_netler
        ts = time.time()
        combos = SEARCH_COMBOS
        if args.only:
            pt = args.only.strip().upper().replace("SOZ", "SÖZ").replace("DIL", "DİL")
            combos = [c for c in SEARCH_COMBOS if c[0] == pt]
            if not combos:
                log(f"  [HATA] --only {args.only!r} geçersiz. Seçenekler: SAY/EA/SÖZ/DİL/TYT")
                return 2
        if args.fetch_netler_only and (args.skip_fetch or args.skip_netler):
            log("  [HATA] --fetch-netler-only, --skip-fetch/--skip-netler ile birlikte kullanılamaz.")
            return 2
        if args.skip_fetch:
            k1_programs = _load_raw_k1(RAW_DIR, log)
            net_raw_rows = [] if args.skip_netler else _load_raw_netler(RAW_DIR, log)
        elif args.fetch_netler_only:
            k1_programs = _load_raw_k1(RAW_DIR, log)
            if args.only:
                # K1 raw'dan tümü yüklendiği için net tarafı da tüm puan türlerini kapsar.
                log("  [uyarı] --fetch-netler-only ile --only yok sayıldı (K1 raw'dan tam yüklenir).")
            log("FETCH NETLER (yalnız eksik yıllar; K1 raw'dan)...")
            net_raw_rows, net_pages, net_per_combo = fetch_netler(
                RAW_DIR, combos=SEARCH_COMBOS, max_pages=args.max_pages, logf=log)
            log(f"  Net toplam: {len(net_raw_rows)} satır, {net_pages} sayfa (ağ), "
                f"kombo={net_per_combo}")
        else:
            log("FETCH (K1: YÖK Atlas)...")
            k1_programs, pages, per_combo = fetch_k1(
                RAW_DIR, combos=combos, max_pages=args.max_pages, logf=log)
            log(f"  K1 toplam: {len(k1_programs)} kayıt, {pages} sayfa, kombo={per_combo}")
            if args.skip_netler:
                net_raw_rows = []
                log("  [net] --skip-netler: net çekimi atlandı (net_profiles boş kalacak)")
            else:
                log("FETCH NETLER (Net Sihirbazı — brief §10)...")
                net_raw_rows, net_pages, net_per_combo = fetch_netler(
                    RAW_DIR, combos=combos, max_pages=args.max_pages, logf=log)
                log(f"  Net toplam: {len(net_raw_rows)} satır, {net_pages} sayfa (ağ), "
                    f"kombo={net_per_combo}")
        # K2 — ÖSYM 2026 kılavuzu (ARTIK OTORİTER, bkz. plan). --skip-kilavuz ile
        # tamamen atlanabilir (dev iterasyonu); parse hatası --allow-missing-k2
        # olmadan FAIL'e düşürür (aşağıda guideCoveragePct kapısı).
        guide = None
        k2_note = "Kılavuz parse edilmedi (--skip-kilavuz)."
        if not args.skip_kilavuz:
            from pipeline.parse_kilavuz import parse_kilavuz
            kilavuz_pdf = Path(args.kilavuz_pdf) if args.kilavuz_pdf else DEFAULT_KILAVUZ_PDF
            if not kilavuz_pdf.exists():
                k2_note = f"K2 atlandı: kılavuz PDF bulunamadı ({kilavuz_pdf})."
                log(f"  [uyarı] {k2_note}")
                if not args.allow_missing_k2:
                    log("  [HATA] Kılavuz PDF yok ve --allow-missing-k2 verilmedi.")
                    return 2
            else:
                log(f"FETCH K2 (ÖSYM kılavuzu: {kilavuz_pdf})...")
                try:
                    guide = parse_kilavuz(kilavuz_pdf, logf=log)
                    k2_note = (f"K2 (OTORİTER): {guide.stats.get('guideProgramCount')} program, "
                               f"{guide.stats.get('dictCodeCount')} koşul kodu, "
                               f"{guide.stats.get('feeRowCount')} ücret satırı parse edildi.")
                except Exception as exc:  # noqa: BLE001 - parse hatası kritik, ama --allow ile geçilebilir
                    k2_note = f"K2 parse hatası: {exc}"
                    log(f"  [HATA] {k2_note}")
                    if not args.allow_missing_k2:
                        return 2
        # K2 XLS — kılavuz Tablo 3/4'ün ÖSYM XLS sürümü, YALNIZ çapraz kontrol
        # (PDF otoriter kalır; sonuç discrepancy_report.md + validate yumuşak uyarı).
        xls_programs = None
        if guide is not None and not args.skip_xls:
            from pipeline.parse_kilavuz_xls import parse_kilavuz_xls
            t3 = _resolve_single(args.kilavuz_xls_t3, DEFAULT_KILAVUZ_XLS_T3_GLOB, log, "Tablo 3 XLS")
            t4 = _resolve_single(args.kilavuz_xls_t4, DEFAULT_KILAVUZ_XLS_T4_GLOB, log, "Tablo 4 XLS")
            if t3 or t4:
                try:
                    xls_programs = parse_kilavuz_xls(t3, t4, logf=log)
                except Exception as exc:  # noqa: BLE001 - çapraz kontrol kritik değil
                    log(f"  [uyarı] kılavuz XLS parse hatası, çapraz kontrol atlandı: {exc}")
        pdf_programs = guide.programs if guide is not None else None
        if guide is not None and xls_programs and args.kilavuz_tablo_kaynak == "xls":
            # XLS otoriter: kod bazında XLS kazanır; yalnız PDF'te olan kodlar korunur.
            guide.programs = {**pdf_programs, **xls_programs}
            guide.stats["tabloKaynak"] = "xls"
            log(f"  [kilavuz] Tablo 3/4 kaynağı: XLS ({len(xls_programs)} program; PDF yalnız "
                f"{len(set(pdf_programs) - set(xls_programs))} kodda kaldı)")
            k2_note += " Tablo 3/4 alanları XLS'ten (PDF yalnız sözlük/1B/ücret/web)."
        elif guide is not None:
            guide.stats["tabloKaynak"] = "pdf"
        timings["fetch"] = time.time() - ts

        # --- Tarihsel arşiv (API'den düşen yıllar için yalnız doldurma) ---
        from pipeline.merge import (load_history_archive, merge, merge_netler,
                                    write_programs_json, write_discrepancy_report)
        history = None
        if not args.skip_archive:
            archive_path = Path(args.history_archive) if args.history_archive else DEFAULT_HISTORY_ARCHIVE
            if archive_path.exists():
                history, arch_meta = load_history_archive(archive_path)
                log(f"  arşiv yüklendi: {archive_path.name} — {len(history)} program, "
                    f"yıllar {arch_meta.get('years')}, kaynak {arch_meta.get('sourceExportedAt')}")
            else:
                log(f"  [uyarı] arşiv yok ({archive_path}); API'den düşen yıllar DB'ye girmeyecek")

        # --- MERGE ---
        ts = time.time()
        log("MERGE + DEDUP...")
        result = merge(k1_programs, guide=guide, history=history, xls_programs=xls_programs,
                       xls_check_base=pdf_programs, logf=log)
        write_discrepancy_report(result, DIST_TMP / "discrepancy_report.md")
        known_kilavuz_kodlari = {r["id"] for r in result.records}
        net_rows, net_stats = merge_netler(net_raw_rows, known_kilavuz_kodlari, logf=log)
        exported_at = _iso_now()
        sha = write_programs_json(result, DIST_TMP / "programs.json", exported_at=exported_at,
                                  schema_version=SCHEMA_VERSION)
        (DIST_TMP / "meta.json").write_text(
            json.dumps({
                "exportedAt": exported_at,
                "sha256_json": sha,
                "schemaVersion": SCHEMA_VERSION,
                "programCount": result.stats["programCount"],
                "dataYear": RESULT_YEAR,
                "k2Note": k2_note,
                "stats": result.stats,
                "netStats": net_stats,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log(f"  programs.json yazıldı (dist.tmp), sha256={sha[:16]}... n={result.stats['programCount']}")
        timings["merge"] = time.time() - ts

        if until_idx < _PHASE_ORDER.index("validate"):
            log(f"  --until={args.until}: fetch+merge tamamlandı, sonraki fazlar atlandı.")
            _summary(log, result.stats, timings, t0, promoted=False, net_stats=net_stats)
            return 0

        # --- VALIDATE / BUILD / TEST (Faz 3–5, Task #2) ---
        try:
            from pipeline import validate as validate_mod
            from pipeline import build_sqlite as build_mod
            from pipeline import tests as tests_mod
        except ImportError as exc:
            log(f"  [BEKLEMEDE] validate/build/test modülleri henüz yok (Task #2): {exc}")
            log("  fetch+merge çıktıları dist.tmp/ altında hazır; tam koşu Task #2'de aktifleşecek.")
            _summary(log, result.stats, timings, t0, promoted=False, net_stats=net_stats)
            return 0

        ts = time.time()
        log("VALIDATE...")
        ok, report = validate_mod.validate(result, allow_missing_k2=args.allow_missing_k2, logf=log)
        (DIST_TMP / "validation_report.md").write_text(report, encoding="utf-8")
        timings["validate"] = time.time() - ts
        if not ok:
            log("  [FAIL] VALIDATE başarısız — dist/ DEĞİŞMEDİ. validation_report.md'ye bakın.")
            _summary(log, result.stats, timings, t0, promoted=False, net_stats=net_stats)
            return 1

        ts = time.time()
        log("BUILD SQLITE...")
        db_sha = build_mod.build(result, DIST_TMP / "nos.db", exported_at=exported_at,
                                 json_sha=sha, schema_version=SCHEMA_VERSION,
                                 net_profiles=net_rows, logf=log)
        timings["build"] = time.time() - ts

        ts = time.time()
        log("TEST...")
        ok_t, test_report = tests_mod.run_tests(
            DIST_TMP / "nos.db", result, net_stats=net_stats, logf=log)
        timings["test"] = time.time() - ts
        if not ok_t:
            log("  [FAIL] TEST başarısız — dist/ DEĞİŞMEDİ.")
            (DIST_TMP / "validation_report.md").write_text(report + "\n\n" + test_report, encoding="utf-8")
            _summary(log, result.stats, timings, t0, promoted=False, net_stats=net_stats)
            return 1

        # sha256_db'yi TÜM DB açma işlemlerinden (build+test) SONRA, son adım olarak
        # hesapla (docs §3.4). Yan dosya kalıntısı varsa hata ver.
        build_mod.assert_no_sidecars(DIST_TMP / "nos.db")
        db_sha_final = build_mod.file_sha256(DIST_TMP / "nos.db")
        if db_sha_final != db_sha:
            log(f"  [not] nos.db build sonrası dokunuldu (sha {db_sha[:12]}→{db_sha_final[:12]}); "
                f"son değer kullanılıyor")
        (DIST_TMP / "meta.json").write_text(
            json.dumps({
                "exportedAt": exported_at,
                "sha256_json": sha,
                "sha256_db": db_sha_final,
                "schemaVersion": SCHEMA_VERSION,
                "programCount": result.stats["programCount"],
                "dataYear": RESULT_YEAR,
                "k2Note": k2_note,
                "stats": result.stats,
                "netStats": net_stats,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (DIST_TMP / "validation_report.md").write_text(report + "\n\n" + test_report, encoding="utf-8")

        # --- PROMOTE (tüm kapılar geçti) ---
        _promote(DIST_TMP, DIST_DIR, log)
        _summary(log, result.stats, timings, t0, promoted=True, net_stats=net_stats)
        return 0

    except Exception as exc:  # noqa: BLE001
        import traceback
        log(f"  [HATA] pipeline çöktü: {exc}")
        log(traceback.format_exc())
        return 1
    finally:
        log.close()


def _summary(log: Logger, stats: dict[str, Any], timings: dict[str, float],
             t0: float, *, promoted: bool, net_stats: dict[str, Any] | None = None) -> None:
    log("=== ÖZET ===")
    log(f"  programCount: {stats.get('programCount')}")
    log(f"  duplicatesDropped: {stats.get('duplicatesDropped')}")
    log(f"  null sonSiralama: {stats.get('nullSonSiralama')} (%{stats.get('nullSonSiralamaPct')})")
    log(f"  3-yıl dolu ({stats.get('trendYears')}): {stats.get('full3YearCount')} (%{stats.get('full3YearPct')}) | "
        f"son_yil dağılımı: {stats.get('sonYilDist')} | arşiv: +{stats.get('archiveRowsAdded')} satır, "
        f"{stats.get('archiveFieldsFilled')} alan, {stats.get('archiveConflicts')} çakışma")
    log(f"  karma-tür şüphesi: {stats.get('mixedSuspectCount')} | trend-yukselen: {stats.get('trendYukselenCount')}")
    log(f"  kosulSozluk: {stats.get('kosulSozlukCount')} | baraj: {stats.get('barajCount')}")
    log(f"  uniTur dağılımı: {stats.get('uniTurDist')}")
    log(f"  puanTuru dağılımı: {stats.get('puanTuruDist')}")
    if net_stats is not None:
        log(f"  net_profiles: {net_stats.get('netRowCount')} satır | "
            f"eşleşme %{net_stats.get('eslesmeOrani')} | "
            f"dup {net_stats.get('dedupCount')} | "
            f"negatif {net_stats.get('negatifCount')} | aralık-dışı {net_stats.get('aralikDisiCount')}")
    log(f"  faz süreleri (s): { {k: round(v, 1) for k, v in timings.items()} }")
    log(f"  toplam süre: {round(time.time() - t0, 1)}s | dist/ promote edildi: {promoted}")


if __name__ == "__main__":
    sys.exit(main())
