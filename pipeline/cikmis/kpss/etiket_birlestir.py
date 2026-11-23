"""İki bağımsız etiketleme ve hakem kararlarından KPSS etiket dosyaları (YKS `etiket_birlestir.py`'nin karşılığı).

Girdi (yerel, yerel/kpss/etiketleme/):
  A.json, tam-<belge>-A.json   bu hattaki etiketleme: {soru kimliği: konu anahtarı} / {kimlik: {"konu", "ek"}}
  B (kardeş)   nosakademi-web `data/kpss/cikmis-dizin/<belge>/<test>.json` (bağımsız ayrı etiketleme; varsa)
  B2.json      kardeş dizinde bulunmayan sorular için ikinci bağımsız etiketleme: {kimlik: {"konu", "ek"}}
  hakem.json   uyuşmayanlar için sayfa/metin üzerinden üçüncü karar: {kimlik: {"konu", "ekKonu"?}}
Uyuşan konu `cift-onay`, hakemin karar verdiği `hakem`, kararsız `belirsiz`. Sayfa ve cevap `metin.py`
çıktısındandır (cevap: ÖSYM'nin sayfadaki "DOĞRU CEVAP" satırı; kardeş dizinin cevabı kullanılmaz).

Çıktı (commit edilir): etiket/<belge>-<test>.json (yalnız künye; soru metni yok).

  uv run python -m pipeline.cikmis.kpss.etiket_birlestir [--kardes <cikmis-dizin yolu>]
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

from .ortak import ETIKET_DIZINI, HAM, KOK, METIN_DIZINI, belgeler, konu_katalogu

ETIKETLEME = HAM / "etiketleme"
KARDES = KOK.parent / "nosakademi-web" / "data" / "kpss" / "cikmis-dizin"


def anahtar_ders() -> dict[str, str]:
    sonuc: dict[str, str] = {}
    for ders, v in konu_katalogu().items():
        for k in v["konular"]:
            if k in sonuc:
                raise SystemExit(f"konu anahtarı iki derste: {k}")
            sonuc[k] = ders
    return sonuc


def yukle(ad: str) -> dict:
    yol = ETIKETLEME / ad
    return json.loads(yol.read_text(encoding="utf-8")) if yol.exists() else {}


def main() -> None:
    kardes = Path(sys.argv[sys.argv.index("--kardes") + 1]) if "--kardes" in sys.argv else KARDES
    ders_of = anahtar_ders()
    A, B2, hakem = yukle("A.json"), yukle("B2.json"), yukle("hakem.json")
    for yol in sorted(ETIKETLEME.glob("tam-*-A.json")):  # 2019-2021 tam kitapçıklar: belge başına ayrı etiketleme dosyası
        A.update({k: v["konu"] for k, v in json.loads(yol.read_text(encoding="utf-8")).items()})
    for yol in sorted(ETIKETLEME.glob("tam-hakem-*.json")):
        if "girdi" not in yol.name:
            hakem.update(json.loads(yol.read_text(encoding="utf-8")))
    bugun = datetime.date.today().isoformat()
    for b in belgeler():
        metin = json.loads((METIN_DIZINI / f"{b['id']}.json").read_text(encoding="utf-8"))
        for test in b["testler"]:
            ozgun: dict[int, str] = {}
            yol = kardes / b["id"] / f"{test}.json"
            if yol.exists():
                ozgun = {s["no"]: s.get("konu", "") for s in json.loads(yol.read_text(encoding="utf-8"))["sorular"]}
            sorular = []
            for q in metin["sorular"][test]:
                k = f"{b['id']}-{test}-{q['no']}"
                a = A.get(k)
                bb = ozgun.get(q["no"]) or (B2.get(k) or {}).get("konu")
                if not a or not bb:
                    raise SystemExit(f"{k}: iki etiketleme de gerekli (A={a}, B={bb})")
                ek = None
                if a == bb:
                    konu, tur = a, "cift-onay"
                elif k in hakem:
                    konu, ek, tur = hakem[k]["konu"], hakem[k].get("ekKonu"), "hakem"
                else:
                    konu, tur = a, "belirsiz"
                for x in (konu, ek):
                    if x is not None and x not in ders_of:
                        raise SystemExit(f"{k}: konu anahtarı katalogda yok: {x}")
                sorular.append({
                    "no": q["no"], "sayfa": q["sayfa"], "konu": f"{ders_of[konu]}.{konu}", "altKonu": None,
                    "ekKonu": f"{ders_of[ek]}.{ek}" if ek and ek != konu else None,
                    "cevap": metin["anahtar"][test][str(q["no"])], "iptal": False, "etiket": tur,
                })
            dosya = ETIKET_DIZINI / f"{b['id']}-{test}.json"
            with dosya.open("w", encoding="utf-8") as f:
                f.write("{\n")
                f.write(f'  "belge": "{b["id"]}",\n  "test": "{test}",\n')
                f.write('  "etiketleme": ' + json.dumps({"tarih": bugun, "yontem": "iki bağımsız etiketleme (bu hat + nosakademi-web dizini ya da ayrı ikinci etiketleyici); uyuşmayanlar üçüncü karar (hakem); insan denetimi bekliyor"}, ensure_ascii=False) + ",\n")
                f.write('  "sorular": [\n' + ",\n".join("    " + json.dumps(s, ensure_ascii=False) for s in sorular) + "\n  ]\n}\n")
            print(f"{dosya.name}: {len(sorular)} soru, hakem {sum(1 for s in sorular if s['etiket'] == 'hakem')}, belirsiz {sum(1 for s in sorular if s['etiket'] == 'belirsiz')}")


if __name__ == "__main__":
    main()
