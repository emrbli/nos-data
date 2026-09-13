"""VALIDATE — yayın kapısı (brief §6 + plan §5 Faz 3).

Herhangi bir SERT kapı FAIL -> (False, rapor); run.py exit 1 döner, dist/ dokunulmaz.
Yumuşak bulgular rapora yazılır ama yayını durdurmaz. K3/K4 çapraz-kaynak siteleri
programatik erişilemez -> SKIPPED (insan onayı şart) işaretlenir.
"""

from __future__ import annotations

from typing import Any, Callable

from .merge import MergeResult
from .years import GUIDE_RESULT_YEAR, RESULT_YEAR, TREND_YEARS

_TREND_LABEL = "+".join(str(y) for y in TREND_YEARS)  # rapor metni, ör. "2024+2025+2026"

_MIN_COUNT = 15000
_MAX_COUNT = 40000
_YEAR_INTEGRITY_MIN = 0.70
_KONT2026_MIN = 0.95  # kont2026 kapsaması (K2'siz koşuda düşerse FAIL, allow ile geçilir)
_PUAN_LO, _PUAN_HI = 100.0, 560.0
_ALL_PT = ["SAY", "EA", "SÖZ", "DİL", "TYT"]

# Kılavuz (K2, otoriter) kapıları — bkz. plan §5. Kapsama düşükse veya sapma
# oranı yüksekse (sütun kayması şüphesi) parse hatası riskini FAIL ile durdur;
# --allow-missing-k2 ile (yalnız rapor amaçlı) atlanabilir.
_GUIDE_COVERAGE_MIN = 0.98
_GUIDE_DISCREPANCY_MAX = 0.10  # skaler alan başına üzerine-yazma oranı üst sınırı
# "kosul" ÇOK-DEĞERLİ (liste) bir alan: tek bir eklenen/çıkarılan kod bile
# "sapma" sayılır (küme eşitliği), bu yüzden yapısal olarak skalerlerden daha
# duyarlıdır. Gerçek koşuda (2026-07-25) ~%15 çıktı; örnekler incelendiğinde
# hem taraf da GEÇERLİ kod içeriyor (ör. guide'ın eklediği 22/23/24 kodları
# kılavuzun kendi sözlüğünde "öğretim dili İngilizce/hazırlık" olarak
# tanımlı) — sütun kayması değil, K1 anlık görüntüsü ile güncel kılavuz
# arasında GERÇEK editöryal fark. Bu yüzden ayrı (daha yüksek) eşiği var;
# skaler alanlar (kont2026/sure/puanTuru/akreditasyon/sonSiralama/sonPuan)
# %10 kapısında kalır — onlarda spike gerçek sütun-kayması işaretidir.
_GUIDE_DISCREPANCY_MAX_BY_FIELD: dict[str, float] = {"kosul": 0.25}
_FEE_MATCH_WARN_MIN = 0.50     # yumuşak: ücret eşleşmesi bunun altındaysa uyar
_GOLD_BOGAZICI_CS_MAX = 10000  # altın ref üst sınırı (gerekçe: _golden_refs içindeki tarihçe)
_XLS_MISMATCH_WARN = 0.02      # yumuşak: PDF↔XLS sayısal alan farkı bunun üstündeyse uyar
_XLS_NUMERIC_FIELDS = {"kont2026", "sure", "puanTuru", f"sira{GUIDE_RESULT_YEAR}",
                       f"puan{GUIDE_RESULT_YEAR}"}


def _log(logf: Callable[[str], None] | None, msg: str) -> None:
    if logf:
        logf(msg)


def _pct(n: int, d: int) -> float:
    return round(100 * n / d, 2) if d else 0.0


def validate(
    result: MergeResult,
    *,
    allow_missing_k2: bool = False,
    logf: Callable[[str], None] | None = None,
) -> tuple[bool, str]:
    recs = result.records
    n = len(recs)
    fails: list[str] = []
    warns: list[str] = []
    lines: list[str] = []

    ids = [r["id"] for r in recs]
    unique_ok = len(ids) == len(set(ids))

    pt_dist: dict[str, int] = {}
    uni_tur_dist: dict[str, int] = {}
    onlisans = lisans = 0
    kont2026_present = 0
    year_present_3 = 0
    empty_str = 0
    yerlesen_gt_kont = 0
    puan_out = 0
    sure_out = 0
    for r in recs:
        pt_dist[r["puanTuru"]] = pt_dist.get(r["puanTuru"], 0) + 1
        uni_tur_dist[r["uniTur"]] = uni_tur_dist.get(r["uniTur"], 0) + 1
        if r["birimTur"] == "ONLISANS":
            onlisans += 1
        else:
            lisans += 1
        if r["kont2026"] is not None:
            kont2026_present += 1
        years_present = {y["y"] for y in r["yillar"]}
        if set(TREND_YEARS) <= years_present:
            year_present_3 += 1
        # boş string taraması (NOT NULL text alanları)
        for key in ("uni", "prog", "grup", "il", "puanTuru", "birimTur", "ogrTur",
                    "uniNorm", "progNorm", "grupNorm"):
            if r[key] == "":
                empty_str += 1
                break
        if r["sure"] is not None and not (2 <= r["sure"] <= 6):
            sure_out += 1
        for y in r["yillar"]:
            if y["p"] is not None and not (_PUAN_LO <= y["p"] <= _PUAN_HI):
                puan_out += 1
            if y["k"] is not None and y["z"] is not None and y["z"] > y["k"]:
                yerlesen_gt_kont += 1

    # --- SERT KAPILAR: son sonuç bütünlüğü (2026-07-25 olayı sonrası) ---
    # (a) son_yil = sırası dolu EN GÜNCEL yıl olmalı ve son_siralama o yılın
    #     yearly_stats.sira'sıyla BİREBİR aynı olmalı — fark = kılavuz-parse
    #     bulaşması (filigran sayı bölmesi 154725'i 1 yapmıştı, sihirbaz çökmüştü)
    #     veya yıl geçişinde son* yeniden türetilmemesi.
    # (b) elit tutarlılık: sıra ≤ 2000 iken puan < 400 OLAMAZ (gerçek veride
    #     sıra 2000 ⇒ puan ≥ ~429 (SÖZ tabanı) her puan türünde) — bölünmüş-rakam artığını yakalar.
    sira_mismatch = 0
    sira_mismatch_sample: list[str] = []
    elite_violation = 0
    elite_sample: list[str] = []
    for r in recs:
        filled_years = [row["y"] for row in r["yillar"] if row["s"] is not None]
        expected_son_yil = max(filled_years) if filled_years else None
        s_son = next((row["s"] for row in r["yillar"] if row["y"] == r["sonYil"]), None)
        if r["sonYil"] != expected_son_yil or (
            r["sonSiralama"] is not None and s_son is not None and r["sonSiralama"] != s_son
        ):
            sira_mismatch += 1
            if len(sira_mismatch_sample) < 10:
                sira_mismatch_sample.append(
                    f"{r['id']}: son_yil={r['sonYil']} (beklenen {expected_son_yil}) "
                    f"son={r['sonSiralama']} yil.s={s_son}")
        if (r["sonSiralama"] is not None and r["sonSiralama"] <= 2000
                and r["sonPuan"] is not None and r["sonPuan"] < 400.0):
            elite_violation += 1
            if len(elite_sample) < 10:
                elite_sample.append(f"{r['id']}: sıra={r['sonSiralama']} puan={r['sonPuan']}")
    if sira_mismatch:
        fails.append(f"Son sıra tutarlılığı: {sira_mismatch} kayıtta son_yil/son_siralama, "
                     f"yearly_stats ile uyumsuz (kılavuz-parse bulaşması veya yıl geçişi hatası). "
                     f"Örnek: {sira_mismatch_sample}")
    if elite_violation:
        fails.append(f"Elit tutarlılık: {elite_violation} kayıtta sıra ≤ 2000 ama puan < 400 "
                     f"(bölünmüş-rakam artığı şüphesi). Örnek: {elite_sample}")

    # --- SERT KAPILAR ---
    if not (_MIN_COUNT < n < _MAX_COUNT):
        fails.append(f"Hacim: programCount={n} beklenen ({_MIN_COUNT}, {_MAX_COUNT}) aralığında değil.")
    for pt in _ALL_PT:
        if pt_dist.get(pt, 0) <= 0:
            fails.append(f"Puan türü {pt}: 0 kayıt (her puan türünde >0 olmalı).")
    if uni_tur_dist.get("KKTC", 0) <= 0:
        fails.append("KKTC: 0 kayıt (KKTC>0 olmalı).")
    if onlisans <= 0:
        fails.append("Önlisans: 0 kayıt (önlisans>0 olmalı).")
    if not unique_ok:
        fails.append("Tekillik: kilavuz_kodu benzersizliği ihlal edildi.")
    yr_pct = _pct(year_present_3, n)
    if yr_pct < _YEAR_INTEGRITY_MIN * 100:
        fails.append(f"Yıl bütünlüğü: {_TREND_LABEL} dolu oran %{yr_pct} < %{int(_YEAR_INTEGRITY_MIN*100)}.")
    kont_pct = _pct(kont2026_present, n)
    if kont_pct < _KONT2026_MIN * 100 and not allow_missing_k2:
        fails.append(f"kont2026 kapsaması %{kont_pct} < %{int(_KONT2026_MIN*100)} "
                     f"(K2'siz kısmi koşu — --allow-missing-k2 ile rapor amaçlı geçilebilir).")

    # --- KILAVUZ (K2, OTORİTER) KAPILARI ---
    guide_lines: list[str] = []
    if "guideCoveragePct" in result.stats:
        cov = result.stats["guideCoveragePct"]
        guide_lines.append(f"- Kılavuz kapsaması: {result.stats.get('guideMatched')}/{n} (**%{cov}**, kapı ≥%{int(_GUIDE_COVERAGE_MIN*100)})")
        if cov < _GUIDE_COVERAGE_MIN * 100 and not allow_missing_k2:
            fails.append(f"Kılavuz kapsaması %{cov} < %{int(_GUIDE_COVERAGE_MIN*100)} "
                         f"(parse/bölüm-tespiti hatası şüphesi — --allow-missing-k2 ile rapor amaçlı geçilebilir).")
        over_pct = result.stats.get("guideOverwritePctByField", {})
        guide_lines.append(f"- Alan bazında üzerine-yazma oranı: {over_pct}  (kapı ≤%{int(_GUIDE_DISCREPANCY_MAX*100)}/alan)")
        for field, pct in over_pct.items():
            threshold = _GUIDE_DISCREPANCY_MAX_BY_FIELD.get(field, _GUIDE_DISCREPANCY_MAX)
            if pct > threshold * 100 and not allow_missing_k2:
                fails.append(f"Kılavuz sapma: alan '{field}' üzerine-yazma oranı %{pct} > "
                             f"%{int(threshold*100)} (sütun kayması şüphesi — "
                             f"--allow-missing-k2 ile rapor amaçlı geçilebilir).")
        xls_fields = result.stats.get("xlsMismatchByField")
        if xls_fields:
            guide_lines.append(f"- Kılavuz PDF↔XLS çapraz kontrol: ortak {result.stats.get('xlsCommonCount')} program, "
                               f"yalnız XLS {result.stats.get('xlsOnlyCount')}, yalnız PDF "
                               f"{result.stats.get('xlsPdfOnlyCount')}; alan farkı % "
                               f"{ {k: v['pct'] for k, v in xls_fields.items()} } (yumuşak eşik "
                               f"%{_XLS_MISMATCH_WARN*100:g} sayısal alanlarda)")
            for fname, d in xls_fields.items():
                if fname in _XLS_NUMERIC_FIELDS and d["pct"] > _XLS_MISMATCH_WARN * 100:
                    warns.append(f"PDF↔XLS sapma: alan '{fname}' %{d['pct']} > %{_XLS_MISMATCH_WARN*100:g} "
                                 f"({d['mismatch']}/{d['compared']}; discrepancy_report.md 'PDF ↔ XLS' bölümü).")
        elif "xlsProgramCount" in result.stats:
            guide_lines.append("- Kılavuz PDF↔XLS çapraz kontrol: karşılaştırılabilir alan yok.")
        fee_pct = result.stats.get("guideFeeMatchPct")
        if fee_pct is not None:
            guide_lines.append(f"- Vakıf/KKTC ücret eşleşmesi: **%{fee_pct}** (yumuşak eşik ≥%{int(_FEE_MATCH_WARN_MIN*100)})")
            if fee_pct < _FEE_MATCH_WARN_MIN * 100:
                warns.append(f"Ücret eşleşmesi düşük: %{fee_pct} < %{int(_FEE_MATCH_WARN_MIN*100)} "
                             f"(discrepancy_report.md'deki eşleşmeyen örneklere bakın).")
    else:
        guide_lines.append("- Kılavuz (K2) bu koşuda uygulanmadı (--skip-kilavuz / PDF yok / parse hatası).")
        if not allow_missing_k2:
            fails.append("Kılavuz (K2) uygulanmadı ve --allow-missing-k2 verilmedi — otoriter kaynak eksik.")

    # --- ALTIN REFERANS SETİ (§6.3) ---
    gold_lines, gold_fails, gold_warns = _golden_refs(recs)
    fails.extend(gold_fails)
    warns.extend(gold_warns)

    # --- YUMUŞAK BULGULAR ---
    if uni_tur_dist.get("YURTDISI", 0) == 0:
        warns.append("YURTDIŞI: 0 kayıt (uyarı — beklenen >0).")
    if empty_str:
        fails.append(f"Boş string: {empty_str} kayıtta NOT NULL text alanı boş (ya değer ya NULL olmalı).")
    if puan_out:
        warns.append(f"Puan aralığı: {puan_out} yıl-satırında puan [100,560] dışında (build null'lar).")
    if sure_out:
        warns.append(f"Süre aralığı: {sure_out} kayıtta sure [2,6] dışında (build null'lar).")
    if yerlesen_gt_kont:
        warns.append(f"yerlesen>kontenjan: {yerlesen_gt_kont} yıl-satırı (İÖ ek kontenjan istisnası — loglanır).")
    if result.stats.get("mixedSuspectCount"):
        warns.append(f"Karma puan türü şüphesi (K-1): {result.stats['mixedSuspectCount']} kayıt "
                     f"(trend dışı bırakıldı, gözden geçirilmeli).")
    if result.stats.get("uncoveredKosulCount"):
        warns.append(f"K-5 koşul kapsama: {result.stats['uncoveredKosulCount']} kullanılan koşul kodu "
                     f"açıklamasız (kapsama %{result.stats.get('kosulCodeCoveragePct')}). UI çıplak kod "
                     f"göstermemeli — örnek kodlar: {result.stats.get('uncoveredKosulSample')}")

    ok = not fails

    # --- RAPOR ---
    lines.append("# NOS Veri Doğrulama Raporu (VALIDATE)")
    lines.append("")
    lines.append(f"**Sonuç: {'PASS ✅' if ok else 'FAIL ❌'}**  ·  programCount={n}")
    lines.append("")
    lines.append("> İnsan onayı olmadan `assets/db/nos.db` GÜNCELLENMEZ (brief §6.7).")
    lines.append("")
    lines.append("## Hacim & Dağılım")
    lines.append(f"- Toplam program: **{n}**  (kapı: {_MIN_COUNT}–{_MAX_COUNT})")
    lines.append(f"- Lisans / Önlisans: {lisans} / {onlisans}")
    lines.append(f"- Puan türü dağılımı: {pt_dist}")
    lines.append(f"- Üniversite türü dağılımı: {uni_tur_dist}")
    lines.append(f"- Tekillik (kilavuz_kodu): {'OK' if unique_ok else 'İHLAL'} ({len(set(ids))}/{len(ids)})")
    lines.append("")
    lines.append("## Bütünlük")
    lines.append(f"- {_TREND_LABEL} üçü de dolu: {year_present_3} (**%{yr_pct}**, kapı ≥%70)")
    lines.append(f"- {RESULT_YEAR} sırası dolu: {result.stats.get('resultYearSiraCount')} "
                 f"(%{result.stats.get('resultYearSiraPct')})  ·  son_yil dağılımı: {result.stats.get('sonYilDist')}")
    lines.append(f"- Arşiv doldurma: +{result.stats.get('archiveRowsAdded', 0)} yıl satırı, "
                 f"{result.stats.get('archiveFieldsFilled', 0)} alan, "
                 f"{result.stats.get('archiveConflicts', 0)} çakışma (API korundu)")
    lines.append(f"- kont2026 kapsaması: {kont2026_present} (%{kont_pct})")
    lines.append(f"- null son_siralama: {result.stats.get('nullSonSiralama')} "
                 f"(%{result.stats.get('nullSonSiralamaPct')})")
    lines.append(f"- kosul_sozluk: {result.stats.get('kosulSozlukCount')} kod  ·  "
                 f"baraj: {result.stats.get('barajCount')} kayıt  ·  "
                 f"trend-yukselen: {result.stats.get('trendYukselenCount')}")
    lines.append(f"- Son sıra tutarlılığı (son_yil = en güncel dolu yıl, son_siralama == yearly_stats[son_yil].sira): "
                 f"{'✅ 0 uyumsuz' if sira_mismatch == 0 else f'❌ {sira_mismatch} uyumsuz'}  ·  "
                 f"elit tutarlılık (sıra≤2000 ⇒ puan≥400): "
                 f"{'✅ 0 ihlal' if elite_violation == 0 else f'❌ {elite_violation} ihlal'}")
    lines.append("")
    lines.append("## K1-Inline Alan Doluluğu (kılavuz uygulanmadan ÖNCEKİ K1 ham doluluk; "
                 "kılavuz-sonrası değerler için yukarıdaki 'Kılavuz (K2, OTORİTER)' bölümüne bakın)")
    lines.append(f"- Koşul kodu (kosul) olan program: {result.stats.get('kosulPresentCount')} "
                 f"(**%{result.stats.get('kosulPresentPct')}**)")
    lines.append(f"- Başarı sırası barajı (minBasariSirasi) olan program: {result.stats.get('barajPresentCount')} "
                 f"(**%{result.stats.get('barajPresentPct')}**)")
    lines.append(f"- Kullanılan farklı koşul kodu: {result.stats.get('usedKosulCodes')}  ·  "
                 f"açıklama kapsaması (K-5): **%{result.stats.get('kosulCodeCoveragePct')}** "
                 f"({result.stats.get('uncoveredKosulCount')} kod açıklamasız)")
    lines.append("")
    lines.append("## Kılavuz (K2, OTORİTER) — bkz. discrepancy_report.md için ayrıntı")
    lines.extend(guide_lines)
    lines.append("")
    lines.append("## Altın Referans Seti (§6.3)")
    lines.extend(gold_lines)
    lines.append("")
    lines.append("## Çapraz Kaynak (K3/K4)")
    lines.append("- **SKIPPED** — basarisiralamalari.com / kariyer.net programatik erişilemez. "
                 "Brief §6.4 uyarınca 20 program ELLE karşılaştırılmalı; **insan onayı şarttır**.")
    lines.append("")
    if warns:
        lines.append("## Uyarılar")
        for w in warns:
            lines.append(f"- ⚠️ {w}")
        lines.append("")
    if fails:
        lines.append("## FAIL Nedenleri")
        for f in fails:
            lines.append(f"- ❌ {f}")
        lines.append("")

    report = "\n".join(lines)
    _log(logf, f"  validate: {'PASS' if ok else 'FAIL'} — {len(fails)} fail, {len(warns)} uyarı, yıl-bütünlüğü %{yr_pct}")
    for f in fails:
        _log(logf, f"    FAIL: {f}")
    return ok, report


def _golden_refs(recs: list[dict[str, Any]]) -> tuple[list[str], list[str], list[str]]:
    """§6.3 altın örnekleri. Sayısal çıpalar (Boğaziçi CS, devlet Tıp) sert kapı;
    varlık kontrolleri (Hukuk/PDR/İng Öğr/Anestezi) uyarı."""
    lines: list[str] = []
    fails: list[str] = []
    warns: list[str] = []

    def find(pred) -> list[dict[str, Any]]:
        return [r for r in recs if pred(r)]

    # Boğaziçi Bilgisayar Müh (SAY) -> en iyi son_siralama < _GOLD_BOGAZICI_CS_MAX.
    # Eşik tarihçesi: 2022=315, 2023=775, 2024=1008, 2025=1448, 2026=4560 (piyasa
    # geneli: İTÜ 1435→2503, ODTÜ 1204→2989; aynı SAY puanının sırası 2026'da ~2x —
    # gerçek dağılım kayması, parse hatası değil). Eski eşik 3000 bu yüzden 10000'e
    # alındı; "bilgisayar" grubu Öğretim Teknolojileri Öğretmenliği'ni de yakalar
    # (min() bu yüzden), asıl hedef parse bulaşmasıyla sıranın 6 haneye fırlamasıdır.
    bogazici_cs = find(lambda r: "bogazici" in r["uniNorm"] and "bilgisayar" in r["grupNorm"]
                        and r["puanTuru"] == "SAY")
    ranks = [r["sonSiralama"] for r in bogazici_cs if r["sonSiralama"] is not None]
    if not bogazici_cs:
        fails.append("Altın ref: Boğaziçi Bilgisayar Müh (SAY) BULUNAMADI.")
        lines.append("- ❌ Boğaziçi Bilgisayar Müh (SAY): bulunamadı")
    elif ranks and min(ranks) < _GOLD_BOGAZICI_CS_MAX:
        lines.append(f"- ✅ Boğaziçi Bilgisayar Müh (SAY): en iyi sıra {min(ranks)} (<{_GOLD_BOGAZICI_CS_MAX})")
    else:
        fails.append(f"Altın ref: Boğaziçi Bilgisayar Müh (SAY) sırası beklenmedik: {ranks}")
        lines.append(f"- ❌ Boğaziçi Bilgisayar Müh (SAY): sıra {ranks} (<{_GOLD_BOGAZICI_CS_MAX} bekleniyor)")

    # Devlet Tıp (SAY) -> en iyi sıra < 60000
    devlet_tip = find(lambda r: r["uniTur"] == "DEVLET" and r["grupNorm"] == "tip"
                      and r["puanTuru"] == "SAY")
    tranks = [r["sonSiralama"] for r in devlet_tip if r["sonSiralama"] is not None]
    if not devlet_tip:
        fails.append("Altın ref: Devlet Tıp (SAY) BULUNAMADI.")
        lines.append("- ❌ Devlet Tıp (SAY): bulunamadı")
    elif tranks and min(tranks) < 60000:
        lines.append(f"- ✅ Devlet Tıp (SAY): en iyi sıra {min(tranks)} (<60000), {len(devlet_tip)} program")
    else:
        fails.append(f"Altın ref: Devlet Tıp (SAY) sırası beklenmedik: min={min(tranks) if tranks else None}")
        lines.append(f"- ❌ Devlet Tıp (SAY): en iyi sıra {min(tranks) if tranks else None} (<60000 bekleniyor)")

    # Varlık kontrolleri (uyarı düzeyi)
    checks = [
        ("Hukuk (EA)", lambda r: "hukuk" in r["grupNorm"] and r["puanTuru"] == "EA"),
        ("PDR/Rehberlik (EA)", lambda r: ("rehberlik" in r["grupNorm"] or "psikolojik danisman" in r["grupNorm"])
         and r["puanTuru"] == "EA"),
        ("İngilizce Öğretmenliği (DİL)", lambda r: "ingilizce ogretmenligi" in r["grupNorm"]
         and r["puanTuru"] == "DİL"),
        ("Anestezi önlisans (TYT)", lambda r: "anestezi" in r["grupNorm"] and r["puanTuru"] == "TYT"
         and r["birimTur"] == "ONLISANS"),
    ]
    for label, pred in checks:
        hits = find(pred)
        if hits:
            lines.append(f"- ✅ {label}: {len(hits)} program")
        else:
            warns.append(f"Altın ref: {label} bulunamadı (elle kontrol önerilir).")
            lines.append(f"- ⚠️ {label}: bulunamadı")

    return lines, fails, warns
