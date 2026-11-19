"""İki bağımsız etiketleme (A, B) ve hakem kararlarından etiket dosyaları.

Girdi (yerel): yerel/etiketleme/<grup>-A.json, <grup>-B.json; hakem kararları
yerel/etiketleme/hakem2/karar-*.json. Uyuşan konu `cift-onay`, hakemin karar verdiği
`hakem`. Sayfa ve cevap `metin.py` çıktısından; ÖSYM'nin sonradan yaptığı değişiklikler
`duzeltmeler.json`'dan (iptal, cevap değişikliği).

Çıktı (commit edilir): etiket/<belge>-<test>.json (yalnız künye; soru metni yok).

  uv run python -m pipeline.cikmis.etiket_birlestir tyt-trk tyt-sos ...   # grup: <oturum>-<test>
"""

from __future__ import annotations

import datetime
import json
import sys

from .ortak import BURASI, ETIKET_DIZINI, HAM, METIN_DIZINI, belgeler

ETIKETLEME = HAM / "etiketleme"


def hakem_kararlari() -> dict[str, dict]:
    sonuc: dict[str, dict] = {}
    for dosya in sorted((ETIKETLEME / "hakem2").glob("karar-*.json")):
        sonuc.update(json.loads(dosya.read_text(encoding="utf-8")))
    return sonuc


def main() -> None:
    gruplar = sys.argv[1:]
    duzeltme = json.loads((BURASI / "duzeltmeler.json").read_text(encoding="utf-8"))["sorular"]
    hakem = hakem_kararlari()
    bugun = datetime.date.today().isoformat()
    for grup in gruplar:
        A = json.loads((ETIKETLEME / f"{grup}-A.json").read_text(encoding="utf-8"))
        B = json.loads((ETIKETLEME / f"{grup}-B.json").read_text(encoding="utf-8"))
        oturum = grup.split("-", 1)[0]
        test = grup.split("-", 2)[-1] if oturum == "ydt" else grup.split("-", 1)[1]
        for b in belgeler():
            if b["oturum"].lower() != oturum or test not in b["testler"]:
                continue
            metin = json.loads((METIN_DIZINI / f"{b['id']}.json").read_text(encoding="utf-8"))
            anahtar = metin["anahtar"][test]
            sorular, eksik = [], []
            for q in metin["sorular"][test]:
                k = f"{b['id']}-{test}-{q['no']}"
                a, bb = A.get(k), B.get(k)
                if not a or not bb:
                    eksik.append(k)
                    continue
                if a["konu"] == bb["konu"]:
                    konu, tur = a["konu"], "cift-onay"
                    ek = a.get("ekKonu") if a.get("ekKonu") and a.get("ekKonu") == bb.get("ekKonu") else None
                elif k in hakem:
                    konu, ek, tur = hakem[k]["konu"], hakem[k].get("ekKonu"), "hakem"
                else:
                    konu, ek, tur = a["konu"], None, "belirsiz"
                cevap = anahtar.get(str(q["no"]))
                kayit = {"no": q["no"], "sayfa": q["sayfa"], "konu": konu, "altKonu": None,
                         "ekKonu": ek if ek != konu else None, "cevap": cevap, "iptal": cevap is None, "etiket": tur}
                d = duzeltme.get(k)
                if d:
                    if d.get("iptal"):
                        kayit.update({"cevap": None, "iptal": True})
                    if d.get("cevap"):
                        kayit.update({"cevap": d["cevap"], "cevapDegisti": d.get("cevapDegisti")})
                sorular.append(kayit)
            if eksik:
                raise SystemExit(f"{b['id']} {test}: etiketi eksik {len(eksik)} soru ({eksik[:3]})")
            dosya = ETIKET_DIZINI / f"{b['id']}-{test}.json"
            with dosya.open("w", encoding="utf-8") as f:
                f.write("{\n")
                f.write(f'  "belge": "{b["id"]}",\n  "test": "{test}",\n')
                f.write('  "etiketleme": ' + json.dumps({"tarih": bugun, "yontem": "iki bağımsız etiketleme; uyuşmayanlar soru görselinden üçüncü karar (hakem); insan denetimi bekliyor"}, ensure_ascii=False) + ",\n")
                f.write('  "sorular": [\n' + ",\n".join("    " + json.dumps(s, ensure_ascii=False) for s in sorular) + "\n  ]\n}\n")
            print(f"{dosya.name}: {len(sorular)} soru, hakem {sum(1 for s in sorular if s['etiket'] == 'hakem')}, belirsiz {sum(1 for s in sorular if s['etiket'] == 'belirsiz')}")


if __name__ == "__main__":
    main()
