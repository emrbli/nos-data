"""Kesintiden sonra kaldığı yerden devam: ilerleme.json üretir, kalan işi listeler (her adım diskteki çıktıya bakar).

  uv run python -m pipeline.cikmis.kpss.devam            # durumu tara, ilerleme.json yaz, kalan işleri yaz
  uv run python -m pipeline.cikmis.kpss.devam --calistir # kod adımlarını (indir, metin, kirp) eksik belgelerde koştur
  uv run python -m pipeline.cikmis.kpss.devam --girdi    # etiketsiz soruların ajan girdilerini yaz (etiketleme/girdi/)

Adımlar (belge başına): indir, metin, kirp, A (bu hattın etiketi), B (sitenin dizini ya da B2), birlestir, hakem, denetle,
paketle. Durum: bekliyor | bitti | hata. Durum diskteki çıktılardan türetilir; "sürüyor" saklanmaz, yarım kalan adımın
çıktısı eksik olduğu için yeniden "bekliyor" görünür. Etiketleme soru düzeyindedir: A ve B2 dosyalarındaki kimlikler
atlanır, ajan yalnız etiketsiz kimlikleri alır. ilerleme.json atomik yazılır (geçici dosya + rename).
"""

from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path

from .denetle import denetle
from .etiket_birlestir import ETIKETLEME, KARDES
from .ortak import (
    DIST, DIZIN_ADI, ETIKET_DIZINI, ILERLEME, METIN_DIZINI, RAPOR, belgeler, ders_testleri, gruplar, konu_katalogu,
)

ADIMLAR = ("indir", "metin", "kirp", "A", "B", "birlestir", "hakem", "denetle", "paketle")
GIRDI = ETIKETLEME / "girdi"


def _oku(yol: Path):
    return json.loads(yol.read_text(encoding="utf-8")) if yol.exists() else {}


def etiketli_kimlikler() -> tuple[set[str], set[str]]:
    """(A kimlikleri, B2 kimlikleri): ETIKETLEME altındaki bütün A ve B2 dosyalarından."""
    a, b2 = set(_oku(ETIKETLEME / "A.json")), set(_oku(ETIKETLEME / "B2.json"))
    for y in ETIKETLEME.glob("tam-*-A.json"):
        a |= set(_oku(y))
    for y in ETIKETLEME.glob("tam-*-B2.json"):
        b2 |= set(_oku(y))
    return a, b2


def soru_kimlikleri(b: dict) -> list[str]:
    m = _oku(METIN_DIZINI / f"{b['id']}.json")
    return [f"{b['id']}-{t}-{q['no']}" for t, qs in m.get("sorular", {}).items() for q in qs]


def site_kimlikleri(b: dict) -> set[str]:
    sonuc: set[str] = set()
    for t in b["testler"]:
        d = _oku(KARDES / b["id"] / f"{t}.json")
        sonuc |= {f"{b['id']}-{t}-{s['no']}" for s in d.get("sorular", []) if s.get("konu")}
    return sonuc


def tara() -> dict:
    a_set, b2_set = etiketli_kimlikler()
    rapor = _oku(RAPOR)
    hatalar = denetle()
    dist = _oku(DIST / DIZIN_ADI)
    dist_belge = {s["belge"] for s in dist.get("sorular", [])}
    sonuc: dict[str, dict] = {}
    for b in belgeler():
        kim = soru_kimlikleri(b)
        durum: dict[str, dict] = {}

        def yaz(adim: str, bitti: bool, mesaj: str = "", hata: bool = False):
            durum[adim] = {"durum": "bitti" if bitti else ("hata" if hata else "bekliyor"), **({"mesaj": mesaj} if mesaj else {})}

        pdfler = [y for y, _ in gruplar(b)]
        yaz("indir", all(y.exists() and y.read_bytes()[:5] == b"%PDF-" for y in pdfler))
        yaz("metin", bool(kim))
        kirpildi = bool(kim) and all(rapor.get(k, {}).get("durum") == "tamam" for k in kim)
        eksik_kirp = [k for k in kim if k in rapor and rapor[k].get("durum") != "tamam"]
        yaz("kirp", kirpildi, f"{len(eksik_kirp)} soru kırpılamadı" if eksik_kirp else "", hata=bool(eksik_kirp))
        yaz("A", bool(kim) and all(k in a_set for k in kim), f"{sum(k in a_set for k in kim)}/{len(kim)}")
        site = site_kimlikleri(b)
        yaz("B", bool(kim) and all(k in site or k in b2_set for k in kim), f"site {sum(k in site for k in kim)}, B2 {sum(k in b2_set for k in kim)}/{len(kim)}")
        et = [ETIKET_DIZINI / f"{b['id']}-{t}.json" for t in b["testler"]]
        yaz("birlestir", all(y.exists() for y in et))
        belirsiz = sum(1 for y in et if y.exists() for s in _oku(y)["sorular"] if s["etiket"] == "belirsiz")
        yaz("hakem", all(y.exists() for y in et) and belirsiz == 0, f"{belirsiz} belirsiz" if belirsiz else "")
        mine = [h for h in hatalar if h.startswith(f"{b['id']}-") or h.startswith(f"{b['id']}:")]
        yaz("denetle", all(y.exists() for y in et) and not mine, "; ".join(mine[:3]), hata=bool(mine))
        yaz("paketle", b["id"] in dist_belge)
        sonuc[b["id"]] = durum
    return sonuc


def yaz_ilerleme(durum: dict) -> None:
    ozet = {"guncelleme": datetime.datetime.now().isoformat(timespec="seconds"), "adimlar": list(ADIMLAR), "belgeler": durum}
    gecici = ILERLEME.with_suffix(".swap")
    gecici.write_text(json.dumps(ozet, ensure_ascii=False, indent=1), encoding="utf-8")
    gecici.replace(ILERLEME)


def girdi_yaz(durum: dict) -> list[str]:
    """Etiketsiz soruların ajan girdilerini yazar: etiketleme/girdi/A-<belge>.json (KONULAR + SORULAR) ve B2 gerekiyorsa B2-<belge>.json."""
    GIRDI.mkdir(parents=True, exist_ok=True)
    a_set, b2_set = etiketli_kimlikler()
    katalog = konu_katalogu()
    yazilan = []
    for b in belgeler():
        m = _oku(METIN_DIZINI / f"{b['id']}.json")
        if not m:
            continue
        konular = {
            f"{d} ({v['ad']}, {'/'.join(ders_testleri(v))})": v["konular"]
            for d, v in katalog.items() if set(ders_testleri(v)) & set(b["testler"])
        }
        site = site_kimlikleri(b)
        for ad, uygun in (("A", lambda k: k not in a_set), ("B2", lambda k: k not in site and k not in b2_set)):
            metinler = {
                f"{b['id']}-{t}-{q['no']}": q["metin"].replace("\n", " ")
                for t, qs in m["sorular"].items() for q in qs if uygun(f"{b['id']}-{t}-{q['no']}")
            }
            yol = GIRDI / f"{ad}-{b['id']}.json"
            if metinler:
                yol.write_text(json.dumps({"KONULAR": konular, "SORULAR": metinler}, ensure_ascii=False, indent=1), encoding="utf-8")
                yazilan.append(f"{yol.name}: {len(metinler)} soru")
            elif yol.exists():
                yol.unlink()
    return yazilan


def main() -> None:
    if "--calistir" in sys.argv:
        for b in belgeler():
            d = tara()[b["id"]]
            for modul, adim in (("indir", "indir"), ("metin", "metin"), ("kirp", "kirp")):
                if d[adim]["durum"] == "bitti":
                    continue
                if modul == "indir":
                    subprocess.run([sys.executable, "-m", "pipeline.cikmis.kpss.indir"], check=False)
                else:
                    ek = ["--belge", b["id"]]
                    subprocess.run([sys.executable, "-m", f"pipeline.cikmis.kpss.{modul}", *ek], check=False)
                d = tara()[b["id"]]
    durum = tara()
    yaz_ilerleme(durum)
    if "--girdi" in sys.argv:
        for s in girdi_yaz(durum):
            print("girdi:", s)
    bekleyen: dict[str, list[str]] = {}
    for bid, d in durum.items():
        for adim in ADIMLAR:
            if d[adim]["durum"] != "bitti":
                bekleyen.setdefault(adim, []).append(bid)
    print(f"ilerleme: {len(durum)} belge -> {ILERLEME}")
    for adim in ADIMLAR:
        print(f"  {adim:10} bitti {len(durum) - len(bekleyen.get(adim, []))}/{len(durum)}" + (f"  kalan: {', '.join(bekleyen[adim][:6])}{'...' if len(bekleyen[adim]) > 6 else ''}" if adim in bekleyen else ""))


if __name__ == "__main__":
    main()
