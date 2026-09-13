"""YIL MODELİ — pipeline'daki TEK yıl konfigürasyonu.

Hiçbir modül literal yıl yazmaz; hepsi buradan türetilir. Yıl geçişinde
(yeni YKS yerleştirme sonuçları YÖK Atlas'a düştüğünde) prosedür:
docs/VERI_NOTLARI.md §1.6.

YÖK Atlas tercih-kılavuz kaydı 4 yıl taşır: `current` (suffix'siz) = EN SON
TAMAMLANAN yerleştirme, `suffix1/2/3` = önceki 3 yıl. En eski yıl her geçişte
API'den DÜŞER; tarihsel süreklilik `archive/yearly_stats_*.json.gz` ile
sağlanır (bkz. merge.apply_history_archive, scripts/make_history_archive.py).

2026-09 geçişi (canlı API ile doğrulandı, Koç Tıp 203910699):
  current -> 2026 (sıra 65 / 552.857), suffix1 -> 2025, suffix2 -> 2024,
  suffix3 -> 2023; 2022 yalnız arşivde. `gkY` (current yerleşen) geldi,
  `gkY1` (tarihsel yerleşen) kayboldu -> 2024 yerleşen arşivden doldurulur.
"""

from __future__ import annotations

# En son tamamlanan yerleştirme yılı = API `current` kaydının yılı = meta.dataYear.
RESULT_YEAR = 2026

# Kılavuz / kontenjan yılı. `programs.kont2026` kolonunun anlamı; şu an RESULT_YEAR
# ile aynı (2026 kılavuzu + 2026 yerleştirmesi). Kolon adı tüketici sözleşmesidir,
# yeniden adlandırma SCHEMA_VERSION artırır (bkz. run.py).
CATALOG_YEAR = 2026

# Kılavuz Tablo 3/4'te basılan "önceki yıl" sonuç sütunlarının yılı
# ("2025-YKS BAŞARI SIRASI / EN KÜÇÜK PUAN"). Kılavuz Temmuz'da, yerleştirme
# Ağustos'ta çıktığı için her zaman RESULT_YEAR - 1'dir.
GUIDE_RESULT_YEAR = RESULT_YEAR - 1

# Arşivden korunan en eski yıl (API'den düşmüş olsa da yearly_stats'ta kalır).
ARCHIVE_MIN_YEAR = 2022

# API suffix -> yerleştirme yılı (yeni -> eski). "" = current.
HISTORY_YEARS: list[tuple[int, str]] = [
    (RESULT_YEAR - i, "" if i == 0 else str(i)) for i in range(4)
]

# yearly_stats.yil için izin verilen küme (DDL CHECK + test).
ALL_YEARS: tuple[int, ...] = tuple(range(ARCHIVE_MIN_YEAR, RESULT_YEAR + 1))

# Trend (K-11) ve "3 yıl dolu" bütünlük kapısı için ardışık üçlü (eski -> yeni).
TREND_YEARS: tuple[int, int, int] = (RESULT_YEAR - 2, RESULT_YEAR - 1, RESULT_YEAR)

# Net Sihirbazı (/api/netler/search) yılları (yeni -> eski). Netler yerleştirmeden
# aylar sonra yayınlanır; RESULT_YEAR boş dönerse fetch_netler atlar + loglar.
NET_YEARS: tuple[int, ...] = tuple(RESULT_YEAR - i for i in range(4))


def years_sql_in(years: tuple[int, ...] = ALL_YEARS) -> str:
    """SQL `IN (...)` gövdesi: '2022,2023,2024,2025,2026'."""
    return ",".join(str(y) for y in years)
