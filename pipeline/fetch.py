"""FETCH — Plan §5 Faz 1.

K1: YÖK Atlas tercih-kılavuz JSON API (yokatlas-py transport'u üzerinden, ham
dict olarak). Tipli `Program` modeli KKTC/YURTDIŞI üniversitelerde ValidationError
fırlattığı için (`universite_turu` Literal'i yalnız DEVLET/VAKIF/VAKIF MYO kabul
eder) ham JSON'ı doğrudan işleriz; kütüphanenin yalnızca HTTP taşımasını
(base_url, header, RateLimitError) kullanırız.

K2: ÖSYM 2026 kılavuzu — 2026-07-25 itibarıyla OTORİTER kaynak (bkz.
docs/VERI_NOTLARI.md §1.3). Aşağıdaki `fetch_k2`/`_parse_osym_xls`/
`_parse_osym_pdf` bu kararın ÖNCESİNDEN kalma, kullanılmayan bir taslaktır;
gerçek parser `OUTBOX/pipeline/parse_kilavuz.py::parse_kilavuz()`dur (run.py
oradan çağırır). Bu fonksiyonlar yalnız referans için bırakıldı.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from yokatlas_py import SearchFilters
from yokatlas_py.client import _SEARCH_PATH, _build_request
from yokatlas_py.exceptions import APIError, RateLimitError
from yokatlas_py.http_client import HttpClient

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
_INTER_PAGE_SLEEP = 0.3  # saniye, sayfalar arası
_BACKOFF_SCHEDULE = (1, 2, 4, 8, 16)  # RateLimitError için exponential backoff


@dataclass
class FetchResult:
    programs: list[dict[str, Any]] = field(default_factory=list)
    pages_fetched: int = 0
    per_combo: dict[str, int] = field(default_factory=dict)
    osym_used: bool = False
    osym_note: str = ""


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
    """K1: tüm evreni sayfalı çeker. Ham sayfaları raw/k1/{PT}/{page}.json yazar.

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
            combo_dir = raw_dir / "k1" / combo_ad
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


# --- K2 (ÖSYM 2026 kılavuz) — ARTIK KULLANILMIYOR (bkz. parse_kilavuz.py) ----
# 2026-07-25: kılavuz OTORİTER kaynak oldu. run.py artık burayı çağırmıyor;
# gerçek parser `OUTBOX/pipeline/parse_kilavuz.py::parse_kilavuz()`. Bu
# fonksiyonlar (yalnız `raw/osym/`'a elle bırakılan XLS/PDF için, kod-only
# taslak) geriye dönük referans olarak bırakıldı, ölü koddur.


def fetch_k2(
    raw_dir: str | Path,
    *,
    logf: Callable[[str], None] | None = None,
) -> tuple[dict[int, dict[str, Any]], str]:
    """K2: `raw/osym/` altındaki elle bırakılmış XLS/PDF'ten 2026 kontenjan/koşul
    çapraz-kontrol verisi okur. Dosya yoksa boş döner (SERT bağımlılık değil).

    Döndürür: ({kilavuz_kodu: {"kont2026": int, ...}}, açıklama_notu).
    """
    osym_dir = Path(raw_dir) / "osym"
    osym_dir.mkdir(parents=True, exist_ok=True)
    xls_files = sorted([*osym_dir.glob("*.xls"), *osym_dir.glob("*.xlsx")])
    pdf_files = sorted(osym_dir.glob("*.pdf"))

    if not xls_files and not pdf_files:
        note = (
            "K2 atlandı: raw/osym/ boş. K1'in 2026 (current) kaydı kont2026 + koşul "
            "kodları + koşul açıklamaları + başarı sırası barajını inline sağladığı için "
            "ÖSYM kılavuzu sert bağımlılık değildir."
        )
        _log(logf, f"  {note}")
        return {}, note

    result: dict[int, dict[str, Any]] = {}
    try:
        if xls_files:
            result = _parse_osym_xls(xls_files, logf=logf)
            note = f"K2 çapraz-kontrol: {len(result)} kayıt {len(xls_files)} XLS dosyasından okundu."
        else:
            result = _parse_osym_pdf(pdf_files, logf=logf)
            note = f"K2 çapraz-kontrol: {len(result)} kayıt {len(pdf_files)} PDF dosyasından okundu."
    except Exception as exc:  # noqa: BLE001 - K2 kritik değil, hata loglanır ve atlanır
        note = f"K2 parse hatası (atlandı, K1 yeterli): {exc}"
        _log(logf, f"  {note}")
        return {}, note
    _log(logf, f"  {note}")
    return result, note


def _parse_osym_xls(
    files: list[Path], *, logf: Callable[[str], None] | None = None
) -> dict[int, dict[str, Any]]:
    """ÖSYM Tablo 3/4 XLS'ini okur. Program kodu ve 2026 kontenjan sütunlarını
    başlık adlarından sezgisel olarak bulur (kılavuz formatı yıldan yıla değişir)."""
    from openpyxl import load_workbook

    out: dict[int, dict[str, Any]] = {}
    for f in files:
        wb = load_workbook(f, read_only=True, data_only=True)
        for ws in wb.worksheets:
            rows = ws.iter_rows(values_only=True)
            header = None
            code_idx = kont_idx = None
            for row in rows:
                cells = [str(c).strip().lower() if c is not None else "" for c in row]
                if header is None:
                    if any("program kodu" in c or "prog. kodu" in c or c == "kod" for c in cells):
                        header = cells
                        for i, c in enumerate(cells):
                            if "program kodu" in c or "prog. kodu" in c or c == "kod":
                                code_idx = i
                            if "kontenjan" in c and kont_idx is None:
                                kont_idx = i
                    continue
                if code_idx is None:
                    continue
                try:
                    code = int(str(row[code_idx]).strip())
                except (TypeError, ValueError):
                    continue
                kont = None
                if kont_idx is not None and row[kont_idx] not in (None, ""):
                    try:
                        kont = int(float(str(row[kont_idx]).replace(".", "").replace(",", ".")))
                    except (TypeError, ValueError):
                        kont = None
                out[code] = {"kont2026": kont, "source": "osym-xls"}
        wb.close()
    return out


def _parse_osym_pdf(
    files: list[Path], *, logf: Callable[[str], None] | None = None
) -> dict[int, dict[str, Any]]:
    """ÖSYM PDF yedeği (pdfplumber). XLS bulunamazsa kullanılır."""
    import pdfplumber

    out: dict[int, dict[str, Any]] = {}
    for f in files:
        with pdfplumber.open(f) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    for row in table:
                        if not row:
                            continue
                        first = (row[0] or "").strip()
                        if first.isdigit() and len(first) >= 8:
                            try:
                                code = int(first)
                            except ValueError:
                                continue
                            out[code] = {"kont2026": None, "source": "osym-pdf"}
    return out
