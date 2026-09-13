"""NET KATSAYI — Net Sihirbazı "Sıralamamı Bul" için ÖSYM net→puan katsayıları.

Neden bu yöntem doğru: resmî ÖSYM puanı ham netlerden değil, o yıl tüm adayların
ham netleri üzerinden hesaplanan STANDART puanlardan (ortalama 50, ss 10) üretilir,
sonra yayınlanan katsayılarla ağırlıklanır. Standartlaştırma her derse afin
olduğundan, sabit bir yıl+puan türü için ÖSYM puanı ham netlerin + OBP'nin afin
fonksiyonudur. `net_profiles` her programda o yıl en düşük puanla YERLEŞEN
öğrencinin gerçek ders netlerini + gerçek taban_puan'ını içerir (ÖSYM ground-
truth). Bu veriye afin model oturtunca ÖSYM'nin o yılki gerçek formülü geri elde
edilir — doğrulandı: SAY R²≈0.9986, EA R²≈0.996 (bkz. plan/docs), katsayılar
resmî yapıyla örtüşüyor (OBP≈0.12, AYT Mat≈2.9, TYT dersleri≈1.3).

Bağımlılık YOK (numpy yok) — saf Python, kısmi pivotlu Gauss eliminasyonuyla en
küçük kareler. build_sqlite.build() içinden, ayrıca bir ağ/DB sorgusu olmadan
elde mevcut `net_profiles` listesi + programs kilavuz_kodu->puan_turu haritasıyla
çağrılır.

ÖNEMLİ: _ALANLAR_BY_PT burada src/lib/net-fields.ts'teki NET_ALANLARI_BY_PUAN_TURU
ile BİREBİR senkron tutulmalıdır (puan türü başına modele giren ders alanları).
"""

from __future__ import annotations

from typing import Any, Callable

# Puan türü başına modele giren ders alanları (net_profiles kolonlarıyla `_net`
# eki hariç eşleşir). src/lib/net-fields.ts NET_ALANLARI_BY_PUAN_TURU ile birebir.
_ALANLAR_BY_PT: dict[str, list[str]] = {
    "SAY": ["tyt_trk", "tyt_sos", "tyt_mat", "tyt_fen", "ayt_mat", "ayt_fiz", "ayt_kim", "ayt_bio"],
    "EA": ["tyt_trk", "tyt_sos", "tyt_mat", "tyt_fen", "ayt_mat", "ayt_tde", "ayt_trh1", "ayt_cog1"],
    "SÖZ": [
        "tyt_trk", "tyt_sos", "tyt_mat", "tyt_fen",
        "ayt_tde", "ayt_trh1", "ayt_cog1", "ayt_trh2", "ayt_cog2", "ayt_fel", "ayt_din",
    ],
    "DİL": ["tyt_trk", "tyt_sos", "tyt_mat", "tyt_fen", "ydt_ydil"],
    "TYT": ["tyt_trk", "tyt_sos", "tyt_mat", "tyt_fen"],
}

# net_profiles.katsayi'nin baskın (standart/güncel mezun) değeri — gözlemlenen
# dağılım {0.12: ~93%, 0.18: ~7%, NULL: az}; fit tek, tutarlı bir alt küme
# üzerinde yapılır (varyantları karıştırmak katsayıları bozar).
_KATSAYI_STANDART = 0.12
# Bu eşiğin altında örneklem sayısı olan (yıl,puan_türü) grubu güvenilmez kabul
# edilip atlanır (satırları net_katsayi'de üretilmez).
_MIN_SAMPLE = 30
_YILLAR: tuple[int, ...] = (2023, 2024, 2025)


def _log(logf: Callable[[str], None] | None, msg: str) -> None:
    if logf:
        logf(msg)


def _solve(a_rows: list[list[float]], b: list[float]) -> list[float]:
    """Normal denklemler (AᵀA)x=Aᵀb; kısmi pivotlu Gauss-Jordan eliminasyonu.
    Bağımlılıksız (numpy yok) en küçük kareler çözümü — küçük (≤18x18) sistemler
    için yeterli ve hızlıdır (her (yıl,puan_türü) grubu ayrı ayrı çözülür)."""
    n = len(a_rows[0])
    ata = [[0.0] * n for _ in range(n)]
    atb = [0.0] * n
    for row, target in zip(a_rows, b):
        for i in range(n):
            atb[i] += row[i] * target
            for j in range(n):
                ata[i][j] += row[i] * row[j]
    m = [ata[i] + [atb[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        m[col], m[pivot] = m[pivot], m[col]
        d = m[col][col]
        if abs(d) < 1e-12:
            continue  # tekil/dejenere sütun — o katsayı 0 kalır (savunmacı)
        m[col] = [v / d for v in m[col]]
        for r in range(n):
            if r != col and m[r][col] != 0:
                f = m[r][col]
                m[r] = [m[r][k] - f * m[col][k] for k in range(n + 1)]
    return [m[i][n] for i in range(n)]


def _fit_group(rows: list[dict[str, Any]], alanlar: list[str]) -> dict[str, Any] | None:
    """Bir (yıl,puan_türü) grubu için `taban_puan ~ 1 + Σ net_alan + obp` afin
    modelini ground-truth'a (yerleşen son öğrenci) oturtur. Örneklem yetersizse
    (veya tüm satırlar eksik alan içeriyorsa) None döner (grup atlanır)."""
    clean = [
        r for r in rows
        if r.get("obp") is not None and r.get("taban_puan") is not None
        and all(r.get(f"{alan}_net") is not None for alan in alanlar)
    ]
    if len(clean) < _MIN_SAMPLE:
        return None

    names = ["intercept", *alanlar, "obp"]
    a_rows = [[1.0, *[r[f"{alan}_net"] for alan in alanlar], r["obp"]] for r in clean]
    y = [r["taban_puan"] for r in clean]
    coef = _solve(a_rows, y)

    ybar = sum(y) / len(y)
    sst = sum((v - ybar) ** 2 for v in y)
    sse = 0.0
    for a_row, target in zip(a_rows, y):
        pred = sum(c * x for c, x in zip(coef, a_row))
        sse += (target - pred) ** 2
    r2 = 1 - sse / sst if sst else 0.0
    rmse = (sse / len(clean)) ** 0.5
    ort_obp = sum(r["obp"] for r in clean) / len(clean)

    return {
        "coef": dict(zip(names, coef)),
        "n": len(clean),
        "r2": r2,
        "rmse": rmse,
        "ort_obp": ort_obp,
    }


def compute_net_katsayi(
    net_profiles: list[dict[str, Any]],
    puan_turu_by_kilavuz: dict[int, str],
    *,
    logf: Callable[[str], None] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """net_profiles (build_sqlite'a giden ham liste, merge_netler çıktısı) +
    kilavuz_kodu->puan_türü haritasından (programs'tan) her (yıl,puan_türü)
    için afin net→puan katsayılarını oturtur.

    Döndürür: (katsayi_rows, meta_rows, stats).
    - katsayi_rows: net_katsayi tablosu satırları — {yil, puan_turu, alan, katsayi}.
      `alan` gerçek ders alanlarının yanı sıra 'intercept' ve 'obp' sözde-alanlarını
      da içerir (sabit terim + OBP katsayısı).
    - meta_rows: net_katsayi_meta satırları — {yil, puan_turu, ort_obp, n, r2, rmse}.
      ort_obp: kullanıcı OBP girmediğinde varsayılan (o yıl/türün ortalama OBP'si).
    """
    by_group: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for row in net_profiles:
        if row.get("katsayi") != _KATSAYI_STANDART:
            continue
        yil = row.get("yil")
        if yil not in _YILLAR:
            continue
        pt = puan_turu_by_kilavuz.get(row.get("kilavuz_kodu"))
        if pt is None:
            continue
        by_group.setdefault((yil, pt), []).append(row)

    katsayi_rows: list[dict[str, Any]] = []
    meta_rows: list[dict[str, Any]] = []
    skipped: list[str] = []
    r2_values: list[float] = []

    for yil in _YILLAR:
        for pt, alanlar in _ALANLAR_BY_PT.items():
            rows = by_group.get((yil, pt), [])
            fit = _fit_group(rows, alanlar)
            if fit is None:
                skipped.append(f"{pt}/{yil} (n={len(rows)})")
                continue
            for alan, k in fit["coef"].items():
                katsayi_rows.append({"yil": yil, "puan_turu": pt, "alan": alan, "katsayi": k})
            meta_rows.append({
                "yil": yil,
                "puan_turu": pt,
                "ort_obp": fit["ort_obp"],
                "n": fit["n"],
                "r2": fit["r2"],
                "rmse": fit["rmse"],
            })
            r2_values.append(fit["r2"])
            _log(logf, f"  [net_katsayi] {pt}/{yil}: n={fit['n']} R²={fit['r2']:.4f} RMSE={fit['rmse']:.2f}")

    if skipped:
        _log(logf, f"  [net_katsayi] yetersiz örneklem, atlandı: {skipped}")

    stats = {
        "groupCount": len(meta_rows),
        "skippedCount": len(skipped),
        "skipped": skipped,
        "minR2": min(r2_values) if r2_values else None,
    }
    return katsayi_rows, meta_rows, stats
