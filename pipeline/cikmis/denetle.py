"""Çıkmış soru dizininin denetimi; hata varsa çıkış kodu 1 ve paketleme durur.

Denetlenen:
- belgeler.json: kimlik tekil, kapsam, https adresler, etiketlenen testin TESTLER'de olması.
- etiket dosyası: belgesi var, numaralar 1..N kesintisiz ve tekil, konu kimliği biçimi ve
  dersi belgenin `dersler`'inde, alt konu yalnız izinli konuda ve listede, etiket türü,
  cevap A-E ya da iptal, yalnız izinli alanlar (soru metni olamaz).
- yerel metin varsa: sayfa ve cevap kitapçıktaki anahtar ve sayfayla aynı.
- --baglanti: kitapçık PDF'leri (`%PDF` imzası) ve yayım sayfaları yanıt veriyor mu.
Konu kimliğinin katalogda olduğunu nos-academy `pnpm test` denetler (katalog orada).
"""

from __future__ import annotations

import json
import sys
import time

import httpx

from .ortak import (
    BURASI,
    ALT_KONULAR,
    ETIKET_TURLERI,
    HARFLER,
    KONU_DESENI,
    METIN_DIZINI,
    TESTLER,
    belgeler,
    etiket_dosyalari,
    oku,
)

ETIKET_SORU_ALANLARI = {"no", "sayfa", "konu", "altKonu", "ekKonu", "cevap", "iptal", "cevapDegisti", "etiket"}


def denetle() -> list[str]:
    hatalar: list[str] = []
    duzeltme = json.loads((BURASI / "duzeltmeler.json").read_text(encoding="utf-8"))["sorular"]
    bler = {}
    for b in belgeler():
        if b["id"] in bler:
            hatalar.append(f"{b['id']}: belge kimliği iki kez")
        bler[b["id"]] = b
        if b["kapsam"] not in ("tam", "yuzde20"):
            hatalar.append(f"{b['id']}: kapsam")
        for alan in ("kitapcikUrl", "yayimUrl"):
            if not str(b.get(alan, "")).startswith("https://"):
                hatalar.append(f"{b['id']}: {alan} https değil")
        if b.get("cozumUrl") is not None and not str(b["cozumUrl"]).startswith("https://"):
            hatalar.append(f"{b['id']}: cozumUrl https değil")
        testler = {kod for kod, _, _ in TESTLER.get(b["oturum"], [])}
        for t in b.get("testler", []):
            if t not in testler:
                hatalar.append(f"{b['id']}: {t} testi {b['oturum']} için tanımlı değil")

    gorulen = set()
    for yol in etiket_dosyalari():
        e = oku(yol)
        b = bler.get(e["belge"])
        if not b:
            hatalar.append(f"{yol.name}: belge {e['belge']} yok")
            continue
        test = e["test"]
        gorulen.add((b["id"], test))
        if test not in b.get("testler", []):
            hatalar.append(f"{yol.name}: {test} belgede etiketlenen testlerde yok")
        adet = next((a for k, a, _ in TESTLER[b["oturum"]] if k == test), None)
        nolar = [s["no"] for s in e["sorular"]]
        if adet is None or sorted(nolar) != list(range(1, adet + 1)):
            hatalar.append(f"{yol.name}: numaralar 1..{adet} değil")
        metin = None
        mp = METIN_DIZINI / f"{b['id']}.json"
        if mp.exists():
            metin = oku(mp)
        for s in e["sorular"]:
            ad = f"{yol.name} #{s['no']}"
            fazla = set(s) - ETIKET_SORU_ALANLARI
            if fazla:
                hatalar.append(f"{ad}: tanınmayan alan {sorted(fazla)}")
            konu = s.get("konu", "")
            if not KONU_DESENI.match(konu) or konu.split(".")[0] not in b["dersler"]:
                hatalar.append(f"{ad}: konu {konu} belgenin dersleriyle uyumsuz")
            if s.get("ekKonu") is not None and (not KONU_DESENI.match(s["ekKonu"]) or s["ekKonu"] == konu):
                hatalar.append(f"{ad}: ekKonu {s['ekKonu']}")
            alt = s.get("altKonu")
            if alt is not None and alt not in ALT_KONULAR.get(konu, set()):
                hatalar.append(f"{ad}: altKonu {alt} bu konuda yok")
            if s.get("etiket") not in ETIKET_TURLERI:
                hatalar.append(f"{ad}: etiket {s.get('etiket')}")
            if s.get("iptal"):
                if s.get("cevap") is not None:
                    hatalar.append(f"{ad}: iptal ama cevap var")
            elif s.get("cevap") not in HARFLER:
                hatalar.append(f"{ad}: cevap {s.get('cevap')}")
            if metin:
                kitapcik = metin["anahtar"][test].get(str(s["no"]), "yok")
                # ÖSYM'nin sonradan yaptığı değişiklik (duzeltmeler.json) kitapçık anahtarına üstün gelir.
                if f"{b['id']}-{test}-{s['no']}" in duzeltme:
                    pass
                elif kitapcik != s.get("cevap"):
                    hatalar.append(f"{ad}: cevap {s.get('cevap')}, kitapçık anahtarı {kitapcik}")
                sf = next((q["sayfa"] for q in metin["sorular"].get(test, []) if q["no"] == s["no"]), None)
                if sf != s.get("sayfa"):
                    hatalar.append(f"{ad}: sayfa {s.get('sayfa')}, kitapçıkta {sf}")
    for b in bler.values():
        for t in b.get("testler", []):
            if (b["id"], t) not in gorulen:
                hatalar.append(f"{b['id']}: {t} etiket dosyası yok")
    return hatalar


def baglantilari_denetle() -> list[str]:
    hatalar = []
    for b in belgeler():
        for alan in ("kitapcikUrl", "yayimUrl", "cozumUrl"):
            url = b.get(alan)
            if not url:
                continue
            try:
                with httpx.stream("GET", url, timeout=120, follow_redirects=True) as y:
                    bas = next(y.iter_bytes(), b"")[:5]
                    if y.status_code != 200 or (alan == "kitapcikUrl" and bas != b"%PDF-"):
                        hatalar.append(f"{b['id']} {alan}: {y.status_code} {bas!r}")
            except httpx.HTTPError as e:
                hatalar.append(f"{b['id']} {alan}: {e}")
            time.sleep(1.5)
    return hatalar


def main() -> None:
    hatalar = denetle()
    if "--baglanti" in sys.argv:
        hatalar += baglantilari_denetle()
    for h in hatalar:
        print("HATA", h)
    sayi = sum(len(oku(y)["sorular"]) for y in etiket_dosyalari())
    print(f"denetle: {len(etiket_dosyalari())} etiket dosyası, {sayi} soru, {len(hatalar)} hata")
    if hatalar:
        sys.exit(1)


if __name__ == "__main__":
    main()
