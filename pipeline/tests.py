"""TEST — nos.db üzerinde zorunlu test paketi (brief §9 + plan §5 Faz 5).

Motor simülasyonu brief §7 banding sözleşmesini birebir uygular (TS engine.ts ile
aynı sözleşme). Herhangi bir test FAIL -> (False, rapor); run.py dist'i taşımaz.
"""

from __future__ import annotations

import random
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable

from .years import ALL_YEARS, RESULT_YEAR, years_sql_in

from .merge import MergeResult

# Ana sihirbaz sorgusu (plan §4). :mtok_ok, :s parametreli.
_WIZARD_SQL = """
SELECT id, grup, ogr_tur, mtok, kktc_uyruklu, kont2026, son_siralama, puan_turu
FROM programs
WHERE puan_turu = :pt AND kont2026 IS NOT NULL
  AND (:include_aof = 1 OR ogr_tur NOT IN ('Açıköğretim','Uzaktan'))
  AND mtok <= :mtok_ok AND kktc_uyruklu = 0
  AND (son_siralama IS NULL OR son_siralama * 1.11 >= :s)
ORDER BY CASE WHEN son_siralama IS NULL THEN 1 ELSE 0 END, son_siralama
"""

# 5 sentetik profil: (puan_turu, kullanıcı_sırası S)
_PROFILES = [("SAY", 15000), ("EA", 80000), ("SÖZ", 120000), ("DİL", 30000), ("TYT", 400000)]


def _log(logf: Callable[[str], None] | None, msg: str) -> None:
    if logf:
        logf(msg)


def _band(S: int, P: int | None, cfg: dict[str, float]) -> str:
    """Brief §7 banding. P=None -> Güven (dolmadı)."""
    if P is None:
        return "Güven"
    if S < P * cfg["guven_carpan"]:
        return "Güven"
    if S <= P * cfg["denge_ust"]:
        return "Denge"
    if S <= P * cfg["hedef_ust"]:
        return "Hedef"
    return "Liste dışı"


def _simulate(conn: sqlite3.Connection, pt: str, S: int, cfg: dict[str, float],
              baraj: dict[str, int], *, include_aof: bool = False,
              mtok_ok: int = 0) -> list[tuple[dict[str, Any], str]]:
    """Motor: ana sorgu + K-2 baraj dışlaması + bant ataması."""
    conn.row_factory = sqlite3.Row
    rows = conn.execute(_WIZARD_SQL, {
        "pt": pt, "s": S, "mtok_ok": mtok_ok, "include_aof": 1 if include_aof else 0,
    }).fetchall()
    out: list[tuple[dict[str, Any], str]] = []
    for row in rows:
        b = baraj.get(row["grup"])
        if b is not None and S > b:  # kullanıcı barajı geçemiyor -> grubu sert dışla
            continue
        band = _band(S, row["son_siralama"], cfg)
        if band == "Liste dışı":
            continue
        out.append((dict(row), band))
    return out


def run_tests(db_path: str | Path, result: MergeResult,
              *, net_stats: dict[str, Any] | None = None,
              logf: Callable[[str], None] | None = None) -> tuple[bool, str]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    fails: list[str] = []
    lines: list[str] = ["# NOS Veri Test Raporu (TEST)", ""]

    def ok(name: str, cond: bool, detail: str = "") -> None:
        lines.append(f"- {'✅' if cond else '❌'} {name}{(' — ' + detail) if detail else ''}")
        if not cond:
            fails.append(name)

    try:
        cfg = {k: v for k, v in conn.execute("SELECT key,value FROM config")}
        baraj: dict[str, int] = {}
        for r in conn.execute("SELECT grup_pattern,baraj_sira FROM baraj"):
            baraj[r["grup_pattern"]] = int(r["baraj_sira"])

        # --- Bütünlük ---
        lines.append("## Bütünlük")
        db_n = conn.execute("SELECT COUNT(*) c FROM programs").fetchone()["c"]
        ok("JSON satır == programs", db_n == len(result.records),
           f"db={db_n} json={len(result.records)}")
        meta_n = int(conn.execute("SELECT value FROM meta WHERE key='programCount'").fetchone()["value"])
        ok("meta.programCount == programs", meta_n == db_n, f"meta={meta_n}")
        orphan = conn.execute(
            "SELECT COUNT(*) c FROM yearly_stats y LEFT JOIN programs p ON p.id=y.program_id "
            "WHERE p.id IS NULL").fetchone()["c"]
        ok("yearly_stats FK eksiksiz", orphan == 0, f"yetim={orphan}")
        bad_year = conn.execute(
            f"SELECT COUNT(*) c FROM yearly_stats WHERE yil NOT IN ({years_sql_in(ALL_YEARS)})").fetchone()["c"]
        ok(f"yearly_stats yıl ∈ {{{ALL_YEARS[0]}..{ALL_YEARS[-1]}}}", bad_year == 0, f"bad={bad_year}")
        # 2026-07-25 olayı sonrası (bkz. VERI_NOTLARI §1.3): son_siralama, son_yil
        # yılının yearly_stats sırasıyla birebir aynı olmalı; kılavuz-parse bulaşması
        # (filigran sayı bölmesi) bunu bozmuştu (Erciyes Makine 154725 -> 1).
        sira_drift = conn.execute(
            "SELECT COUNT(*) c FROM programs p JOIN yearly_stats y "
            "ON y.program_id = p.id AND y.yil = p.son_yil "
            "WHERE p.son_siralama IS NOT NULL AND y.sira IS NOT NULL "
            "AND p.son_siralama != y.sira").fetchone()["c"]
        ok("son_siralama == yearly_stats(son_yil).sira", sira_drift == 0, f"uyumsuz={sira_drift}")
        # son_yil, sırası dolu en güncel yıl olmalı (yıl geçişinde son* yeniden türetildi mi?)
        stale_son = conn.execute(
            "SELECT COUNT(*) c FROM programs p WHERE p.son_yil IS NOT NULL AND EXISTS ("
            "SELECT 1 FROM yearly_stats y WHERE y.program_id = p.id AND y.sira IS NOT NULL "
            "AND y.yil > p.son_yil)").fetchone()["c"]
        ok("son_yil = sırası dolu en güncel yıl", stale_son == 0, f"bayat={stale_son}")
        ry = conn.execute(
            "SELECT COUNT(*) c FROM yearly_stats WHERE yil = ? AND sira IS NOT NULL",
            (RESULT_YEAR,)).fetchone()["c"]
        ok(f"{RESULT_YEAR} sonuç satırı var (sira dolu > 10000)", ry > 10000, f"n={ry}")
        ry_son = conn.execute(
            "SELECT COUNT(*) c FROM programs WHERE son_yil = ?", (RESULT_YEAR,)).fetchone()["c"]
        lines.append(f"- son_yil={RESULT_YEAR} olan program: {ry_son}/{db_n} "
                     f"(%{round(100*ry_son/db_n, 2) if db_n else 0})")
        meta_year = conn.execute("SELECT value FROM meta WHERE key='dataYear'").fetchone()["value"]
        ok(f"meta.dataYear == {RESULT_YEAR}", meta_year == str(RESULT_YEAR), f"meta={meta_year}")
        elite_bad = conn.execute(
            "SELECT COUNT(*) c FROM programs WHERE son_siralama IS NOT NULL "
            "AND son_siralama <= 2000 AND son_puan IS NOT NULL AND son_puan < 400").fetchone()["c"]
        ok("elit tutarlılık (sıra≤2000 ⇒ puan≥400)", elite_bad == 0, f"ihlal={elite_bad}")

        # --- Şema/tip ---
        lines.append("")
        lines.append("## Şema / Tip")
        empty = conn.execute(
            "SELECT COUNT(*) c FROM programs WHERE uni='' OR prog='' OR grup='' OR il='' "
            "OR uni_norm='' OR prog_norm='' OR grup_norm=''").fetchone()["c"]
        ok("boş string yok", empty == 0, f"boş={empty}")
        bad_puan = conn.execute(
            "SELECT COUNT(*) c FROM yearly_stats WHERE puan IS NOT NULL "
            "AND (puan<100 OR puan>560)").fetchone()["c"]
        ok("puan ∈ [100,560] veya NULL", bad_puan == 0, f"bad={bad_puan}")
        bad_sira = conn.execute(
            "SELECT COUNT(*) c FROM yearly_stats WHERE sira IS NOT NULL AND sira<=0").fetchone()["c"]
        ok("sira >0 veya NULL", bad_sira == 0, f"bad={bad_sira}")

        # schema v2 ek nullable kolonlar: boş string yok (NULL kullanılmalı) + doluluk
        empty_v2 = conn.execute(
            "SELECT COUNT(*) c FROM programs WHERE akreditasyon='' OR akreditasyon_ack='' "
            "OR uni_akreditasyon=''").fetchone()["c"]
        ok("v2 TEXT alanları boş string değil (NULL)", empty_v2 == 0, f"boş={empty_v2}")
        bad_kadro = conn.execute(
            "SELECT COUNT(*) c FROM programs WHERE (prof IS NOT NULL AND prof<0) "
            "OR (doc IS NOT NULL AND doc<0) OR (dou IS NOT NULL AND dou<0) "
            "OR (ar_gor IS NOT NULL AND ar_gor<0)").fetchone()["c"]
        ok("akademik kadro sayıları >=0 veya NULL", bad_kadro == 0, f"bad={bad_kadro}")
        osym_nonnull = conn.execute(
            "SELECT COUNT(*) c FROM programs WHERE osym_kilavuz_id IS NOT NULL").fetchone()["c"]
        ok("osym_kilavuz_id kolonu dolu (v2 wiring)", osym_nonnull > 0, f"dolu={osym_nonnull}")

        # schema v3 (ÖSYM 2026 kılavuzu, K2 otoriter) — boş string yok + aralık + wiring
        empty_v3 = conn.execute(
            "SELECT COUNT(*) c FROM programs WHERE ucret_aciklama='' OR tyc='' "
            "OR uni_web=''").fetchone()["c"]
        ok("v3 TEXT alanları boş string değil (NULL)", empty_v3 == 0, f"boş={empty_v3}")
        bad_kont_v3 = conn.execute(
            "SELECT COUNT(*) c FROM programs WHERE (ucret IS NOT NULL AND ucret < 0) "
            "OR (kont_sehit_gazi IS NOT NULL AND kont_sehit_gazi < 0) "
            "OR (kont_okul_birincisi IS NOT NULL AND kont_okul_birincisi < 0)").fetchone()["c"]
        ok("v3 kontenjan/ücret alanları >=0 veya NULL", bad_kont_v3 == 0, f"bad={bad_kont_v3}")
        vakif_ucret = conn.execute(
            "SELECT COUNT(*) c FROM programs WHERE uni_tur IN ('VAKIF','KKTC') "
            "AND ucret IS NOT NULL").fetchone()["c"]
        if "guideCoveragePct" not in result.stats:
            lines.append("- ⏭️ SKIPPED — kılavuz (K2) bu koşuda uygulanmadı, ücret wiring testi atlandı.")
        else:
            ok("en az bir VAKIF/KKTC programında ucret dolu (v3 wiring)", vakif_ucret > 0,
               f"dolu={vakif_ucret}")

        # --- Net Profilleri (schema v2, brief §10) ---
        lines.append("")
        lines.append("## Net Profilleri (schema v2, brief §10)")
        net_count = conn.execute("SELECT COUNT(*) c FROM net_profiles").fetchone()["c"]
        if net_count == 0:
            lines.append("- ⏭️ SKIPPED — net_profiles boş (muhtemelen --skip-netler). "
                         "programCount ve diğer kapılar etkilenmez.")
            _log(logf, "  net testleri SKIPPED (net_profiles boş)")
        else:
            _NET_FIELDS = [
                "tyt_trk_net", "tyt_sos_net", "tyt_mat_net", "tyt_fen_net",
                "ayt_mat_net", "ayt_fiz_net", "ayt_kim_net", "ayt_bio_net",
                "ayt_tde_net", "ayt_trh1_net", "ayt_cog1_net", "ayt_trh2_net",
                "ayt_cog2_net", "ayt_fel_net", "ayt_din_net", "ydt_ydil_net",
            ]
            lines.append(f"- net_profiles satır sayısı: **{net_count}**")

            # Eşleşme kapısı: ≥%90 YALNIZ birincil (en güncel) yıla uygulanır. Eski yıl
            # program kodları güncel kılavuzda olmadığından genel oran doğal olarak düşer
            # (2025 %92.6, 2024 %85.7, 2023 %77.3 — beklenen YÖK Atlas davranışı, düzeltilemez;
            # elenen satırlar zaten sorgulanamaz yetim). Genel + yıl-bazlı oranlar görünürlük
            # için loglanır. merge_netler istatistiğinden — DB'de yalnız eşleşenler var.
            by_yil = net_stats.get("eslesmeOraniByYil") if net_stats else None
            overall = net_stats.get("eslesmeOrani") if net_stats else None
            if by_yil:
                primary_yil = max(by_yil)  # en güncel yıl = ürünün gösterdiği "yerleşen" referansı
                primary_rate = by_yil[primary_yil]
                lines.append(f"- eşleşme: genel %{overall} | yıl-bazlı {by_yil} "
                             f"(kapı yalnız birincil yıl {primary_yil})")
                ok(f"net eşleşme oranı (birincil yıl {primary_yil}) ≥ %90", primary_rate >= 90.0,
                   f"%{primary_rate} (genel eşleşen={net_stats.get('netMatched')}, "
                   f"eşleşmeyen={net_stats.get('netUnmatched')})")
            else:
                lines.append("- (net_stats/yıl-bazlı oran verilmedi — eşleşme oranı DB'den doğrulanamaz)")

            # FK bütünlüğü: yetim net satırı yok
            net_orphan = conn.execute(
                "SELECT COUNT(*) c FROM net_profiles n LEFT JOIN programs p "
                "ON p.id = n.kilavuz_kodu WHERE p.id IS NULL").fetchone()["c"]
            ok("net_profiles FK eksiksiz (DB)", net_orphan == 0, f"yetim={net_orphan}")

            # Değer aralığı: TYT/AYT netleri 0-40, YDT (ydt_ydil_net) 0-80 (80 soruluk
            # Yabancı Dil Testi). Negatif dahil aralık dışı → başarısızlık.
            bad_net_total = 0
            worst = []
            for col in _NET_FIELDS:
                hi = 80 if col == "ydt_ydil_net" else 40
                c = conn.execute(
                    f"SELECT COUNT(*) c FROM net_profiles "
                    f"WHERE {col} IS NOT NULL AND ({col} < 0 OR {col} > {hi})").fetchone()["c"]
                if c:
                    worst.append(f"{col}={c}")
                bad_net_total += c
            ok("*_net alanları aralıkta (TYT/AYT 0-40, YDT 0-80) veya NULL", bad_net_total == 0,
               f"aralık dışı={bad_net_total}{(' — ' + ', '.join(worst)) if worst else ''}")

            # OBP 100-500 veya NULL
            bad_obp = conn.execute(
                "SELECT COUNT(*) c FROM net_profiles "
                "WHERE obp IS NOT NULL AND (obp < 100 OR obp > 500)").fetchone()["c"]
            ok("obp 100-500 veya NULL", bad_obp == 0, f"bad={bad_obp}")

            # taban_puan negatif değil (varsa)
            bad_taban = conn.execute(
                "SELECT COUNT(*) c FROM net_profiles "
                "WHERE taban_puan IS NOT NULL AND taban_puan < 0").fetchone()["c"]
            ok("taban_puan negatif yok", bad_taban == 0, f"bad={bad_taban}")

            # Altın örnek: Boğaziçi Bilgisayar Müh., en güncel net yılı (elle doğrulama referansı)
            net_primary = conn.execute("SELECT MAX(yil) y FROM net_profiles").fetchone()["y"]
            bogazici = conn.execute(
                "SELECT id, prog, puan_turu FROM programs "
                "WHERE uni_norm LIKE '%bogazici%' AND prog_norm LIKE '%bilgisayar muhendisligi%' "
                "AND puan_turu='SAY' ORDER BY son_siralama LIMIT 1").fetchone()
            if bogazici is None:
                lines.append("- ⚠️ Boğaziçi Bilgisayar Müh. (SAY) programs'ta bulunamadı — altın örnek atlandı")
            else:
                np = conn.execute(
                    "SELECT * FROM net_profiles WHERE kilavuz_kodu=? AND yil=? "
                    "ORDER BY katsayi", (bogazici["id"], net_primary)).fetchall()
                if not np:
                    # birincil yıl yoksa herhangi bir yıl dene (bilgi amaçlı)
                    np_any = conn.execute(
                        "SELECT * FROM net_profiles WHERE kilavuz_kodu=? ORDER BY yil DESC, katsayi",
                        (bogazici["id"],)).fetchall()
                    ok("altın örnek: Boğaziçi Bilgisayar net profili mevcut",
                       len(np_any) > 0, f"kk={bogazici['id']} {net_primary} yok, toplam={len(np_any)} yıl-satırı")
                    np = np_any
                else:
                    ok(f"altın örnek: Boğaziçi Bilgisayar {net_primary} net profili mevcut",
                       len(np) > 0, f"kk={bogazici['id']} {len(np)} katsayi varyantı")
                if np:
                    sample = np[0]
                    filled = [f for f in _NET_FIELDS if sample[f] is not None]
                    ok("altın örnek: net alanları makul aralıkta (dolu + 0-40)",
                       len(filled) > 0 and all(0 <= sample[f] <= 40 for f in filled),
                       f"taban_puan={sample['taban_puan']} obp={sample['obp']} "
                       f"dolu_net={len(filled)}/16 örn: "
                       f"tyt_mat={sample['tyt_mat_net']} ayt_mat={sample['ayt_mat_net']}")
                    lines.append(f"  - ELLE DOĞRULAMA NOTU: Boğaziçi Bilgisayar (kk={bogazici['id']}) "
                                 f"{sample['yil']} → taban={sample['taban_puan']}, obp={sample['obp']}, "
                                 f"tyt(trk/sos/mat/fen)="
                                 f"{sample['tyt_trk_net']}/{sample['tyt_sos_net']}/"
                                 f"{sample['tyt_mat_net']}/{sample['tyt_fen_net']}, "
                                 f"ayt(mat/fiz/kim/bio)="
                                 f"{sample['ayt_mat_net']}/{sample['ayt_fiz_net']}/"
                                 f"{sample['ayt_kim_net']}/{sample['ayt_bio_net']} "
                                 f"— YÖK Atlas web ile karşılaştırın.")

        # --- Net Katsayı (schema v4, net_profiles ground-truth'una oturtulmuş
        # afin net→puan regresyonu — bkz. pipeline/net_katsayi.py) ---
        lines.append("")
        lines.append("## Net Katsayı (Regresyon)")
        katsayi_meta_rows = conn.execute(
            "SELECT yil, puan_turu, n, r2, rmse FROM net_katsayi_meta"
        ).fetchall()
        if not katsayi_meta_rows:
            lines.append("- ⏭️ SKIPPED — net_katsayi_meta boş (muhtemelen --skip-netler).")
            _log(logf, "  net_katsayi testleri SKIPPED (net_katsayi_meta boş)")
        else:
            min_r2 = min(r["r2"] for r in katsayi_meta_rows)
            ok("net_katsayi R² eşiği (tüm gruplar ≥ 0.90)", min_r2 >= 0.90, f"min_r2={min_r2:.4f}")

            # Her meta satırının net_katsayi'de karşılığı (intercept + obp dahil) var mı.
            missing = conn.execute(
                "SELECT COUNT(*) c FROM net_katsayi_meta m WHERE NOT EXISTS ("
                "  SELECT 1 FROM net_katsayi k WHERE k.yil=m.yil AND k.puan_turu=m.puan_turu "
                "  AND k.alan='intercept'"
                ")"
            ).fetchone()["c"]
            ok("net_katsayi_meta her satır için intercept katsayısı var", missing == 0,
               f"eksik={missing}")

            # FK-benzeri tutarlılık: net_katsayi'de meta'sı olmayan (yil,puan_turu) yok.
            orphan_katsayi = conn.execute(
                "SELECT COUNT(*) c FROM net_katsayi k WHERE NOT EXISTS ("
                "  SELECT 1 FROM net_katsayi_meta m WHERE m.yil=k.yil AND m.puan_turu=k.puan_turu"
                ")"
            ).fetchone()["c"]
            ok("net_katsayi tüm satırların net_katsayi_meta karşılığı var", orphan_katsayi == 0,
               f"yetim={orphan_katsayi}")

            for r in katsayi_meta_rows:
                lines.append(
                    f"  - {r['puan_turu']}/{r['yil']}: n={r['n']} R²={r['r2']:.4f} RMSE={r['rmse']:.2f}"
                )

        # --- Motor simülasyonu ---
        lines.append("")
        lines.append("## Motor Simülasyonu (5 profil)")
        profile_results: dict[str, list[tuple[dict, str]]] = {}
        for pt, S in _PROFILES:
            res = _simulate(conn, pt, S, cfg, baraj)
            profile_results[pt] = res
            bands = {}
            for _, b in res:
                bands[b] = bands.get(b, 0) + 1
            ok(f"{pt} S={S}: >0 sonuç", len(res) > 0, f"{len(res)} sonuç, bantlar={bands}")

        # 50 rastgele kayıt: bant yeniden hesap == motor
        pool = [(pt, row, b) for pt, res in profile_results.items() for row, b in res]
        sample = random.sample(pool, min(50, len(pool)))
        S_by_pt = dict(_PROFILES)
        band_mismatch = 0
        for pt, row, b in sample:
            expected = _band(S_by_pt[pt], row["son_siralama"], cfg)
            if expected != b:
                band_mismatch += 1
        ok("50 rastgele kayıt bant matematiği tutarlı", band_mismatch == 0, f"uyumsuz={band_mismatch}")

        # K-2: SAY 400k kullanıcı -> 0 Tıp
        say_400k = _simulate(conn, "SAY", 400000, cfg, baraj)
        tip_in = [r for r, _ in say_400k if r["grup"] == "Tıp"]
        ok("K-2 baraj: SAY 400k -> 0 Tıp", len(tip_in) == 0, f"Tıp={len(tip_in)}")

        # --- Negatif testler ---
        lines.append("")
        lines.append("## Negatif Testler")
        # kapanan (kont2026 NULL) motor sonucunda YOK
        null_kont_in_result = any(r["kont2026"] is None for r, _ in profile_results["SAY"])
        ok("kont2026 NULL sonuçta yok", not null_kont_in_result)
        # NULL sıra -> Güven
        null_sira_bands = {b for r, b in profile_results["SAY"] if r["son_siralama"] is None}
        ok("NULL sıra -> Güven", null_sira_bands <= {"Güven"},
           f"bantlar={null_sira_bands or '{yok}'}")
        # AÖF varsayılan dışı
        aof_default = [r for r, _ in profile_results["TYT"] if r["ogr_tur"] in ("Açıköğretim", "Uzaktan")]
        aof_total = conn.execute(
            "SELECT COUNT(*) c FROM programs WHERE ogr_tur IN ('Açıköğretim','Uzaktan')").fetchone()["c"]
        ok("AÖF/Uzaktan varsayılan dışı", len(aof_default) == 0, f"DB'de toplam AÖF/Uzaktan={aof_total}")
        # MTOK / kktc_uyruklu genel kullanıcıya kapalı
        mtok_in = [r for r, _ in profile_results["SAY"] if r["mtok"] == 1]
        kktcu_in = [r for r, _ in profile_results["SAY"] if r["kktc_uyruklu"] == 1]
        ok("MTOK genel kullanıcıya kapalı", len(mtok_in) == 0)
        ok("KKTC-uyruklu genel kullanıcıya kapalı", len(kktcu_in) == 0)

        # --- Türkçe fold arama (FTS) ---
        lines.append("")
        lines.append("## Türkçe Fold Arama (FTS5)")
        from .turkish import fold

        def fts_ids(query: str) -> set[int]:
            folded = fold(query)
            tokens = [f"{t}*" for t in folded.split() if t]
            if not tokens:
                return set()
            match = " ".join(tokens)
            return {r["rowid"] for r in conn.execute(
                "SELECT rowid FROM program_fts WHERE program_fts MATCH ?", (match,))}

        ids_upper = fts_ids("BİLGİSAYAR")
        ids_lower = fts_ids("bilgisayar")
        ids_ascii = fts_ids("bilgisayar muhendisligi".upper())
        ok("'BİLGİSAYAR'=='bilgisayar' (fold)", ids_upper == ids_lower and len(ids_lower) > 0,
           f"upper={len(ids_upper)} lower={len(ids_lower)}")
        ok("'BİLGİSAYAR MÜHENDİSLİĞİ' arama >0", len(ids_ascii) > 0, f"{len(ids_ascii)} sonuç")
        # İ/ı ayrımı: 'işletme' ve 'ISPARTA' fold farklı köklere gitmeli ama arama çalışmalı
        ok("'İşletme' araması >0", len(fts_ids("İşletme")) > 0)

        # --- Performans ---
        lines.append("")
        lines.append("## Performans (Python sqlite3, cihaz değil)")
        perf = _perf(conn)
        for label, ms in perf.items():
            lines.append(f"- {label}: **{ms:.2f} ms**")

    finally:
        conn.close()

    ok_all = not fails
    header = f"\n**TEST Sonucu: {'PASS ✅' if ok_all else 'FAIL ❌'}** ({len(fails)} fail)\n"
    lines.insert(1, header)
    _log(logf, f"  tests: {'PASS' if ok_all else 'FAIL'} — {len(fails)} başarısız")
    for f in fails:
        _log(logf, f"    FAIL: {f}")
    return ok_all, "\n".join(lines)


def _perf(conn: sqlite3.Connection) -> dict[str, float]:
    """Ana sorgu + 3 tipik filtre kombinasyonunu ölçer (ms)."""
    def timeit(sql: str, params: dict, repeat: int = 20) -> float:
        best = float("inf")
        for _ in range(repeat):
            t = time.perf_counter()
            conn.execute(sql, params).fetchall()
            best = min(best, (time.perf_counter() - t) * 1000)
        return best

    out = {}
    out["ana sorgu (SAY, S=15k)"] = timeit(_WIZARD_SQL,
        {"pt": "SAY", "s": 15000, "mtok_ok": 0, "include_aof": 0})
    out["ana sorgu + il filtresi"] = timeit(
        _WIZARD_SQL.replace("ORDER BY", "AND il=:il ORDER BY"),
        {"pt": "EA", "s": 80000, "mtok_ok": 0, "include_aof": 0, "il": "İSTANBUL"})
    out["ana sorgu + grup filtresi"] = timeit(
        _WIZARD_SQL.replace("ORDER BY", "AND grup=:grup ORDER BY"),
        {"pt": "SAY", "s": 50000, "mtok_ok": 0, "include_aof": 0, "grup": "Tıp"})
    out["FTS arama (prefix)"] = _time_fts(conn)
    return out


def _time_fts(conn: sqlite3.Connection) -> float:
    best = float("inf")
    for _ in range(20):
        t = time.perf_counter()
        conn.execute("SELECT rowid FROM program_fts WHERE program_fts MATCH ?",
                     ("bilgisayar*",)).fetchall()
        best = min(best, (time.perf_counter() - t) * 1000)
    return best
