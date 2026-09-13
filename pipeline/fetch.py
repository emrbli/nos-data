"""FETCH — Plan §5 Faz 1.

K1: YÖK Atlas tercih-kılavuz JSON API (yokatlas-py transport'u üzerinden, ham
dict olarak). Tipli `Program` modeli KKTC/YURTDIŞI üniversitelerde ValidationError
fırlattığı için (`universite_turu` Literal'i yalnız DEVLET/VAKIF/VAKIF MYO kabul
eder) ham JSON'ı doğrudan işleriz; kütüphanenin yalnızca HTTP taşımasını
(base_url, header, RateLimitError) kullanırız.

K2: ÖSYM kılavuzu — OTORİTER kaynak (bkz. docs/VERI_NOTLARI.md §1.3);
parser `pipeline/parse_kilavuz.py::parse_kilavuz()` (PDF), çapraz kontrol
`pipeline/parse_kilavuz_xls.py` (XLS). Bu modül yalnız K1'i çeker.

Ham sayfalar `raw/k1/{RESULT_YEAR}/{kombo}/NNNN.json` altına yazılır: API her
yıl geçişinde en eski yılı düşürdüğü için önceki yılın anlık görüntüsü
ÜZERİNE YAZILMAZ (yerel yedek; kalıcı güvence archive/, bkz. years.py).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from yokatlas_py import SearchFilters
from yokatlas_py.client import _SEARCH_PATH, _build_request
from yokatlas_py.exceptions import RateLimitError
from yokatlas_py.http_client import HttpClient

from .years import RESULT_YEAR

# 5 tarama kombinasyonu (Plan §5 Faz 1.1) + 2 TAMAMLAMA taraması (2026-07-25).
#   puan_turu (BÜYÜK, Türkçe) x birim_turu_id (46=LİSANS, 47=ÖNLİSANS)
#
# TAMAMLAMA (pt=None): API'de puanTuru alanı NULL olan kayıtlar (canlı API'de
# doğrulandı: Kırgızistan-Türkiye Manas Üni. 2 Filoloji programı — kılavuzda
# puan türü DİL basılı ama API null döndürüyor) PT-filtreli 5 sorguya HİÇ
# GİRMİYOR. Filtresiz birim taraması evreni tamamlar (canlı toplam 21.482 =
# 5 kombo 21.480 + bu 2). PT-tagli kombolar ÖNCE gelir; merge dedup "ilk kayıt
# kazanır" olduğundan tamamlama yalnız yeni (null-PT) kodları ekler; puan
# türlerini ÖSYM kılavuzu doldurur (merge._apply_guide, guide otoriter).
SEARCH_COMBOS: list[tuple[str | None, int]] = [
    ("SAY", 46),
    ("EA", 46),
    ("SÖZ", 46),
    ("DİL", 46),
    ("TYT", 47),
    (None, 46),
    (None, 47),
]

# Dosya-sistemi güvenli dizin adları (SÖZ->SOZ, DİL->DIL).
_PT_DIR = {"SAY": "SAY", "EA": "EA", "SÖZ": "SOZ", "DİL": "DIL", "TYT": "TYT"}


def _combo_dir_name(puan_turu: str | None, birim_turu_id: int) -> str:
    """raw/k1/ altındaki dizin adı. Tamamlama (pt=None) taramaları ALL46/ALL47."""
    return _PT_DIR[puan_turu] if puan_turu is not None else f"ALL{birim_turu_id}"

_PAGE_SIZE = 100


def k1_raw_dir(raw_dir: str | Path) -> Path:
    """Bu sonuç yılının K1 ham dizini: raw/k1/{RESULT_YEAR}/ (bkz. years.py)."""
    return Path(raw_dir) / "k1" / str(RESULT_YEAR)
_INTER_PAGE_SLEEP = 0.3  # saniye, sayfalar arası
_BACKOFF_SCHEDULE = (1, 2, 4, 8, 16)  # RateLimitError için exponential backoff


@dataclass
class FetchResult:
    programs: list[dict[str, Any]] = field(default_factory=list)
    pages_fetched: int = 0
    per_combo: dict[str, int] = field(default_factory=dict)


def _log(logf: Callable[[str], None] | None, msg: str) -> None:
    if logf:
        logf(msg)


def _post_with_backoff(
    http: HttpClient,
    body: dict[str, Any],
    logf: Callable[[str], None] | None,
    label: str,
    path: str = _SEARCH_PATH,
) -> dict[str, Any]:
    """RateLimitError'da exponential backoff ile tek sayfayı çeker.

    `path`: sorgulanacak API uç noktası. Varsayılan program araması
    (`_SEARCH_PATH`); net taraması `_NETLER_SEARCH_PATH` geçer (fetch_netler)."""
    last_exc: Exception | None = None
    for attempt in range(len(_BACKOFF_SCHEDULE) + 1):
        try:
            return http.post_json(path, json_body=body)
        except RateLimitError as exc:
            last_exc = exc
            if attempt >= len(_BACKOFF_SCHEDULE):
                break
            wait = _BACKOFF_SCHEDULE[attempt]
            _log(logf, f"  [rate-limit] {label} deneme {attempt + 1}: {wait}s bekleniyor ({exc})")
            time.sleep(wait)
    raise RuntimeError(f"{label}: rate-limit sonrası {len(_BACKOFF_SCHEDULE)} deneme tükendi") from last_exc


def fetch_k1(
    raw_dir: str | Path,
    *,
    combos: list[tuple[str | None, int]] | None = None,
    max_pages: int | None = None,
    logf: Callable[[str], None] | None = None,
    http: HttpClient | None = None,
) -> tuple[list[dict[str, Any]], int, dict[str, int]]:
    """K1: tüm evreni sayfalı çeker. Ham sayfaları raw/k1/{RESULT_YEAR}/{PT}/{page}.json yazar.

    Döndürür: (ham_program_dict_listesi, çekilen_sayfa_sayısı, kombo_basina_sayi).
    `max_pages`: kombo başına maksimum sayfa (bounded test koşusu için; None=tümü).
    """
    raw_dir = Path(raw_dir)
    combos = combos or SEARCH_COMBOS
    own_http = http is None
    if http is None:
        http = HttpClient()
    programs: list[dict[str, Any]] = []
    pages_fetched = 0
    per_combo: dict[str, int] = {}
    try:
        for puan_turu, birim_turu_id in combos:
            combo_ad = _combo_dir_name(puan_turu, birim_turu_id)
            combo_dir = k1_raw_dir(raw_dir) / combo_ad
            combo_dir.mkdir(parents=True, exist_ok=True)
            combo_count = 0
            page = 0
            total_pages = None
            while True:
                if max_pages is not None and page >= max_pages:
                    _log(logf, f"  [{combo_ad}] max_pages={max_pages} sınırına ulaşıldı, durduruluyor")
                    break
                # Tamamlama taraması (pt=None): puan_turu filtresi GÖNDERİLMEZ —
                # API'de puanTuru NULL olan kayıtlar ancak böyle görünür.
                pt_kwargs = {"puan_turu": puan_turu} if puan_turu is not None else {}
                filters = SearchFilters(birim_turu_id=birim_turu_id, **pt_kwargs)
                body = _build_request(filters, page=page, size=_PAGE_SIZE, sort_by="basariSirasi", direction="ASC")
                raw = _post_with_backoff(http, body, logf, f"{combo_ad} p{page}")
                content = raw.get("content") or []
                total_pages = raw.get("totalPages")
                total_elements = raw.get("totalElements")
                # Ham sayfayı diske yaz (debug + idempotent yeniden koşu).
                (combo_dir / f"{page:04d}.json").write_text(
                    json.dumps(raw, ensure_ascii=False), encoding="utf-8"
                )
                for item in content:
                    # Kombo bilgisini iz olarak ekle (merge'de puan türü doğrulaması
                    # için). Tamamlama taramasında PT izi YOK — puan türü kaydın
                    # kendi alanından, o da boşsa kılavuzdan gelir.
                    if puan_turu is not None:
                        item.setdefault("_fetch_puan_turu", puan_turu)
                    item.setdefault("_fetch_birim_turu_id", birim_turu_id)
                    programs.append(item)
                combo_count += len(content)
                pages_fetched += 1
                if page == 0:
                    _log(logf, f"  [{combo_ad} bt={birim_turu_id}] total={total_elements} pages={total_pages}")
                if raw.get("last") or not content:
                    break
                page += 1
                time.sleep(_INTER_PAGE_SLEEP)
            per_combo[combo_ad] = combo_count
            _log(logf, f"  [{combo_ad}] {combo_count} kayıt çekildi ({page + 1} sayfa)")
    finally:
        if own_http:
            http.close()
    return programs, pages_fetched, per_combo
