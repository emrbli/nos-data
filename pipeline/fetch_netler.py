"""FETCH NETLER — Plan §1 (Net Sihirbazı verisi, brief §10).

K1 ile aynı resmî YÖK Atlas API'sinin `/api/netler/search` uç noktasını TOPLU
tarar: her kayıt, o programa o yıl en düşük puanla YERLEŞEN öğrencinin ders bazlı
net dökümüdür (bir puan HESAPLAMA verisi DEĞİL; kıyas referansı).

Kritik sözleşme (araştırmayla doğrulandı):
  - `universite_id`/`birim_grup_id`/`katsayi` KESİNLİKLE None bırakılır. None =
    filtresiz = sunucu TÜM evreni döner (program-bazlı ayrı çağrı senaryosu YOK).
    `katsayi` filtrelenirse varyantlar sessizce kaybolur; dedup anahtarı
    (kilavuz_kodu, yil, katsayi) tüm varyantları gerektirir.
  - `yil` MUTLAKA set edilir (None → yalnız güncel/config döner, yerleşme yok).
  - Sayfalama `search`'le aynı `SearchPage` sözleşmesi: content/last/totalPages.
  - Ham sayfalar raw/netler/{PT}/{yil}/{page:04d}.json'a yazılır (idempotent
    yeniden koşu + kesinti sonrası resume için).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

from yokatlas_py import NetFilters
from yokatlas_py.client import _NETLER_SEARCH_PATH, _build_net_request
from yokatlas_py.http_client import HttpClient

from .fetch import (
    SEARCH_COMBOS,
    _INTER_PAGE_SLEEP,
    _PAGE_SIZE,
    _PT_DIR,
    _log,
    _post_with_backoff,
)

from .years import NET_YEARS  # yeni → eski; en yeni yıl (netler henüz yayınlanmadıysa)
# ilk sayfada boş dönerse atlanır + loglanır (bkz. years.py). Yeniden export:
# run.py `--skip-fetch` yolu ve testler buradan okur.
__all__ = ["NET_YEARS", "fetch_netler"]


def _existing_net_pages(combo_dir: Path) -> dict[int, Path]:
    """Bir (PT, yil) dizinindeki mevcut sayfa dosyalarını {sayfa_no: yol} döner."""
    pages: dict[int, Path] = {}
    for f in combo_dir.glob("*.json"):
        try:
            pages[int(f.stem)] = f
        except ValueError:
            continue
    return pages


def _load_cached_prefix(
    existing: dict[int, Path],
    puan_turu: str,
    yil: int,
    logf: Callable[[str], None] | None,
) -> tuple[list[dict[str, Any]], int, bool]:
    """0'dan başlayan kesintisiz sayfa önekini diskten yükler.

    Döndürür: (cache_satırları, sonraki_çekilecek_sayfa, tamamlandı_mı).
    `tamamlandı_mı`=True ise önekin son sayfası `last`/boş olduğundan ağ gereksiz.
    Kesintisiz önek yoksa/boşsa ([], 0, False) döner (baştan çek).
    """
    if not existing:
        return [], 0, False
    cached_rows: list[dict[str, Any]] = []
    page = 0
    complete = False
    while page in existing:
        raw = json.loads(existing[page].read_text(encoding="utf-8"))
        content = raw.get("content") or []
        if page == 0 and not content:
            # Boş ilk sayfa = o yıl henüz YAYINLANMAMIŞTI (ör. yerleştirme sonrası
            # netler aylar sonra çıkar). Bunu "tamamlandı" saymak cache'i sonsuza
            # dek boş kilitler; ağdan yeniden denenmeli.
            return [], 0, False
        for item in content:
            item.setdefault("_fetch_puan_turu", puan_turu)
            item.setdefault("_fetch_yil", yil)
            cached_rows.append(item)
        page += 1
        if raw.get("last") or not content:
            complete = True
            break
    if cached_rows or complete:
        _log(logf, f"  [net {puan_turu}/{yil}] cache: {len(cached_rows)} satır "
                   f"({page} sayfa){' — tamamlandı' if complete else ', devam ediliyor'}")
    return cached_rows, page, complete


def fetch_netler(
    raw_dir: str | Path,
    *,
    combos: list[tuple[str, int]] | None = None,
    years: tuple[int, ...] = NET_YEARS,
    max_pages: int | None = None,
    logf: Callable[[str], None] | None = None,
    http: HttpClient | None = None,
) -> tuple[list[dict[str, Any]], int, dict[str, int]]:
    """Net evrenini (puan türü × yıl) sayfalı çeker; raw/netler/ altına yazar.

    Döndürür: (ham_net_dict_listesi, ağdan_çekilen_sayfa, kombo_yıl_başına_satır).
    `max_pages`: (PT,yıl) başına maksimum sayfa (bounded test; None=tümü).
    Mevcut raw/netler/ önbelleği kesintisiz önek olarak yeniden kullanılır (resume).
    """
    raw_dir = Path(raw_dir)
    combos = combos or SEARCH_COMBOS
    own_http = http is None
    if http is None:
        http = HttpClient()
    rows: list[dict[str, Any]] = []
    pages_fetched = 0
    per_combo: dict[str, int] = {}
    try:
        for puan_turu, birim_turu_id in combos:
            if puan_turu is None:
                # Tamamlama taraması (fetch.SEARCH_COMBOS pt=None) net API'sine
                # uygulanmaz: net taraması PT'ye göre yapılır; null-PT kayıtların
                # (2 Manas Filoloji) net verisi PT'li taramalarda zaten yok.
                continue
            for yil in years:
                combo_key = f"{puan_turu}/{yil}"
                combo_dir = raw_dir / "netler" / _PT_DIR[puan_turu] / str(yil)
                combo_dir.mkdir(parents=True, exist_ok=True)

                existing = _existing_net_pages(combo_dir)
                cached_rows, page, complete = _load_cached_prefix(existing, puan_turu, yil, logf)
                rows.extend(cached_rows)
                combo_count = len(cached_rows)
                if complete:
                    per_combo[combo_key] = combo_count
                    continue

                empty_year = False
                while True:
                    if max_pages is not None and page >= max_pages:
                        _log(logf, f"  [net {combo_key}] max_pages={max_pages} sınırı")
                        break
                    filters = NetFilters(puan_turu=puan_turu, birim_turu_id=birim_turu_id, yil=yil)
                    body = _build_net_request(filters, page=page, size=_PAGE_SIZE)
                    raw = _post_with_backoff(
                        http, body, logf, f"net {combo_key} p{page}", path=_NETLER_SEARCH_PATH)
                    content = raw.get("content") or []
                    (combo_dir / f"{page:04d}.json").write_text(
                        json.dumps(raw, ensure_ascii=False), encoding="utf-8")
                    if page == 0 and not content:
                        _log(logf, f"  [net {combo_key}] ilk sayfa boş → yıl atlandı")
                        empty_year = True
                        break
                    for item in content:
                        item.setdefault("_fetch_puan_turu", puan_turu)
                        item.setdefault("_fetch_yil", yil)
                        rows.append(item)
                    combo_count += len(content)
                    pages_fetched += 1
                    if page == 0:
                        _log(logf, f"  [net {combo_key}] total={raw.get('totalElements')} "
                                   f"pages={raw.get('totalPages')}")
                    if raw.get("last") or not content:
                        break
                    page += 1
                    time.sleep(_INTER_PAGE_SLEEP)

                per_combo[combo_key] = combo_count
                if not empty_year:
                    _log(logf, f"  [net {combo_key}] {combo_count} satır ({page + 1} sayfa)")
    finally:
        if own_http:
            http.close()
    return rows, pages_fetched, per_combo
