"""PARSE_KILAVUZ — ÖSYM 2026 Yükseköğretim Programları ve Kontenjanları Kılavuzu
(docs/kontkilavuz_yktd21072026.pdf, 793 sayfa) parse eder.

Kılavuz artık OTORİTER kaynaktır (bkz. plan). Bu modül saf/ağ-bağımsızdır: yalnız
pdfplumber ile konumsal (x-koordinat) sütun çıkarımı yapar. `fetch._parse_osym_pdf`
taslağının (yalnız kod çıkaran `extract_tables()` stub'ı) yerini alır.

Sütun haritaları kılavuzun kendi "TABLOLARDA KULLANILAN BAŞLICA KISALTMALAR" ve
"Tablo 3 ve Tablo 4 ile İlgili Açıklamalar" bölümlerinden (bkz. kılavuz s.15-17)
DOĞRULANMIŞ marker x-pozisyonlarından hesaplanır (bkz. plan). Tablo 4'ün öğretim
üyesi (13-16: P.DR/D.DR/DR.ÖĞR.ÜYE/GRV) ve sınav ortalaması (19-24: TUS/DUS/AB
AYP/KPSS) sütunları KASITLI ATLANIR: GRV (Görevlendirme) "*" işareti taşıyan bir
bayrak sütunudur, DB'nin `ar_gor` (araştırma görevlisi, yokatlas kaynaklı) alanıyla
SEMANTİK OLARAK FARKLIDIR — yanlış eşleme riskini önlemek için onaylı kapsam
dışında bırakılmıştır (bkz. plan §Riskler).

Tablo 5 (özel yetenek) atlanır: puan türü/merkezi başarı sırası yok, sihirbaz
modeline uymaz (bkz. plan "Kapsam dışı").
"""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .turkish import fold

_PT_VALUES = {"SAY", "EA", "SÖZ", "DİL", "TYT"}
_LEVEL_VALUES = {"Hazırlık", "Önlisans", "Ön Lisans", "Lisans"}


def _log(logf: Callable[[str], None] | None, msg: str) -> None:
    if logf:
        logf(msg)


# --- Sütun haritaları (marker x-pozisyonları kılavuz PDF'inden ölçülmüştür) --

# Tablo 3 (Ön lisans, 13 sütun) marker x'leri — s.15 "13 sütun" açıklamasıyla uyumlu.
_T3_MARKERS: dict[int, float] = {
    1: 33.47, 2: 145.79, 3: 213.89, 4: 237.77, 5: 264.05, 6: 289.97,
    7: 326.45, 8: 356.23, 9: 447.18, 10: 480.52, 11: 517.40, 12: 535.66, 13: 557.74,
}
# Tablo 4 (Lisans, 24 sütun) marker x'leri — s.16-17 açıklamasıyla uyumlu.
_T4_MARKERS: dict[int, float] = {
    1: 31.06, 2: 89.25, 3: 194.78, 4: 212.54, 5: 233.42, 6: 255.26,
    7: 273.02, 8: 304.09, 9: 335.92, 10: 363.41, 11: 409.00, 12: 450.04,
    13: 466.03, 14: 483.31, 15: 504.67, 16: 526.03, 17: 541.75, 18: 566.35,
    19: 600.22, 20: 632.50, 21: 665.62, 22: 699.46, 23: 733.30, 24: 767.16,
}

# Sütun indeksi -> semantik alan adı. Yalnız ONAYLI kapsam alanları eşlenir;
# MEB kont. (T4 col7), öğretim üyesi (T4 13-16), sınav ortalamaları (T4 19-24)
# haritalanmaz -> otomatik olarak yok sayılır (bant değeri okunur ama kullanılmaz).
_T3_FIELD: dict[int, str] = {
    3: "sure", 4: "puanTuru", 5: "genelKont", 6: "okBirKont",
    7: "sehitGaziKont", 8: "y34Kont", 9: "kosul", 10: "sirasiOnceki",
    11: "puanOnceki", 12: "tyc", 13: "akreditasyon",
}
_T4_FIELD: dict[int, str] = {
    3: "sure", 4: "puanTuru", 5: "genelKont", 6: "okBirKont",
    8: "sehitGaziKont", 9: "y34Kont", 10: "kosul", 11: "sirasiOnceki",
    12: "puanOnceki", 17: "tyc", 18: "akreditasyon",
}


def _boundaries(markers: dict[int, float]) -> tuple[list[float], list[int]]:
    """marker x-pozisyonlarından [sınır...] + [sütun_indeksi...] üretir (bisect ile
    kullanılır): ardışık marker'ların ORTA NOKTASI sınırdır (kılavuzun kendi
    verdiği kolon numaralarıyla doğrulandı, bkz. plan)."""
    items = sorted(markers.items(), key=lambda kv: kv[1])
    bounds = [-1.0]  # ilk sütun: [-1, ilk_sınır)
    cols = [items[0][0]]
    for (idx_a, x_a), (idx_b, x_b) in zip(items, items[1:]):
        bounds.append((x_a + x_b) / 2)
        cols.append(idx_b)
    return bounds, cols


_T3_BOUNDS, _T3_COLS = _boundaries(_T3_MARKERS)
_T4_BOUNDS, _T4_COLS = _boundaries(_T4_MARKERS)


def _col_for_x(bounds: list[float], cols: list[int], x: float) -> int:
    i = bisect_right(bounds, x) - 1
    return cols[max(0, min(i, len(cols) - 1))]


# --- Sayı/metin ayrıştırma yardımcıları ---------------------------------------


def _is_dash_or_star(s: str) -> bool:
    """"- - - -" (yeni program) / "* * * *" (puan türü değişti) işaretleri -> boş."""
    return bool(re.fullmatch(r"[-*]+", s.replace(" ", "")))


def _parse_int_bare(s: str) -> int | None:
    s = s.strip().rstrip(",")
    if not s or _is_dash_or_star(s):
        return None
    try:
        n = int(s)
    except ValueError:
        return None
    return n if n > 0 else None


def _parse_puan_dot(s: str) -> float | None:
    s = s.strip().rstrip(",")
    if not s or _is_dash_or_star(s):
        return None
    try:
        p = float(s)
    except ValueError:
        return None
    return p if p > 0 else None


_TL_RE = re.compile(r"^\d{1,3}(\.\d{3})*,\d{2}$")


def _parse_tl(s: str) -> float | None:
    """Türk lirası biçimi: binlik '.', ondalık ',' (örn. '720.000,00' -> 720000.0)."""
    s = s.strip()
    if not _TL_RE.match(s):
        return None
    try:
        return float(s.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _is_noise_char(text: str) -> bool:
    """Tek karakterlik/anlamsız izole token (filigran/dipnot sızıntısı sanısı)."""
    return len(text) <= 1 and not text.isdigit()


# --- Satır gruplama ------------------------------------------------------------


@dataclass
class _Row:
    top: float
    words: list[tuple[float, str]]  # (x0, text) x0'a göre sıralı


def _rows_for_page(page: Any, *, min_words: int = 1, top_margin: float = 20.0) -> list[_Row]:
    """Sayfa kelimelerini `top`'a göre satırlara gruplar. Her sayfanın tekrar eden
    üst-bilgi ve alt-bilgi (sayfa no + kılavuz adı, sayfa sonuna yakın) satırları
    burada ELENİR — aksi hâlde veri satırlarıyla karışıp isim/sütun sızıntısına
    yol açar (bkz. plan). `top_margin`: Tablo 3/4 sayfalarında üst-bilgi yalnız
    başlık DEĞİL, TÜM sütun numarası/etiket bloğu (top≈15-52) — DOĞRULANDI:
    bu blok HER sayfada tekrarlıyor (yalnız ilk sayfada değil); dar bir eşik
    (20pt) bu bloğu dışarıda bırakmaz ve önceki sayfanın SON kaydına "devam
    satırı" olarak yapışıp TYÇ/akreditasyon gibi kuyruk alanları filigran/kod
    metniyle ("(12)","(13)" vb.) kirletir — bkz. oturum notu. Kısım/ücret/web
    sayfalarında (daha kısa/farklı üst-bilgi) varsayılan 20pt yeterlidir."""
    words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
    bottom_margin = float(page.height) - 40.0
    buckets: dict[int, list[tuple[float, str]]] = {}
    for w in words:
        if w["top"] < top_margin or w["top"] > bottom_margin:
            continue
        top_key = round(w["top"])
        buckets.setdefault(top_key, []).append((w["x0"], w["text"]))
    rows: list[_Row] = []
    for top in sorted(buckets):
        ws = sorted(buckets[top])
        if len(ws) < min_words:
            continue
        rows.append(_Row(top=float(top), words=ws))
    return rows


_KOD_RE = re.compile(r"^\d{9}$")


def _leading_kod(row: _Row) -> int | None:
    if not row.words:
        return None
    x0, text = row.words[0]
    if x0 < 40 and _KOD_RE.match(text):
        return int(text)
    return None


def _is_uni_header_line(row: _Row) -> bool:
    """Sol-uç kelime x≈49'da VE 9-haneli kod YOK -> üniversite/fakülte başlığı."""
    if not row.words:
        return False
    x0, _ = row.words[0]
    if _leading_kod(row) is not None:
        return False
    return 40 <= x0 < 70


# --- GuideProgram / GuideData veri modeli --------------------------------------


@dataclass
class GuideProgram:
    kod: int
    prog_ad: str
    tablo: int
    sure: int | None = None
    puan_turu: str | None = None
    kont_genel: int | None = None
    kont_okul_birincisi: int | None = None
    kont_sehit_gazi: int | None = None
    kont_34yas: int | None = None
    kosul_kodlari: list[str] = field(default_factory=list)
    basari_sirasi_onceki: int | None = None
    en_kucuk_puan_onceki: float | None = None
    tyc: str | None = None
    akreditasyon: str | None = None
    uni_ad: str | None = None


@dataclass
class FeeRow:
    uni_ad: str
    duzey: str  # 'Hazırlık' | 'Önlisans' | 'Lisans'
    prog_ad: str
    ucret: float | None
    aciklama: str | None


@dataclass
class Tablo1BRow:
    """Tablo 1B: bir meslek kategorisine başvurabilmek için ulusal en düşük
    başarı sırası (K-2 sert eleme kapısının kaynağı). `puan_turu=None` ise
    kural "İlgili Puan Türünde" uygulanır (Öğretmenlik — adayın kullandığı
    puan türü ne olursa olsun aynı sınır geçerlidir)."""
    kategori: str
    puan_turu: str | None
    baraj_sira: int


@dataclass
class GuideData:
    programs: dict[int, GuideProgram] = field(default_factory=dict)
    kosul_sozluk: dict[str, str] = field(default_factory=dict)
    fees: list[FeeRow] = field(default_factory=list)
    uni_web: dict[str, str] = field(default_factory=dict)
    uni_akreditasyon: dict[str, str] = field(default_factory=dict)
    tablo1b: dict[str, Tablo1BRow] = field(default_factory=dict)
    stats: dict[str, Any] = field(default_factory=dict)


# --- Bölüm tespiti (durum makinesi, yalnızca ileri gider) ---------------------

_MODES = [
    "PRE", "T3", "T4", "SKIP_T5", "KOSUL_DICT", "SKIP_MID",
    "FEE_VAKIF", "FEE_KKTC", "UNIWEB", "DONE",
]
_MODE_RANK = {m: i for i, m in enumerate(_MODES)}

_TRIGGERS: list[tuple[str, str]] = [
    (r"TABLO-3\.\s*Merkez", "T3"),
    (r"TABLO-4\.\s*Merkez", "T4"),
    (r"ÖZEL YETENEK SINAVI SONUÇLARINA GÖRE ÖĞRENCİ ALAN", "SKIP_T5"),
    (r"\(1\.\s*KISIM KOŞULLAR\)", "KOSUL_DICT"),
    (r"TABLO 6A|TABLO-6A|Ortaöğretimdeki Bazı Alanların", "SKIP_MID"),
    (r"VAKIF YÜKSEKÖĞRETİM KURUMLARI ÖĞRENİM ÜCRETLERİ", "FEE_VAKIF"),
    (r"KKTC ÜNİVERSİTELERİN?İN? ÖĞRENİM ÜCRETLERİ|KKTC ÜNİVERSİTELERİ ÖĞRENİM ÜCRETLERİ", "FEE_KKTC"),
    # NOT: kılavuzda arka plan/filigran sızıntısı ara sıra kelime içine fazladan
    # boşluk/karakter ekliyor (ör. "İNTE RNET" — gerçek PDF'te doğrulandı). Bu
    # tetikleyici bu yüzden toleranslı: iki başlık kelimesi arasında serbest
    # metne izin verilir.
    (r"ÜNİVERSİTELERİN.{0,20}ADRESLERİ", "UNIWEB"),
    (r"GENEL AMAÇLI DİLEKÇE", "DONE"),
]
_TRIGGER_RES = [(re.compile(pat), mode) for pat, mode in _TRIGGERS]


def _advance_mode(mode: str, page_text: str) -> str:
    for rx, target in _TRIGGER_RES:
        if _MODE_RANK[target] > _MODE_RANK[mode] and rx.search(page_text):
            mode = target
    return mode


# --- Tablo 3/4 satır ayrıştırma ------------------------------------------------

_UNI_TYPE_RE = re.compile(
    r"^(?P<name>.*?)\s*\((?P<tur>Devlet Üniversitesi|Vakıf Üniversitesi|"
    r"Vakıf Meslek Yüksekokulu|Vakıf Yüksekokulu|KKTC|[^)]*)\)\s*(?P<akred>[A-ZÇĞİÖŞÜ]{2,})?\s*$"
)


def _parse_table_programs(
    pages: list[Any], tablo: int, *, stats: dict[str, Any], logf: Callable[[str], None] | None,
) -> dict[int, GuideProgram]:
    bounds, cols = (_T3_BOUNDS, _T3_COLS) if tablo == 3 else (_T4_BOUNDS, _T4_COLS)
    field_map = _T3_FIELD if tablo == 3 else _T4_FIELD
    out: dict[int, GuideProgram] = {}

    heading_block: list[str] = []
    current_uni: str | None = None
    rows_skipped = 0
    wraps_attached = 0

    def finalize_heading() -> None:
        nonlocal current_uni, heading_block
        if not heading_block:
            return
        text = " ".join(heading_block)
        m = _UNI_TYPE_RE.match(text)
        if m:
            current_uni = m.group("name").strip()
        heading_block = []

    pending: GuideProgram | None = None

    def flush_pending() -> None:
        nonlocal pending
        if pending is not None:
            out[pending.kod] = pending
            pending = None

    for page in pages:
        # top=56: Tablo 3/4'ün HER sayfada tekrarlayan başlık+sütun-etiket+
        # numara-marker bloğu top≈15-52'de biter, gerçek içerik (üni başlığı
        # veya ilk program satırı) top=59'da başlar — doğrulandı (bkz. plan).
        rows = _rows_for_page(page, top_margin=56.0)
        for row in rows:
            words = [(x, t) for x, t in row.words if not _is_noise_char(t)]
            if not words:
                continue
            kod = _leading_kod(row)
            if kod is not None:
                finalize_heading()
                flush_pending()
                gp = GuideProgram(kod=kod, prog_ad="", tablo=tablo, uni_ad=current_uni)
                ad_words: list[str] = []
                col_vals: dict[str, list[str]] = {}
                for x0, text in words[1:]:
                    col = _col_for_x(bounds, cols, x0)
                    if col == 2:
                        ad_words.append(text)
                        continue
                    fname = field_map.get(col)
                    if fname is None:
                        continue
                    col_vals.setdefault(fname, []).append(text)
                gp.prog_ad = " ".join(ad_words)
                _apply_fields(gp, col_vals)
                pending = gp
                continue

            if _is_uni_header_line(row):
                # Kod satırı değil; başlık (üniversite/fakülte) satırı olabilir.
                flush_pending()
                heading_block.append(" ".join(t for _, t in words))
                continue

            # Kod yok, başlık değil -> sarılan program adı ve/veya değer devamı
            # (uzun adlar — özellikle UOLP/çift diploma programları — birden çok
            # görsel satıra yayılır; değerler kod satırında ZATEN dolu olsa bile
            # adın kuyruğu bir sonraki satıra taşabilir, bkz. plan). Her iki
            # bandı da (ad + kalan sütunlar) koşulsuz iliştir.
            if pending is not None:
                extra_ad = [t for x, t in words if _col_for_x(bounds, cols, x) == 2]
                col_vals: dict[str, list[str]] = {}
                for x0, text in words:
                    col = _col_for_x(bounds, cols, x0)
                    if col == 2:
                        continue
                    fname = field_map.get(col)
                    if fname:
                        col_vals.setdefault(fname, []).append(text)
                if extra_ad:
                    pending.prog_ad = (pending.prog_ad + " " + " ".join(extra_ad)).strip()
                if col_vals:
                    _apply_fields(pending, col_vals)
                if extra_ad or col_vals:
                    wraps_attached += 1
                    continue
            rows_skipped += 1
    finalize_heading()
    flush_pending()
    stats[f"t{tablo}RowsSkipped"] = rows_skipped
    stats[f"t{tablo}WrapsAttached"] = wraps_attached
    stats[f"t{tablo}ProgramCount"] = len(out)
    _log(logf, f"  [kilavuz] Tablo {tablo}: {len(out)} program, "
               f"{wraps_attached} sarma iliştirildi, {rows_skipped} satır atlandı")
    return out


_SURE_LO, _SURE_HI = 2, 6         # DB CHECK(sure BETWEEN 2 AND 6) ile birebir
_PUAN_LO, _PUAN_HI = 100.0, 560.0  # DB CHECK(puan BETWEEN 100.0 AND 560.0) ile birebir
_SIRA_MAX = 5_000_000              # aday evreni ~3.5M; üstü kesin parse çöpü
_PT_SEARCH_RE = re.compile(r"(SAY|EA|SÖZ|DİL|TYT)")


def _digits_of(tokens: list[str]) -> str:
    """Bant içindeki TÜM token'ların rakamlarını sırayla birleştirir.

    Kılavuzun çapraz filigranı ("2026-YKS...") sayı bloklarını İKİYE BÖLEBİLİYOR
    veya sayıya HARF YAPIŞTIRABİLİYOR — gerçek PDF'te doğrulandı (bkz.
    VERI_NOTLARI §1.3): Erciyes Makine Müh sırası 154725, pdfplumber'da
    "1" + "54725" diye iki kelime; komşu satırda "İ110886". İlk token'ı almak
    ("[0]") bu yüzden FELAKET üretir (154725 → 1: sihirbazda 1. sıraya
    fırlar). Doğru davranış: banttaki rakamları birleştir, harfleri at."""
    return "".join(re.sub(r"\D", "", t) for t in tokens)


def _apply_fields(gp: GuideProgram, col_vals: dict[str, list[str]]) -> None:
    """DİKKAT-1: her alan K1'in DB CHECK kısıtlarıyla AYNI aralıkta doğrulanır;
    aralık dışı/biçimsiz değer SESSİZCE None'a düşer.
    DİKKAT-2: İLK DEĞER KAZANIR — ana kod satırı önce işlenir; sarma/devam
    satırları yalnız BOŞ alanları doldurabilir, dolu alanı EZEMEZ (devam
    satırına düşen serseri filigran rakamı ana satırın doğru değerini
    değiştirmesin diye). kosul istisna: liste alanıdır, birleşim yapılır
    (koşul listesi gerçekten satır sarabiliyor, ör. "...164," + "320")."""
    if "sure" in col_vals and gp.sure is None:
        d = _digits_of(col_vals["sure"])
        if d:
            v = int(d)
            if _SURE_LO <= v <= _SURE_HI:
                gp.sure = v
    if "puanTuru" in col_vals and gp.puan_turu is None:
        # Filigran harfi yapışabilir ("MSAY") -> alt-dizgi araması ile kurtar.
        m = _PT_SEARCH_RE.search(col_vals["puanTuru"][0].strip())
        if m:
            gp.puan_turu = m.group(1)
    if "genelKont" in col_vals and gp.kont_genel is None:
        d = _digits_of(col_vals["genelKont"])
        gp.kont_genel = int(d) if d and int(d) > 0 else None
    if "okBirKont" in col_vals and gp.kont_okul_birincisi is None:
        d = _digits_of(col_vals["okBirKont"])
        gp.kont_okul_birincisi = int(d) if d and int(d) > 0 else None
    if "sehitGaziKont" in col_vals and gp.kont_sehit_gazi is None:
        d = _digits_of(col_vals["sehitGaziKont"])
        gp.kont_sehit_gazi = int(d) if d and int(d) > 0 else None
    if "y34Kont" in col_vals and gp.kont_34yas is None:
        d = _digits_of(col_vals["y34Kont"])
        gp.kont_34yas = int(d) if d and int(d) > 0 else None
    if "kosul" in col_vals:
        joined = " ".join(col_vals["kosul"])
        raw_codes = [c.strip() for c in re.split(r"[,\s]+", joined) if c.strip()]
        # Her token'daki rakam dizilerini çıkar: "E22," -> 22, "G144" -> 144
        # (yapışan filigran harfi kodu tamamen düşürmesin; önceki salt-rakam
        # süzgeci bu kodları sessizce kaybediyordu).
        codes = [d for c in raw_codes for d in re.findall(r"\d+", c)]
        if codes:
            gp.kosul_kodlari = sorted(set(gp.kosul_kodlari) | set(codes), key=lambda c: (len(c), c))
    if "sirasiOnceki" in col_vals and gp.basari_sirasi_onceki is None:
        d = _digits_of(col_vals["sirasiOnceki"])
        if d:
            v = int(d)
            if 0 < v <= _SIRA_MAX:
                gp.basari_sirasi_onceki = v
    if "puanOnceki" in col_vals and gp.en_kucuk_puan_onceki is None:
        # Bölünmüş/harf-yapışmış puanı birleştir: rakam ve nokta dışını at.
        joined = "".join(re.sub(r"[^\d.]", "", t) for t in col_vals["puanOnceki"])
        try:
            v = float(joined) if joined else None
        except ValueError:
            v = None
        if v is not None and _PUAN_LO <= v <= _PUAN_HI:
            gp.en_kucuk_puan_onceki = v
    if "tyc" in col_vals:
        v = col_vals["tyc"][0].strip()
        if not _is_dash_or_star(v):
            gp.tyc = v
    if "akreditasyon" in col_vals:
        v = " ".join(col_vals["akreditasyon"]).strip()
        if v and not _is_dash_or_star(v):
            gp.akreditasyon = v


# --- Koşul sözlüğü (Bakınız + 1./2. Kısım) -------------------------------------

# DİKKAT: kılavuzda TÜM koşul girdileri "Bk. N" öneki taşır (1. ve 2. Kısım'ın
# ikisi de) — doğrulandı (guide_text.txt taraması). Çıplak "N metin" biçiminde
# bir girdi YOKTUR; böyle bir alternatif eklenirse rastgele bir rakamla
# başlayan filigran/gövde metnine yanlışlıkla eşleşip gerçek "Bk. N" girdisinin
# yerini çalar (bkz. plan/oturum notu — kod '1' çarpışmasıyla tespit edildi).
_KOSUL_ENTRY_RE = re.compile(r"^Bk\.\s*(\d+)\s+(.+)$")


def _clean_watermark_tokens(words: list[tuple[float, str]]) -> str:
    """Kılavuzun bazı sayfalarında arka plan/filigran sızıntısı satır akışına
    izole tek-karakterli sahte kelimeler serpiştiriyor (ör. "... T.C. E İ
    olanlar ..." — gerçek PDF'te doğrulandı). Bu tür 1-karakterlik yalnız-başına
    token'lar (gerçek tek harfli kelime olasılığı çok düşük bu bağlamda)
    filtrelenir; kelimeler tek boşlukla birleştirilir."""
    kept = [t for _, t in words if not _is_noise_char(t)]
    return " ".join(kept)


# --- Tablo 1B — ulusal en düşük başarı sırası (Hukuk/Mühendislik/Mimarlık/Tıp/
# Öğretmenlik/Eczacılık/Diş Hekimliği) -------------------------------------

_TABLO1B_TRIGGER_RE = re.compile(r"Tablo 1B")
_TABLO1B_END_RE = re.compile(r"TABLOLARDA KULLANILAN")
_TABLO1B_ROW_RE = re.compile(
    r"(Hukuk|Mühendislik|Mimarlık|Tıp|Öğretmenlik|Eczacılık|Diş Hekimliği) "
    r"programlarına yerleştirme işleml\w*(.*?)En düşük(.*?)bininci",
    re.DOTALL,
)
_TABLO1B_PT_RE = re.compile(r"(SAY|EA|SÖZ|DİL|TYT)\b")


def _parse_tablo1b(pages: list[Any], *, logf: Callable[[str], None] | None) -> dict[str, Tablo1BRow]:
    """Tablo 1B (kılavuz s.16) — 7 sabit ulusal eşik. Metin tabanlı (extract_text)
    parse edilir; kılavuzun filigran sızıntısı sayı/harf dizilerine ara sıra tek
    karakter ekliyor (ör. "300I.000", "MSAY") — sayı alanı yalnız RAKAMLAR
    süzülerek (`re.sub(r'\\D','',...)`), puan türü ise kelime-sınırı olmadan
    (baştaki yapışık harfi göz ardı ederek) çıkarılır."""
    out: dict[str, Tablo1BRow] = {}
    for page in pages:
        text = page.extract_text() or ""
        for m in _TABLO1B_ROW_RE.finditer(text):
            kategori, mid, num = m.groups()
            digits = re.sub(r"\D", "", num)
            if not digits:
                continue
            baraj = int(digits) * 1000  # "N bininci" = N*1000'inci sıra (ör. "100 bininci" = 100.000)
            pt_m = _TABLO1B_PT_RE.search(mid)
            puan_turu = pt_m.group(1) if pt_m else None  # None = "İlgili Puan Türünde"
            out[kategori] = Tablo1BRow(kategori=kategori, puan_turu=puan_turu, baraj_sira=baraj)
    _log(logf, f"  [kilavuz] Tablo 1B: {len(out)}/7 kategori parse edildi "
               f"({', '.join(f'{k}={v.baraj_sira}' for k, v in out.items())})")
    return out


_KISIM1_RE = re.compile(r"\(1\.\s*KISIM KOŞULLAR\)")
_KISIM2_RE = re.compile(r"\(2\.\s*KISIM KOŞULLAR\)")


def _parse_kosul_dict(pages: list[Any], *, logf: Callable[[str], None] | None) -> dict[str, str]:
    """1. ve 2. Kısım AYRI numaralandırma havuzlarıdır (DOĞRULANDI: kılavuzda her
    ikisi de "Bk. 1" ile başlıyor, farklı içerikle — bkz. plan/oturum notu).
    DB'nin mevcut (yokatlas kaynaklı, doğrulanmış) kod '1' metni 1. Kısım'ın
    metniyle birebir eşleşiyor -> çakışmada 1. KISIM ÖNCELİKLİDİR. 2. Kısım
    yalnız 1. Kısım'da BULUNMAYAN kodları doldurur."""
    kisim1: dict[str, str] = {}
    kisim2: dict[str, str] = {}
    target: dict[str, str] | None = None
    current_kod: str | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal current_kod, buf
        if current_kod is not None and buf and target is not None:
            text = " ".join(buf).strip()
            if text:
                target[current_kod] = text
        current_kod, buf = None, []

    for page in pages:
        for row in _rows_for_page(page):
            line = _clean_watermark_tokens(row.words).strip()
            if not line:
                continue
            if _KISIM1_RE.search(line):
                flush()
                target = kisim1
                continue
            if _KISIM2_RE.search(line):
                flush()
                target = kisim2
                continue
            m = _KOSUL_ENTRY_RE.match(line)
            if m:
                flush()
                current_kod = m.group(1)
                buf = [m.group(2)]
            elif current_kod is not None:
                buf.append(line)
    flush()
    collisions = sorted(set(kisim1) & set(kisim2), key=lambda c: (len(c), c))
    out = {**kisim2, **kisim1}  # kisim1 çakışmada kazanır (doğrulanmış eşleşme)
    _log(logf, f"  [kilavuz] koşul sözlüğü: 1.Kısım={len(kisim1)} 2.Kısım={len(kisim2)} "
               f"birleşik={len(out)} çakışma={len(collisions)}{(' ' + str(collisions)) if collisions else ''}")
    return out


# --- Vakıf/KKTC öğrenim ücretleri -----------------------------------------------

_FEE_UNI_END = 150.0
_FEE_LEVEL_END = 196.0
_FEE_AD_END = 292.0
_FEE_UCRET_END = 345.0


def _parse_fee_pages(pages: list[Any], *, logf: Callable[[str], None] | None) -> list[FeeRow]:
    out: list[FeeRow] = []
    rows: list[_Row] = []
    for page in pages:
        rows.extend(_rows_for_page(page))

    def band(words: list[tuple[float, str]], lo: float, hi: float) -> list[str]:
        return [t for x, t in words if lo <= x < hi]

    def level_of(words: list[tuple[float, str]]) -> str | None:
        toks = band(words, 0, _FEE_LEVEL_END + 30)
        joined = " ".join(toks)
        for lv in ("Hazırlık", "Ön Lisans", "Önlisans", "Lisans"):
            if lv in joined:
                return "Önlisans" if lv == "Ön Lisans" else lv
        return None

    i = 0
    n = len(rows)
    while i < n:
        words = [(x, t) for x, t in rows[i].words if not _is_noise_char(t)]
        lvl = level_of(words)
        if lvl is None:
            i += 1
            continue
        uni_parts = band(words, 0, _FEE_UNI_END)
        ad_parts = band(words, _FEE_LEVEL_END, _FEE_AD_END)
        ucret_tok = band(words, _FEE_AD_END, _FEE_UCRET_END)
        aciklama_parts = band(words, _FEE_UCRET_END, 10_000)

        # 1-satır ileri bak: kod/level yoksa bu bir devam satırıdır (uni adı 2.
        # yarısı ve/veya ad/açıklama sarkması) — kılavuzun uzun üniversite adları
        # rutin olarak 2 satıra sarar (bkz. plan).
        if i + 1 < n:
            nxt_words = [(x, t) for x, t in rows[i + 1].words if not _is_noise_char(t)]
            if nxt_words and level_of(nxt_words) is None:
                uni_parts += band(nxt_words, 0, _FEE_UNI_END)
                ad_parts += band(nxt_words, _FEE_LEVEL_END, _FEE_AD_END)
                aciklama_parts += band(nxt_words, _FEE_UCRET_END, 10_000)
                i += 1

        uni_ad = " ".join(uni_parts).strip()
        prog_ad = " ".join(ad_parts).strip()
        ucret = _parse_tl(" ".join(ucret_tok)) if ucret_tok else None
        aciklama = " ".join(aciklama_parts).strip() or None
        if uni_ad and prog_ad:
            out.append(FeeRow(uni_ad=uni_ad, duzey=lvl, prog_ad=prog_ad, ucret=ucret, aciklama=aciklama))
        i += 1

    _log(logf, f"  [kilavuz] ücret satırı: {len(out)}")
    return out


# --- Üniversite web adresleri ---------------------------------------------------

_URL_RE = re.compile(r"^(?P<name>.*?)\s+(?P<url>https?://\S+)\s*$")


def _parse_uniweb_pages(pages: list[Any], *, logf: Callable[[str], None] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for page in pages:
        text = page.extract_text() or ""
        for line in text.splitlines():
            line = line.strip()
            m = _URL_RE.match(line)
            if m:
                name = m.group("name").strip()
                if name:
                    out[fold(name)] = m.group("url").rstrip(".,;")
    _log(logf, f"  [kilavuz] üniversite web adresi: {len(out)}")
    return out


# --- Üniversite akreditasyonu (Tablo 3/4 başlık satırlarından, taşıma) ---------
# (parse_kilavuz ana döngüsünde toplanır; ayrı bir ikinci geçiş gerektirmez.)


# --- Ücret <-> program eşleştirme (yalnız VAKIF/KKTC) --------------------------

_UNI_BOILERPLATE_RE = re.compile(r"\b(universitesi|uni|universitesi\.)\b")
_PAREN_RE = re.compile(r"\([^)]*\)")


def _norm_uni(name: str) -> str:
    name = _PAREN_RE.sub(" ", name)
    name = fold(name)
    name = _UNI_BOILERPLATE_RE.sub(" ", name)
    return re.sub(r"\s+", " ", name).strip()


def _norm_prog(name: str) -> str:
    name = _PAREN_RE.sub(" ", name)
    name = fold(name)
    return re.sub(r"\s+", " ", name).strip()


def _level_to_birim_tur(duzey: str) -> str | None:
    if duzey == "Lisans":
        return "LISANS"
    if duzey == "Önlisans":
        return "ONLISANS"
    return None  # Hazırlık: belirli bir programa değil, üniversite geneline ait


def match_fees(
    records: list[dict[str, Any]], fees: list[FeeRow], *, logf: Callable[[str], None] | None = None,
) -> tuple[dict[int, tuple[float | None, str | None]], dict[str, Any]]:
    """Kılavuzun vakıf/KKTC ücret satırlarını (uni adı + düzey + program adı ile
    anahtarlı) programs kayıtlarına (kod ile anahtarlı) eşler. Yalnız VAKIF/KKTC
    kayıtlarına uygulanır (devlet programları ücretsiz/harç bazlıdır).

    Eşleşme sırası: (1) tam (norm_uni, düzey, norm_prog); (2) aynı (uni,düzey)
    içinde difflib ratio>=0.90 fuzzy program adı — ÜNİVERSİTE ASLA fuzzy
    eşleşmez (çapraz-üniversite sızıntısını önlemek için). 0 veya belirsiz
    (burs/dil varyantı olmayan >1 farklı program) aday -> ücret NULL + rapora
    örnek (kılavuz-otoriter politika: emin olunmayan durumda veri YAZILMAZ)."""
    import difflib

    by_uni_level: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in records:
        if r["uniTur"] not in ("VAKIF", "KKTC"):
            continue
        key = (_norm_uni(r["uni"]), r["birimTur"])
        by_uni_level.setdefault(key, []).append(r)

    out: dict[int, tuple[float | None, str | None]] = {}
    matched = unmatched = ambiguous = 0
    unmatched_sample: list[str] = []
    ambiguous_sample: list[str] = []

    for fee in fees:
        birim_tur = _level_to_birim_tur(fee.duzey)
        if birim_tur is None:
            continue  # Hazırlık: programa atanamaz, atla
        nuni = _norm_uni(fee.uni_ad)
        nprog = _norm_prog(fee.prog_ad)
        candidates = by_uni_level.get((nuni, birim_tur), [])
        if not candidates:
            unmatched += 1
            if len(unmatched_sample) < 20:
                unmatched_sample.append(f"{fee.uni_ad} / {fee.duzey} / {fee.prog_ad}")
            continue

        exact = [r for r in candidates if _norm_prog(r["prog"]) == nprog or _norm_prog(r["grup"]) == nprog]
        if not exact:
            # Fuzzy: yalnız program adı üzerinde (üniversite zaten sabit).
            scored = [
                (difflib.SequenceMatcher(None, nprog, _norm_prog(r["grup"])).ratio(), r)
                for r in candidates
            ]
            scored = [(s, r) for s, r in scored if s >= 0.90]
            if scored:
                best = max(s for s, _ in scored)
                exact = [r for s, r in scored if s == best]

        if not exact:
            unmatched += 1
            if len(unmatched_sample) < 20:
                unmatched_sample.append(f"{fee.uni_ad} / {fee.duzey} / {fee.prog_ad}")
            continue

        # Burs/dil varyantı grubu mu (aynı grup) yoksa gerçekten farklı
        # programlar mı? Farklıysa belirsiz -> atla (güvenli NULL).
        distinct_groups = {r["grup"] for r in exact}
        if len(distinct_groups) > 1:
            ambiguous += 1
            if len(ambiguous_sample) < 20:
                ambiguous_sample.append(f"{fee.uni_ad} / {fee.duzey} / {fee.prog_ad} -> {len(exact)} aday")
            continue

        matched += 1
        for r in exact:
            out[r["id"]] = (fee.ucret, fee.aciklama)

    total = matched + unmatched + ambiguous
    pct = round(100 * matched / total, 2) if total else 0.0
    stats = {
        "feeMatched": matched, "feeUnmatched": unmatched, "feeAmbiguous": ambiguous,
        "feeMatchPct": pct, "feeUnmatchedSample": unmatched_sample, "feeAmbiguousSample": ambiguous_sample,
    }
    _log(logf, f"  [kilavuz] ücret eşleşme: {matched}/{total} (%{pct}) — "
               f"eşleşmeyen={unmatched}, belirsiz={ambiguous}")
    return out, stats


# --- Ana giriş noktası ----------------------------------------------------------


def parse_kilavuz(pdf_path: str | Path, *, logf: Callable[[str], None] | None = None) -> GuideData:
    """Kılavuz PDF'ini tek geçişte parse eder. Bölüm tespiti tek yönlü (yalnız
    ileri) bir durum makinesiyle yapılır; Tablo 5 (özel yetenek) atlanır."""
    import pdfplumber  # local import: yalnız bu modül pdfplumber gerektirir

    stats: dict[str, Any] = {}
    data = GuideData(stats=stats)

    t3_pages: list[Any] = []
    t4_pages: list[Any] = []
    kosul_pages: list[Any] = []
    fee_vakif_pages: list[Any] = []
    fee_kktc_pages: list[Any] = []
    uniweb_pages: list[Any] = []
    tablo1b_pages: list[Any] = []
    tablo1b_done = False  # "Tablo 1B" başlığı yalnız bir kez görülür, tek geçiş yeter

    mode = "PRE"
    with pdfplumber.open(str(pdf_path)) as pdf:
        stats["totalPages"] = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            # Sayfa 1-2 (kapak + İÇİNDEKİLER) TÜM bölüm başlıklarını ÖNCEDEN,
            # bazen BÜYÜK HARFLE (ör. "GENEL AMAÇLI DİLEKÇE ÖRNEĞİ", "VAKIF
            # YÜKSEKÖĞRETİM KURUMLARI ÖĞRENİM ÜCRETLERİ") içerir -> tetikleyici
            # regex'ler İçindekiler'de erken eşleşip durum makinesini yanlışlıkla
            # sona sıçratır. Ön kapak/İçindekiler mod tespitinden HARİÇ tutulur.
            if i < 2:
                continue
            text = page.extract_text() or ""
            # Tablo 1B, ana T3/T4/... durum makinesinden BAĞIMSIZ, "PRE" modunda
            # (Tablo 3'ten önce) görülür — mode geçişini etkilemeden ayrıca yakala.
            if not tablo1b_done and _TABLO1B_TRIGGER_RE.search(text):
                tablo1b_pages.append(page)
                if _TABLO1B_END_RE.search(text):
                    tablo1b_done = True
            mode = _advance_mode(mode, text)
            if mode == "T3":
                t3_pages.append(page)
            elif mode == "T4":
                t4_pages.append(page)
            elif mode == "KOSUL_DICT":
                kosul_pages.append(page)
            elif mode == "FEE_VAKIF":
                fee_vakif_pages.append(page)
            elif mode == "FEE_KKTC":
                fee_kktc_pages.append(page)
            elif mode == "UNIWEB":
                uniweb_pages.append(page)
            # PRE / SKIP_T5 / SKIP_MID / DONE: içerik atlanır.

        stats["t3Pages"] = len(t3_pages)
        stats["t4Pages"] = len(t4_pages)
        stats["kosulPages"] = len(kosul_pages)
        stats["feeVakifPages"] = len(fee_vakif_pages)
        stats["feeKktcPages"] = len(fee_kktc_pages)
        stats["uniwebPages"] = len(uniweb_pages)
        _log(logf, f"  [kilavuz] bölümler: T3={len(t3_pages)} T4={len(t4_pages)} "
                   f"kosul={len(kosul_pages)} ucret_vakif={len(fee_vakif_pages)} "
                   f"ucret_kktc={len(fee_kktc_pages)} uniweb={len(uniweb_pages)} sayfa")

        t3 = _parse_table_programs(t3_pages, 3, stats=stats, logf=logf)
        t4 = _parse_table_programs(t4_pages, 4, stats=stats, logf=logf)
        data.programs = {**t3, **t4}
        data.kosul_sozluk = _parse_kosul_dict(kosul_pages, logf=logf)
        data.fees = _parse_fee_pages(fee_vakif_pages, logf=logf) + _parse_fee_pages(fee_kktc_pages, logf=logf)
        data.uni_web = _parse_uniweb_pages(uniweb_pages, logf=logf)
        data.tablo1b = _parse_tablo1b(tablo1b_pages, logf=logf)
        stats["tablo1bCount"] = len(data.tablo1b)

    # Üniversite-düzeyi akreditasyon: Tablo 3/4 başlıklarında yakalanan uni_ad'lar
    # üzerinden ikinci bir geçiş gerekmez; GuideProgram.uni_ad zaten current_uni
    # taşır. Akreditasyon token'ı (örn. YÖKAK) heading regex'inde yakalanmadıysa
    # (çoğu satırda yok) bu alan boş kalır — v1'de opsiyonel/soft alan.
    stats["guideProgramCount"] = len(data.programs)
    stats["dictCodeCount"] = len(data.kosul_sozluk)
    stats["feeRowCount"] = len(data.fees)
    stats["uniWebCount"] = len(data.uni_web)
    _log(logf, f"  [kilavuz] TOPLAM: {len(data.programs)} program, "
               f"{len(data.kosul_sozluk)} koşul kodu, {len(data.fees)} ücret satırı, "
               f"{len(data.uni_web)} web adresi")
    return data
