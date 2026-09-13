"""MERGE + DEDUP — Plan §5 Faz 2.

Ham K1 kayıtlarını (YÖK Atlas 2026 arama sonucu) tekilleştirir, türetmeleri
uygular ve uygulamanın tükettiği zenginleştirilmiş `programs.json` yapısını üretir.

Yıl modeli (net endpoint çapraz-doğrulamasıyla DÜZELTİLDİ, 2026-07-25):
  Tercih-kilavuz kaydındaki top-level `yil` (=2026) KATALOG/kılavuz yılıdır,
  yerleştirme yılı DEĞİL. "current" (no-suffix) alanları EN SON TAMAMLANAN
  yerleştirmeyi taşır = 2025 (2026 yerleştirmesi Temmuz sonu, henüz yapılmadı).
  Bu, /api/netler/search'ün yerleştirme-yılı etiketleriyle %99.84 birebir
  doğrulandı: net(2025)==current.minPuan, net(2024)==minPuan1, net(2023)==minPuan2.
  - current (no-suffix) -> 2025: p = minPuan, s = basariSirasi (yerleşme sonucu).
    DİKKAT: current'ta gk/gkY YOKTUR -> 2025 satırı k/z (kontenjan/yerleşen) NULL
    taşır; kontenjan alanı (kont2026) 2026 kontenjanıdır, 2025 değil (kullanılmaz).
  - yillar (yerleşme geçmişi): suffix 1/2/3 -> 2024/2023/2022
      k = gk{N} (genel kontenjan), z = gkY{N} (yerleşen),
      p = minPuan{N} (0/boş -> NULL), s = basariSirasi{N}.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .parse_kilavuz import GuideData, GuideProgram, Tablo1BRow, match_fees
from .turkish import fold

# suffix -> GERÇEK yerleşme yılı (yeni -> eski). "" = current (no-suffix) = 2025.
# Net endpoint çapraz-doğrulaması (%99.84) top-level yil=2026'nın katalog yılı
# olduğunu, current'ın 2025 yerleştirmesini taşıdığını kanıtladı (bkz. modül docstring).
_HISTORY_YEARS: list[tuple[int, str]] = [(2025, ""), (2024, "1"), (2023, "2"), (2022, "3")]

# KKTC il adları (universite_turu boş/anormal gelirse yedek türetme için).
_KKTC_ILLER = {"KIBRIS", "LEFKOŞA", "GAZİMAĞUSA", "GİRNE", "LEFKE", "İSKELE", "GÜZELYURT"}

_TREND_MAX_YOY_JUMP = 0.40    # tek yılda >%40 sıra sıçraması -> trend yok (K-11)
_TREND_KONT_TOLERANCE = 0.25  # kontenjan değişimi ±%25 içinde olmalı (K-11)
_MIXED_RATIO = 5.0            # yıllar arası >5x sıra sıçraması -> karma tür şüphesi (K-1)


@dataclass
class MergeResult:
    records: list[dict[str, Any]] = field(default_factory=list)
    kosul_sozluk: dict[str, str] = field(default_factory=dict)
    baraj: list[dict[str, Any]] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    # ÖSYM 2026 kılavuzu (K2, otoriter) ile K1 arasındaki sapmalar — bkz.
    # write_discrepancy_report(). Her biri {kod, field, k1, guide}.
    discrepancies: list[dict[str, Any]] = field(default_factory=list)


def _log(logf: Callable[[str], None] | None, msg: str) -> None:
    if logf:
        logf(msg)


# --- parse yardımcıları -------------------------------------------------------


def _parse_int(value: Any) -> int | None:
    """Tam sayı alanları (kontenjan/sıra/baraj). '80.000' binlik ayracı desteklenir."""
    if value is None:
        return None
    s = str(value).strip()
    if s == "" or s == "<MISSING>":
        return None
    s = s.replace(".", "").replace(",", "").replace(" ", "")
    if s in ("", "-"):
        return None
    try:
        n = int(s)
    except ValueError:
        try:
            n = int(float(str(value)))
        except (TypeError, ValueError):
            return None
    return n if n > 0 else None  # 0 geçersiz (brief §5) -> NULL


def _parse_puan(value: Any) -> float | None:
    """Taban puan (REAL). Nokta ondalık ayracıdır. 0/boş -> NULL."""
    if value is None:
        return None
    s = str(value).strip()
    if s == "" or s == "<MISSING>":
        return None
    try:
        p = float(s)
    except ValueError:
        return None
    return p if p > 0 else None


def _parse_float(value: Any) -> float | None:
    """Genel float parse (0 ve negatif KORUNUR — aralık kararı çağrana bırakılır).
    Net değerleri (0 geçerli) ve kpss1 (istihdam %) için. Nokta ondalık ayracı."""
    if value is None:
        return None
    s = str(value).strip()
    if s == "" or s == "<MISSING>":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _clean_str(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


# --- türetmeler ---------------------------------------------------------------


def derive_uni_tur(raw_value: str | None, uni_adi: str, il_adi: str | None) -> str:
    """API universite_turu -> {DEVLET,VAKIF,KKTC,YURTDISI}. API doğrudan KKTC ve
    YURTDISI * değerlerini döndürür; boş/anormalde ad/il'den yedek türetme yapılır."""
    v = (raw_value or "").strip().upper()
    if v.startswith("YURTDISI") or v.startswith("YURTDIŞI"):
        return "YURTDISI"
    if v == "KKTC":
        return "KKTC"
    if v.startswith("VAKIF"):  # VAKIF, VAKIF MYO
        return "VAKIF"
    if v == "DEVLET":
        return "DEVLET"
    # Yedek: ad/il kalıpları
    name_u = (uni_adi or "").upper()
    if "KKTC" in name_u or (il_adi and il_adi.strip().upper() in _KKTC_ILLER):
        return "KKTC"
    if "(" in name_u and any(x in name_u for x in ("KIRGIZİSTAN", "AZERBAYCAN", "BOSNA", "YURT DIŞI", "YURTDIŞI")):
        return "YURTDISI"
    return "VAKIF" if "VAKIF" in v else "DEVLET"


def normalize_ogr_tur(raw_value: str | None) -> str:
    """API ogrenim_turu_adi -> {Örgün, İkinci Öğretim, Açıköğretim, Uzaktan}.
    K-7 filtresi tam eşleşme yaptığı için kanonik değerler üretilir; bilinmeyen
    değer varsayılan gösterilen 'Örgün' olur.

    "UOLP" (ogrenimTuruId=188) kaynağın karma kovası: 2026 K1 verisinde 113
    kaydın 112'si AÖF programı (Anadolu/Atatürk/İstanbul/Ankara, birim adında
    "(Açıköğretim)"), 1'i gerçek UOLP (Manas Tıp). YÖK Atlas da açıköğretim
    filtresinde bu kovayı Açıköğretim'le birlikte filtreler; aynı davranış
    için kova 'Açıköğretim'e eşlenir. Önceki 'Örgün' eşlemesi AÖF
    programlarını örgün sonuçların içine karıştırıyordu (hata)."""
    v = (raw_value or "").strip()
    vl = v.lower()
    if "açık" in vl or "uolp" in vl:
        return "Açıköğretim"
    if "uzaktan" in vl:
        return "Uzaktan"
    if "ikinci" in vl or "i̇kinci" in vl or vl.startswith("i") and "kinci" in vl:
        return "İkinci Öğretim"
    if "örgün" in vl or "orgun" in vl:
        return "Örgün"
    return "Örgün"


def normalize_birim_tur(raw_value: str | None) -> str:
    v = (raw_value or "").strip().upper()
    if v in ("ÖNLISANS", "ONLISANS", "ÖNLİSANS", "ONLİSANS"):
        return "ONLISANS"
    return "LISANS"


def _detect_flags(birim_adi: str) -> tuple[int, int]:
    """(mtok, kktc_uyruklu) bayrakları — birim_adi kalıplarından (K-8)."""
    upper = birim_adi.upper()
    compact = upper.replace(".", "").replace(" ", "")
    mtok = 1 if ("MTOK" in compact or "M.T.O.K" in upper) else 0
    kktc_uyruklu = 1 if ("KKTC UYRUKLU" in upper or "KKTCUYRUKLU" in compact) else 0
    return mtok, kktc_uyruklu


def _extract_years(item: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    """Yerleşme geçmişini (yillar) çıkarır. (yillar, mixed_suspect) döndürür."""
    puan_turu = item.get("puanTuru") or item.get("_fetch_puan_turu")
    yillar: list[dict[str, Any]] = []
    for year, sfx in _HISTORY_YEARS:
        k = _parse_int(item.get(f"gk{sfx}"))
        z = _parse_int(item.get(f"gkY{sfx}"))
        p = _parse_puan(item.get(f"minPuan{sfx}"))
        s = _parse_int(item.get(f"basariSirasi{sfx}"))
        if k is None and z is None and p is None and s is None:
            continue  # o yıl için hiç veri yok -> satırı ekleme
        yillar.append({"y": year, "k": k, "z": z, "p": p, "s": s, "pt": puan_turu})
    # K-1: yıllar arası >5x sıra sıçraması -> karma puan türü şüphesi
    ranked = [row["s"] for row in yillar if row["s"] is not None]
    mixed = False
    for a, b in zip(ranked, ranked[1:]):
        lo, hi = min(a, b), max(a, b)
        if lo > 0 and hi / lo > _MIXED_RATIO:
            mixed = True
            break
    return yillar, mixed


def _derive_son(yillar: list[dict[str, Any]]) -> tuple[int | None, int | None, float | None]:
    """K-3: en güncel dolu (s!=None) yılın (yil, sıra, puan)."""
    for row in yillar:  # yillar newest->oldest sıralı
        if row["s"] is not None:
            return row["y"], row["s"], row["p"]
    return None, None, None


def _derive_trend(yillar: list[dict[str, Any]], mixed: bool) -> str | None:
    """K-11: istikrarlı iyileşen (rakam küçülen) -> 'yukselen', aksi halde None."""
    if mixed:
        return None
    by_year = {row["y"]: row for row in yillar}
    seq = [by_year.get(y) for y in (2023, 2024, 2025)]
    if any(r is None or r["s"] is None for r in seq):
        return None  # 3 ardışık yıl dolu değil
    s2023, s2024, s2025 = (r["s"] for r in seq)
    # rakam küçülmeli (sıra iyileşmeli): 2023 > 2024 > 2025
    if not (s2023 > s2024 > s2025):
        return None
    # tek yılda >%40 sıçrama yok
    for prev, cur in ((s2023, s2024), (s2024, s2025)):
        if prev > 0 and abs(cur - prev) / prev > _TREND_MAX_YOY_JUMP:
            return None
    # kontenjan değişimi ±%25 içinde
    konts = [r["k"] for r in seq if r["k"] is not None]
    if len(konts) >= 2:
        lo, hi = min(konts), max(konts)
        if lo > 0 and (hi / lo - 1.0) > _TREND_KONT_TOLERANCE:
            return None
    return "yukselen"


def _build_record(item: dict[str, Any]) -> dict[str, Any]:
    kilavuz_kodu = int(item["kilavuzKodu"])
    uni = _clean_str(item.get("universiteAdi")) or ""
    raw_il = _clean_str(item.get("ilAdi")) or _clean_str(item.get("uniIlAdi"))
    ilce = _clean_str(item.get("ilceAdi")) or _clean_str(item.get("uniIlceAdi"))
    prog = _clean_str(item.get("birimAdi")) or ""
    grup = _clean_str(item.get("birimGrupAdi")) or prog  # grup boşsa birim_adi'ne düş
    fakulte = _clean_str(item.get("fymkAdi"))
    puan_turu = _clean_str(item.get("puanTuru")) or item.get("_fetch_puan_turu")
    birim_tur = normalize_birim_tur(item.get("birimTuruAdi"))
    uni_tur = derive_uni_tur(item.get("universiteTuru"), uni, raw_il)
    # YURTDIŞI programlarda API il'i boş gelir; boş string bırakma (plan: boş string yok).
    il = raw_il or ("YURT DIŞI" if uni_tur == "YURTDISI" else "")
    dil = _clean_str(item.get("ogrenimDiliAdi"))
    ogr_tur = normalize_ogr_tur(item.get("ogrenimTuruAdi"))
    burs = _clean_str(item.get("bursOraniAdi"))
    sure = _parse_int(item.get("ogrenimSuresi"))
    kont2026 = _parse_int(item.get("kontenjan"))
    kosul_raw = _clean_str(item.get("kosul")) or ""
    kosul = [c.strip() for c in kosul_raw.split(",") if c.strip()]
    mtok, kktc_uyruklu = _detect_flags(prog)

    yillar, mixed = _extract_years(item)
    son_yil, son_siralama, son_puan = _derive_son(yillar)
    trend = _derive_trend(yillar, mixed)
    baraj_sira = _parse_int(item.get("minBasariSirasi"))

    # Ek nullable alanlar (mevcut kayıtları bozmaz; boş/0 → NULL). kpss2/ogrGor
    # API'de ~%0 dolu olduğu için eklenmez (araştırmayla doğrulandı).
    prof = _parse_int(item.get("prof"))
    doc = _parse_int(item.get("doc"))
    dou = _parse_int(item.get("dou"))
    ar_gor = _parse_int(item.get("arGor"))
    kpss1 = _parse_float(item.get("kpss1"))
    kontenjan_obs = _parse_int(item.get("kontenjanObs"))
    kontenjan_y34 = _parse_int(item.get("kontenjanY34"))
    osym_kilavuz_id = _parse_int(item.get("osymKilavuzId"))
    # YÖK Atlas üniversite logosu endpoint'i için (yokatlas.yok.gov.tr/api/
    # universite-logo?universiteId=...) — K1 satırında zaten geliyor, önceden
    # atılıyordu.
    universite_id = _parse_int(item.get("universiteId"))
    akreditasyon = _clean_str(item.get("akreditasyon"))
    akreditasyon_ack = _clean_str(item.get("akreditasyonAck"))
    uni_akreditasyon = _clean_str(item.get("uniAkreditasyon"))

    return {
        "id": kilavuz_kodu,
        "uni": uni,
        "uniTur": uni_tur,
        "prog": prog,
        "grup": grup,
        "fakulte": fakulte,
        "il": il,
        "ilce": ilce,
        "puanTuru": puan_turu,
        "birimTur": birim_tur,
        "dil": dil,
        "ogrTur": ogr_tur,
        "burs": burs,
        "sure": sure,
        "kosul": kosul,
        "kont2026": kont2026,
        "mtok": mtok,
        "kktcUyruklu": kktc_uyruklu,
        "sonYil": son_yil,
        "sonSiralama": son_siralama,
        "sonPuan": son_puan,
        "trend": trend,
        "mixedSuspect": mixed,
        "prof": prof,
        "doc": doc,
        "dou": dou,
        "arGor": ar_gor,
        "kpss1": kpss1,
        "kontenjanObs": kontenjan_obs,
        "kontenjanY34": kontenjan_y34,
        "osymKilavuzId": osym_kilavuz_id,
        "universiteId": universite_id,
        "akreditasyon": akreditasyon,
        "akreditasyonAck": akreditasyon_ack,
        "uniAkreditasyon": uni_akreditasyon,
        "uniNorm": fold(uni),
        "progNorm": fold(prog),
        "grupNorm": fold(grup),
        "yillar": yillar,
        "_barajSira": baraj_sira,  # baraj tablosuna aktarılır, kayıtta tutulmaz
        "_kosulList": item.get("kosulList") or [],
        # schema v3 (ÖSYM 2026 kılavuzu, K2 — artık OTORİTER): yalnız guide ile
        # doldurulur, K1'de karşılığı yok. Bkz. merge()'deki _apply_guide().
        "ucret": None, "ucretAciklama": None,
        "kontSehitGazi": None, "kontOkulBirincisi": None,
        "tyc": None, "uniWeb": None,
    }


# KAYNAK OTORİTESİ AYRIMI (2026-07-25 olayı sonrası, bkz. VERI_NOTLARI §1.3):
#
# 1) 2026 KILAVUZ VERİSİ (kontenjan, koşul, süre, puan türü, akreditasyon,
#    ücret, baraj): ÖSYM kılavuzu KAYNAĞIN KENDİSİ -> kılavuz OTORİTER,
#    K1'den farklıysa üzerine yazılır.
#
# 2) 2025 YERLEŞME SONUÇLARI (başarı sırası, en küçük puan): bunlar YÖK
#    Atlas'ın yayınladığı TARİHSEL OLGULAR; kılavuz aynı sonuçları yeniden
#    basar. İki kaynak arasında "editöryal fark" OLAMAZ — fark varsa PDF
#    parse hatasıdır (çapraz filigran sayı bloklarını bölüyor: 154725 ->
#    "1"+"54725"; ilk sürüm bunu 1 diye okuyup Erciyes Makine Müh'ü sihirbazda
#    1. sıraya fırlatmıştı, 90 kayıt bozulmuştu). Bu yüzden bu iki alanda
#    ÇAKIŞMADA K1 KAZANIR; kılavuz yalnız K1 NULL ise doldurur, fark rapora
#    "K1 korundu" olarak yazılır.
_GUIDE_OVERWRITE_FIELDS: list[tuple[str, str, str]] = [
    ("kont2026", "kont_genel", "kont2026"),
    ("sure", "sure", "sure"),
    ("puanTuru", "puan_turu", "puanTuru"),
    ("akreditasyon", "akreditasyon", "akreditasyon"),
]
_GUIDE_FILL_ONLY_FIELDS: list[tuple[str, str, str]] = [
    ("sonSiralama", "basari_sirasi_2025", "sonSiralama"),
    ("sonPuan", "en_kucuk_puan_2025", "sonPuan"),
]


def _apply_guide(
    rec: dict[str, Any], gp: GuideProgram, *,
    discrepancies: list[dict[str, Any]], fill_counts: dict[str, int],
    overwrite_counts: dict[str, int], kept_counts: dict[str, int],
) -> None:
    """Kılavuz uygulaması. 2026 alanları: kılavuz otoriter (üzerine yaz +
    raporla). 2025 sonuç alanları: yalnız doldur; çelişkide K1 korunur +
    raporlanır (gerekçe: yukarıdaki KAYNAK OTORİTESİ AYRIMI bloğu)."""
    for rec_key, gp_field, label in _GUIDE_OVERWRITE_FIELDS:
        guide_val = getattr(gp, gp_field)
        if guide_val is None:
            continue
        old = rec.get(rec_key)
        if old is None:
            fill_counts[label] = fill_counts.get(label, 0) + 1
        elif old != guide_val:
            discrepancies.append({"kod": rec["id"], "field": label, "k1": old, "guide": guide_val,
                                  "aksiyon": "kılavuz yazıldı"})
            overwrite_counts[label] = overwrite_counts.get(label, 0) + 1
        rec[rec_key] = guide_val

    # 2025 sonuçları: yalnız K1 NULL ise doldur; makullük kapısı ile
    # (sıra ≤ 5000 iddiası ancak kılavuz puanı da elit düzeydeyse kabul —
    # tek başına küçük bir sayı, bölünmüş-rakam artığı olabilir).
    filled_sira = False
    for rec_key, gp_field, label in _GUIDE_FILL_ONLY_FIELDS:
        guide_val = getattr(gp, gp_field)
        if guide_val is None:
            continue
        old = rec.get(rec_key)
        if old is None:
            if rec_key == "sonSiralama" and guide_val <= 5000 and (
                gp.en_kucuk_puan_2025 is None or gp.en_kucuk_puan_2025 < 450.0
            ):
                continue  # elit sıra iddiası puanla desteklenmiyor -> güvenme
            rec[rec_key] = guide_val
            fill_counts[label] = fill_counts.get(label, 0) + 1
            if rec_key == "sonSiralama":
                filled_sira = True
        elif old != guide_val:
            # ÜZERİNE YAZMA — K1 korunur (2025 sonucunda YÖK Atlas otoriter).
            discrepancies.append({"kod": rec["id"], "field": label, "k1": old, "guide": guide_val,
                                  "aksiyon": "K1 korundu (2025 sonucu)"})
            kept_counts[label] = kept_counts.get(label, 0) + 1

    if guide_val_kosul := gp.kosul_kodlari:
        old_kosul = rec.get("kosul") or []
        if not old_kosul:
            fill_counts["kosul"] = fill_counts.get("kosul", 0) + 1
        elif set(old_kosul) != set(guide_val_kosul):
            discrepancies.append({"kod": rec["id"], "field": "kosul", "k1": old_kosul,
                                  "guide": guide_val_kosul, "aksiyon": "kılavuz yazıldı"})
            overwrite_counts["kosul"] = overwrite_counts.get("kosul", 0) + 1
        rec["kosul"] = guide_val_kosul
    if filled_sira:
        rec["sonYil"] = 2025  # kılavuzdan doldurulan sıra 2025 yerleşme sonucudur
    # Yeni alanlar (yalnız guide'dan gelir, K1'de karşılığı yok -> doğrudan ata).
    if gp.kont_34yas is not None:
        rec["kontenjanY34"] = gp.kont_34yas
    rec["kontSehitGazi"] = gp.kont_sehit_gazi
    rec["kontOkulBirincisi"] = gp.kont_okul_birincisi
    rec["tyc"] = gp.tyc


# Tablo 1B: 5 kategori TEK bir grup_pattern'e karşılık gelir (belirsizlik yok) ->
# doğrudan otoriter üzerine-yazma. Mühendislik/Öğretmenlik GENİŞ kategorilerdir
# (onlarca grup_pattern kapsar, Mühendislik'in kılavuzda adı geçen istisnaları
# vardır) -> yalnız DOĞRULAMA (üzerine yazma YOK; istisna listesinin tam
# olmaması yanlışlıkla doğru bir K1 istisna değerini ezebilir).
_TABLO1B_SINGLE_GRUP: dict[str, str] = {
    "Hukuk": "Hukuk", "Mimarlık": "Mimarlık", "Tıp": "Tıp",
    "Eczacılık": "Eczacılık", "Diş Hekimliği": "Diş Hekimliği",
}
_MUHENDISLIK_EXCLUDE_KEYWORDS = [
    "orman", "ziraat", "tarım bilimleri", "ağaç işleri endüstri", "biyosistem",
    "balıkçılık teknolojisi", "su ürünleri",
]


def _apply_tablo1b(
    baraj_by_key: dict[tuple[str, str], int], tablo1b: dict[str, Tablo1BRow], *,
    discrepancies: list[dict[str, Any]], logf: Callable[[str], None] | None,
) -> dict[str, Any]:
    """Tablo 1B (ulusal en düşük başarı sırası) uygular. `baraj_by_key`'i YERİNDE
    değiştirir (çağıran, `baraj` listesini bundan SONRA kurmalı)."""
    overrides: list[str] = []
    for kategori, grup in _TABLO1B_SINGLE_GRUP.items():
        row = tablo1b.get(kategori)
        if row is None or row.puan_turu is None:
            continue
        key = (grup, row.puan_turu)
        old = baraj_by_key.get(key)
        if old != row.baraj_sira:
            discrepancies.append({"kod": f"baraj:{grup}/{row.puan_turu}", "field": "baraj_sira",
                                   "k1": old, "guide": row.baraj_sira})
            overrides.append(f"{grup}/{row.puan_turu}: {old} -> {row.baraj_sira}")
        baraj_by_key[key] = row.baraj_sira  # kılavuz otoriter (Tablo 1B)

    validated = 0
    violations: list[str] = []
    muh = tablo1b.get("Mühendislik")
    if muh is not None and muh.puan_turu is not None:
        for (grup, pt), val in baraj_by_key.items():
            gl = grup.lower()
            if "mühendis" not in gl or any(kw in gl for kw in _MUHENDISLIK_EXCLUDE_KEYWORDS):
                continue
            validated += 1
            if pt == muh.puan_turu and val != muh.baraj_sira:
                violations.append(f"{grup}/{pt}: K1={val} != Tablo1B={muh.baraj_sira}")
    ogr = tablo1b.get("Öğretmenlik")
    if ogr is not None:
        for (grup, pt), val in baraj_by_key.items():
            if "öğretmenliği" not in grup.lower():
                continue
            validated += 1
            if val != ogr.baraj_sira:
                violations.append(f"{grup}/{pt}: K1={val} != Tablo1B={ogr.baraj_sira}")

    if violations:
        _log(logf, f"  [Tablo1B] Mühendislik/Öğretmenlik doğrulama UYARISI "
                   f"({len(violations)}): {violations[:10]}")
    _log(logf, f"  [Tablo1B] {len(overrides)} baraj otoriter yazıldı ({overrides}), "
               f"{validated} kayıt (Mühendislik/Öğretmenlik) doğrulandı")
    return {"tablo1bOverrides": overrides, "tablo1bValidatedCount": validated,
            "tablo1bViolations": violations}


def merge(
    k1_programs: list[dict[str, Any]],
    k2_map: dict[int, dict[str, Any]] | None = None,
    *,
    guide: GuideData | None = None,
    logf: Callable[[str], None] | None = None,
) -> MergeResult:
    """K1 ham kayıtlarını tekilleştirip zenginleştirilmiş kayıtlara dönüştürür.

    `guide`: ÖSYM 2026 kılavuzu parse çıktısı (parse_kilavuz.parse_kilavuz).
    Verilirse OTORİTER kaynak olarak uygulanır (bkz. _apply_guide) — kont2026,
    kosul, sure, puanTuru, akreditasyon, sonSiralama/sonPuan/sonYil üzerine
    yazılır (K1'den farklıysa sapma kaydedilir); şehit/gazi + 34-yaş + TYÇ +
    ücret + üniversite web adresi yalnız guide'dan doldurulur. `k2_map` (eski
    XLS/PDF taslağı) geriye dönük uyumluluk için tutulur, artık kullanılmaz."""
    k2_map = k2_map or {}
    seen: dict[int, dict[str, Any]] = {}
    dup_count = 0
    kosul_sozluk: dict[str, str] = {}
    baraj_by_key: dict[tuple[str, str], int] = {}
    kosul_present = 0            # ≥1 koşul kodu olan kayıt (K1-inline doluluk)
    baraj_present = 0            # başarı sırası barajı olan kayıt (K1-inline doluluk)
    used_codes: set[str] = set() # tüm kayıtlarda kullanılan koşul kodları (K-5 kapsama)

    for item in k1_programs:
        try:
            code = int(item["kilavuzKodu"])
        except (KeyError, TypeError, ValueError):
            _log(logf, f"  [uyarı] kilavuzKodu eksik/geçersiz, atlandı: {item.get('birimAdi')!r}")
            continue
        if code in seen:
            dup_count += 1
            continue  # ilk kayıt korunur (brief §3)
        rec = _build_record(item)

        # kosul_sozluk (K-5): tüm kosulList girdilerini global sözlüğe topla
        for entry in rec.pop("_kosulList"):
            if isinstance(entry, dict):
                for kod, aciklama in entry.items():
                    if kod not in kosul_sozluk and aciklama:
                        kosul_sozluk[str(kod)] = str(aciklama).strip()

        # K1-inline doluluk izleme (yalnız korunan kayıtlar)
        if rec["kosul"]:
            kosul_present += 1
            used_codes.update(rec["kosul"])

        # baraj (K-2): (grup, puan_turu) -> baraj_sira
        baraj_sira = rec.pop("_barajSira")
        if baraj_sira is not None and rec["puanTuru"]:
            baraj_present += 1
            key = (rec["grup"], rec["puanTuru"])
            # Başarı sırasında KÜÇÜK sayı = daha yüksek eşik = daha KATI. Barajlar grup
            # bazında ulusal olarak tekdüzedir; farklı değer görülürse anomali -> en katı
            # (min) tut ve logla (kullanıcıyı yanlışlıkla yerleşemeyeceği gruba sokmamak için).
            prev = baraj_by_key.get(key)
            if prev is None:
                baraj_by_key[key] = baraj_sira
            elif prev != baraj_sira:
                baraj_by_key[key] = min(prev, baraj_sira)
                _log(logf, f"  [baraj] {key} için farklı baraj: {prev} vs {baraj_sira} "
                           f"-> en katı {min(prev, baraj_sira)} tutuldu")

        # K2 çapraz-kontrol (opsiyonel): kont2026 sapması logla, K1'i otoriter kabul et
        if code in k2_map:
            k2_kont = k2_map[code].get("kont2026")
            if k2_kont is not None and rec["kont2026"] is not None and k2_kont != rec["kont2026"]:
                _log(logf, f"  [K2 sapma] {code}: K1 kont={rec['kont2026']} != K2 kont={k2_kont}")

        seen[code] = rec

    records = list(seen.values())

    # --- Kılavuz (K2, otoriter) uygulaması --------------------------------
    discrepancies: list[dict[str, Any]] = []
    guide_fill_counts: dict[str, int] = {}
    guide_overwrite_counts: dict[str, int] = {}
    guide_kept_counts: dict[str, int] = {}
    guide_matched = 0
    fee_stats: dict[str, Any] = {}
    tablo1b_stats: dict[str, Any] = {}
    if guide is not None:
        for r in records:
            gp = guide.programs.get(r["id"])
            if gp is None:
                continue
            guide_matched += 1
            _apply_guide(r, gp, discrepancies=discrepancies,
                         fill_counts=guide_fill_counts, overwrite_counts=guide_overwrite_counts,
                         kept_counts=guide_kept_counts)
            # uni_web: guide'ın üniversite adı üzerinden (uniNorm eşleşmesi).
            web = guide.uni_web.get(r["uniNorm"])
            if web:
                r["uniWeb"] = web

        # kosul_sozluk: guide otoriter (resmî metin) + guide'da olmayan K1
        # kodlarıyla doldur (guide çakışmada kazanır).
        for kod, aciklama in guide.kosul_sozluk.items():
            kosul_sozluk[kod] = aciklama  # guide K1'in üzerine yazar

        # Ücret eşleştirme (yalnız VAKIF/KKTC) — bkz. parse_kilavuz.match_fees.
        fee_map, fee_stats = match_fees(records, guide.fees, logf=logf)
        for r in records:
            fee = fee_map.get(r["id"])
            if fee is not None:
                r["ucret"], r["ucretAciklama"] = fee

        # Tablo 1B (ulusal en düşük başarı sırası) — bkz. _apply_tablo1b.
        # baraj_by_key'i MUTATE eder (baraj listesi bundan SONRA kurulur).
        if guide.tablo1b:
            tablo1b_stats = _apply_tablo1b(baraj_by_key, guide.tablo1b,
                                           discrepancies=discrepancies, logf=logf)

        _log(logf, f"  [kilavuz] uygulandı: {guide_matched}/{len(records)} program eşleşti, "
                   f"{len(discrepancies)} sapma, doldurma={guide_fill_counts}, "
                   f"üzerine-yazma={guide_overwrite_counts}, "
                   f"K1-korundu(2025 sonucu)={guide_kept_counts}")

    # Tamamlama taraması kayıtları (API puanTuru NULL — ör. Manas Filoloji):
    # puan türünü yukarıda kılavuz doldurdu; yillar satırlarındaki pt izini de
    # geri doldur (yearly_stats.puan_turu NOT NULL). Kılavuz da dolduramadıysa
    # kayıt GÜVENLE ATILIR (DB CHECK'i patlatmak yerine) + loglanır.
    for r in records:
        if r["puanTuru"]:
            for row in r["yillar"]:
                if row["pt"] is None:
                    row["pt"] = r["puanTuru"]
    no_pt = [r for r in records if not r["puanTuru"]]
    if no_pt:
        _log(logf, f"  [uyarı] puan türü çözülemeyen {len(no_pt)} kayıt atıldı "
                   f"(API null + kılavuz eşleşmesi yok): "
                   f"{[(r['id'], r['prog'][:40]) for r in no_pt[:10]]}")
        records = [r for r in records if r["puanTuru"]]

    baraj = [
        {"grupPattern": g, "puanTuru": pt, "barajSira": s}
        for (g, pt), s in sorted(baraj_by_key.items())
    ]

    # istatistikler (validate/rapor için)
    n = len(records)
    null_sira = sum(1 for r in records if r["sonSiralama"] is None)
    mixed_n = sum(1 for r in records if r["mixedSuspect"])
    trend_n = sum(1 for r in records if r["trend"] == "yukselen")
    full_3yr = sum(
        1 for r in records
        if {2023, 2024, 2025} <= {row["y"] for row in r["yillar"] if row["s"] is not None}
    )
    uni_tur_dist: dict[str, int] = {}
    pt_dist: dict[str, int] = {}
    for r in records:
        uni_tur_dist[r["uniTur"]] = uni_tur_dist.get(r["uniTur"], 0) + 1
        pt_dist[r["puanTuru"]] = pt_dist.get(r["puanTuru"], 0) + 1

    # K-5 kapsama: kullanılan koşul kodlarından kaç tanesinin açıklaması var
    uncovered = sorted(used_codes - set(kosul_sozluk.keys()), key=lambda c: (len(c), c))

    stats = {
        "programCount": n,
        "duplicatesDropped": dup_count,
        "nullSonSiralama": null_sira,
        "nullSonSiralamaPct": round(100 * null_sira / n, 2) if n else 0,
        "full3YearCount": full_3yr,
        "full3YearPct": round(100 * full_3yr / n, 2) if n else 0,
        "mixedSuspectCount": mixed_n,
        "trendYukselenCount": trend_n,
        "kosulSozlukCount": len(kosul_sozluk),
        "barajCount": len(baraj),
        # K1-inline alan doluluğu (team-lead isteği)
        "kosulPresentCount": kosul_present,
        "kosulPresentPct": round(100 * kosul_present / n, 2) if n else 0,
        "barajPresentCount": baraj_present,
        "barajPresentPct": round(100 * baraj_present / n, 2) if n else 0,
        "usedKosulCodes": len(used_codes),
        "kosulCodeCoveragePct": round(100 * (len(used_codes) - len(uncovered)) / len(used_codes), 2) if used_codes else 100.0,
        "uncoveredKosulCount": len(uncovered),
        "uncoveredKosulSample": uncovered[:15],
        "uniTurDist": uni_tur_dist,
        "puanTuruDist": pt_dist,
    }
    if guide is not None:
        stats.update({
            "guideProgramCount": len(guide.programs),
            "guideMatched": guide_matched,
            "guideCoveragePct": round(100 * guide_matched / n, 2) if n else 0.0,
            "guideDiscrepancyCount": len(discrepancies),
            "guideFillCounts": guide_fill_counts,
            "guideOverwriteCounts": guide_overwrite_counts,
            "guideKeptK1Counts": guide_kept_counts,
            "guideOverwritePctByField": {
                label: round(100 * cnt / guide_matched, 2) if guide_matched else 0.0
                for label, cnt in guide_overwrite_counts.items()
            },
            "guideParserStats": guide.stats,
            **{f"guide{k[0].upper()}{k[1:]}": v for k, v in fee_stats.items()},
            **tablo1b_stats,
        })
    _log(logf, f"  merge: {n} kayıt, {dup_count} duplicate atıldı, "
               f"{len(kosul_sozluk)} koşul kodu, {len(baraj)} baraj kaydı")
    return MergeResult(records=records, kosul_sozluk=kosul_sozluk, baraj=baraj, stats=stats,
                       discrepancies=discrepancies)


# --- net_profiles (brief §10) -------------------------------------------------

# net_profiles kolon adı -> ham JSON (camelCase) anahtarı. Değerler REAL net;
# geçerli aralık 0-40 (ders bazlı soru sayısı sınırı), aralık dışı → NULL + log.
_NET_FIELD_KEYS: list[tuple[str, str]] = [
    ("tyt_trk_net", "tytTrkNet"),
    ("tyt_sos_net", "tytSosNet"),
    ("tyt_mat_net", "tytMatNet"),
    ("tyt_fen_net", "tytFenNet"),
    ("ayt_mat_net", "aytMatNet"),
    ("ayt_fiz_net", "aytFizNet"),
    ("ayt_kim_net", "aytKimNet"),
    ("ayt_bio_net", "aytBioNet"),
    ("ayt_tde_net", "aytTdeNet"),
    ("ayt_trh1_net", "aytTrh1Net"),
    ("ayt_cog1_net", "aytCog1Net"),
    ("ayt_trh2_net", "aytTrh2Net"),
    ("ayt_cog2_net", "aytCog2Net"),
    ("ayt_fel_net", "aytFelNet"),
    ("ayt_din_net", "aytDinNet"),
    ("ydt_ydil_net", "ydtYdilNet"),
]

_NET_MIN = 0.0                     # ders bazlı net alt sınırı (brief §10)
_NET_MAX_DEFAULT = 40.0            # TYT/AYT ders başına en fazla ~40 soru
# YDT (Yabancı Dil Testi, DİL puan türü) 80 soruludur → ydt_ydil_net 0-80.
# Brief §10 "0-40" TYT/AYT için; YDT istisnası ayrıca ele alınır (yoksa geçerli
# DİL netleri yanlışlıkla NULL'lanır — ilk tam koşuda 1158 satırda görüldü).
_NET_MAX_BY_FIELD: dict[str, float] = {"ydt_ydil_net": 80.0}
_OBP_MIN, _OBP_MAX = 100.0, 500.0  # OBP aralığı (brief §10)


def merge_netler(
    raw_rows: list[dict[str, Any]],
    known_kilavuz_kodlari: set[int],
    *,
    logf: Callable[[str], None] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Ham net satırlarını (kilavuz_kodu, yil, katsayi) anahtarıyla tekilleştirir,
    programs'ta karşılığı olmayanları eler, net/OBP aralık kurallarını uygular.

    - Dedup: aynı anahtarda ilk kayıt korunur, sonrakiler loglanır (programs
      dedup deseniyle tutarlı).
    - Eşleşme: `known_kilavuz_kodlari` dışındaki kilavuz kodları elenir + loglanır
      (FK ihlalini önler; brief §10 ≥%90 eşleşme hedefi).
    - Aralık: net alanları 0-40, OBP 100-500 dışı → NULL + log; negatif → NULL + log.

    Döndürür: (net_rows, stats). net_rows dict anahtarları net_profiles kolonlarıyla
    birebir (build_sqlite.py insert eder).
    """
    # 1) dedup (ilk kayıt kazanır)
    seen: dict[tuple[int, int | None, float | None], dict[str, Any]] = {}
    dedup_count = 0
    skipped_bad_key = 0
    for item in raw_rows:
        kk = _parse_int(item.get("kilavuzKodu"))
        yil = _parse_int(item.get("yil"))
        if kk is None or yil is None:
            skipped_bad_key += 1
            continue
        katsayi = _parse_float(item.get("katsayi"))
        key = (kk, yil, katsayi)
        if key in seen:
            dedup_count += 1
            continue
        seen[key] = item

    # 2) eşleşme + aralık uygulaması
    net_rows: list[dict[str, Any]] = []
    matched = 0
    unmatched = 0
    unmatched_sample: list[int] = []
    negatif_count = 0
    aralik_disi_count = 0
    by_year_total: dict[int, int] = {}      # yıl → distinct anahtar sayısı
    by_year_matched: dict[int, int] = {}    # yıl → eşleşen (programs'ta olan) sayısı
    for (kk, yil, katsayi), item in seen.items():
        by_year_total[yil] = by_year_total.get(yil, 0) + 1
        if kk not in known_kilavuz_kodlari:
            unmatched += 1
            if len(unmatched_sample) < 15:
                unmatched_sample.append(kk)
            continue
        matched += 1
        by_year_matched[yil] = by_year_matched.get(yil, 0) + 1

        taban_puan = _parse_puan(item.get("tabanPuan"))

        obp = _parse_float(item.get("obp"))
        if obp is not None and (obp < 0):
            negatif_count += 1
            obp = None
        elif obp is not None and (obp < _OBP_MIN or obp > _OBP_MAX):
            aralik_disi_count += 1
            _log(logf, f"  [net aralık] {kk}/{yil} obp={obp} ∉ [{_OBP_MIN},{_OBP_MAX}] → NULL")
            obp = None

        rec: dict[str, Any] = {
            "kilavuz_kodu": kk,
            "yil": yil,
            "katsayi": katsayi,
            "taban_puan": taban_puan,
            "obp": obp,
        }
        for col, raw_key in _NET_FIELD_KEYS:
            v = _parse_float(item.get(raw_key))
            if v is None:
                rec[col] = None
                continue
            hi = _NET_MAX_BY_FIELD.get(col, _NET_MAX_DEFAULT)
            if v < 0:
                negatif_count += 1
                rec[col] = None
            elif v < _NET_MIN or v > hi:
                aralik_disi_count += 1
                _log(logf, f"  [net aralık] {kk}/{yil} {col}={v} ∉ [{_NET_MIN},{hi}] → NULL")
                rec[col] = None
            else:
                rec[col] = v
        net_rows.append(rec)

    distinct = matched + unmatched
    eslesme_orani = round(100 * matched / distinct, 2) if distinct else 0.0
    # Yıl bazında eşleşme oranı (tanı + birincil-yıl kapısı için). Eski yıl kodları
    # güncel kılavuzda olmadığından oran yıl eskidikçe düşer (2025 en yüksek).
    eslesme_by_yil = {
        yil: round(100 * by_year_matched.get(yil, 0) / by_year_total[yil], 2)
        for yil in sorted(by_year_total, reverse=True)
    }
    if unmatched:
        _log(logf, f"  [net eşleşme] {unmatched} eşleşmeyen kilavuz_kodu elendi "
                   f"(örnek: {unmatched_sample})")
    _log(logf, f"  [net eşleşme] yıl-bazlı oran: {eslesme_by_yil}")
    stats = {
        "netRowCount": len(net_rows),
        "netDistinctKeys": distinct,
        "netMatched": matched,
        "netUnmatched": unmatched,
        "eslesmeOrani": eslesme_orani,
        "eslesmeOraniByYil": eslesme_by_yil,
        "dedupCount": dedup_count,
        "skippedBadKey": skipped_bad_key,
        "negatifCount": negatif_count,
        "aralikDisiCount": aralik_disi_count,
        "unmatchedSample": unmatched_sample,
    }
    _log(logf, f"  merge_netler: {len(net_rows)} net satırı, eşleşme %{eslesme_orani} "
               f"(yıl-bazlı {eslesme_by_yil}), {dedup_count} dup, {negatif_count} negatif, "
               f"{aralik_disi_count} aralık-dışı NULL'landı")
    return net_rows, stats


# --- programs.json çıktısı ----------------------------------------------------


def content_sha256(result: MergeResult) -> str:
    """Veri-içeriği sha256'sı (exportedAt'ten BAĞIMSIZ — idempotans için).
    Aynı kaynak -> aynı sha256."""
    payload = {
        "programs": sorted(result.records, key=lambda r: r["id"]),
        "kosulSozluk": dict(sorted(result.kosul_sozluk.items())),
        "baraj": sorted(result.baraj, key=lambda b: (b["grupPattern"], b["puanTuru"])),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def write_programs_json(
    result: MergeResult,
    path: str | Path,
    *,
    exported_at: str,
    schema_version: int = 1,
) -> str:
    """Zenginleştirilmiş programs.json'ı yazar, veri-içeriği sha256'sını döndürür."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sha = content_sha256(result)
    doc = {
        "meta": {
            "exportedAt": exported_at,
            "source": "yokatlas.yok.gov.tr (K1) + ÖSYM 2026 Kılavuzu (K2, OTORİTER)",
            "programCount": len(result.records),
            "sha256": sha,
            "dataYear": 2025,
            "schemaVersion": schema_version,
        },
        "kosulSozluk": dict(sorted(result.kosul_sozluk.items())),
        "baraj": sorted(result.baraj, key=lambda b: (b["grupPattern"], b["puanTuru"])),
        "programs": sorted(result.records, key=lambda r: r["id"]),
    }
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return sha


# --- Kılavuz (K2) sapma raporu -------------------------------------------------

_DISCREPANCY_SAMPLE_CAP = 50


def write_discrepancy_report(result: MergeResult, path: str | Path) -> None:
    """ÖSYM 2026 kılavuzu (K2, otoriter) ile K1 (yokatlas) arasındaki sapmaları
    yazar. AYRI bir dosyadır (validation_report.md'nin sync-db PASS kapısını
    etkilememesi için, bkz. plan). Guide verilmediyse (--allow-missing-k2 veya
    parse hatası) bunu açıkça belirtir."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    stats = result.stats
    lines: list[str] = ["# NOS Kılavuz (K2) Sapma Raporu", ""]

    if "guideCoveragePct" not in stats:
        lines.append("Kılavuz bu koşuda uygulanmadı (K2 yok / `--skip-kilavuz` / parse hatası). "
                     "Tüm veriler K1 (yokatlas) kaynaklıdır.")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    lines.append(f"- Kılavuzdaki program sayısı: **{stats['guideProgramCount']}**")
    lines.append(f"- K1 ile eşleşen: **{stats['guideMatched']}** (kapsama **%{stats['guideCoveragePct']}**)")
    lines.append(f"- Toplam alan sapması (K1 ≠ kılavuz, kılavuz yazıldı): **{stats['guideDiscrepancyCount']}**")
    lines.append("")
    lines.append("## Alan bazında doldurma / üzerine-yazma / K1-korundu")
    lines.append("> 2026 alanlarında (kont2026/kosul/sure/puanTuru/akreditasyon) kılavuz otoriter →")
    lines.append("> çelişkide kılavuz yazılır. 2025 SONUÇ alanlarında (sonSiralama/sonPuan) YÖK Atlas")
    lines.append("> otoriter → çelişkide K1 korunur (kılavuz PDF filigranı sayıları bölebiliyor).")
    lines.append("")
    lines.append("| Alan | Doldurma (K1 NULL idi) | Üzerine-yazma (kılavuz kazandı) | K1 korundu | Üzerine-yazma % |")
    lines.append("|---|---|---|---|---|")
    fields = sorted(set(stats.get("guideFillCounts", {})) | set(stats.get("guideOverwriteCounts", {}))
                    | set(stats.get("guideKeptK1Counts", {})))
    for f in fields:
        fill = stats.get("guideFillCounts", {}).get(f, 0)
        ow = stats.get("guideOverwriteCounts", {}).get(f, 0)
        kept = stats.get("guideKeptK1Counts", {}).get(f, 0)
        pct = stats.get("guideOverwritePctByField", {}).get(f, 0.0)
        lines.append(f"| {f} | {fill} | {ow} | {kept} | %{pct} |")
    lines.append("")
    lines.append("## Tablo 1B (ulusal en düşük başarı sırası — Hukuk/Mimarlık/Tıp/Eczacılık/Diş Hekimliği)")
    overrides = stats.get("tablo1bOverrides") or []
    if overrides:
        lines.append("Otoriter üzerine yazıldı:")
        for o in overrides:
            lines.append(f"- {o}")
    else:
        lines.append("- Değişiklik yok (K1 zaten Tablo 1B ile uyumluydu, veya Tablo 1B parse edilemedi).")
    violations = stats.get("tablo1bViolations") or []
    lines.append(f"- Mühendislik/Öğretmenlik (geniş kategori, yalnız DOĞRULAMA — üzerine yazılmaz): "
                 f"{stats.get('tablo1bValidatedCount', 0)} kayıt kontrol edildi, {len(violations)} sapma")
    for v in violations[:15]:
        lines.append(f"  - ⚠️ {v}")
    lines.append("")
    lines.append("## Ücret eşleşmesi (yalnız VAKIF/KKTC)")
    lines.append(f"- Eşleşen: {stats.get('guideFeeMatched', 0)}  ·  "
                 f"Eşleşmeyen: {stats.get('guideFeeUnmatched', 0)}  ·  "
                 f"Belirsiz: {stats.get('guideFeeAmbiguous', 0)}  ·  "
                 f"Oran: **%{stats.get('guideFeeMatchPct', 0.0)}**")
    unmatched_sample = stats.get("guideFeeUnmatchedSample") or []
    if unmatched_sample:
        lines.append("")
        lines.append("### Eşleşmeyen ücret satırı örnekleri")
        for s in unmatched_sample[:15]:
            lines.append(f"- {s}")
    lines.append("")
    lines.append(f"## Sapma örnekleri (ilk {_DISCREPANCY_SAMPLE_CAP})")
    lines.append("| Kod | Alan | K1 | Kılavuz | Aksiyon |")
    lines.append("|---|---|---|---|---|")
    for d in result.discrepancies[:_DISCREPANCY_SAMPLE_CAP]:
        lines.append(f"| {d['kod']} | {d['field']} | {d['k1']} | {d['guide']} | {d.get('aksiyon', '')} |")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
