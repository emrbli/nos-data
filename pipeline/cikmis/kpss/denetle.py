"""KPSS çıkmış soru dizininin denetimi; hata varsa çıkış kodu 1 ve paketleme durur (YKS `denetle.py` ile aynı kurallar).

Denetlenen:
- belgeler.json: kimlik tekil, kapsam tam (2019-2021) ya da yuzde10, https adresler, testin TESTLER'de olması.
- etiket dosyası: belgesi var; numaralar tekil, 1..basılı adet aralığında ve beklenen sayıda (tam: basılı adedin tamamı 1..N; yuzde10: test başına 6/6/8); konu kimliği katalogda (`konular.json`), dersi belgenin `dersler`'inde ve testin
  dersi; etiket türü; cevap A-E; yalnız izinli alanlar (soru metni olamaz).
- yerel metin varsa: yayımlanan numaralar, sayfa ve cevap kitapçıkla (sayfadaki "DOĞRU CEVAP") aynı.
- --baglanti: kitapçık PDF'leri (`%PDF` imzası) ve yayım sayfaları yanıt veriyor mu.
"""

from __future__ import annotations

import sys

from ..denetle import ETIKET_SORU_ALANLARI
from .ortak import (
    ETIKET_TURLERI,
    HARFLER,
    KONU_DESENI,
    GORSEL_DIZINI,
    METIN_DIZINI,
    RAPOR,
    TESTLER,
    belge_testleri,
    beklenen,
    ders_testleri,
    belgeler,
    etiket_dosyalari,
    konu_katalogu,
    oku,
)


def denetle() -> list[str]:
    hatalar: list[str] = []
    katalog = konu_katalogu()
    bler: dict[str, dict] = {}
    for b in belgeler():
        if b["id"] in bler:
            hatalar.append(f"{b['id']}: belge kimliği iki kez")
        bler[b["id"]] = b
        if b["kapsam"] not in ("tam", "yuzde10"):
            hatalar.append(f"{b['id']}: kapsam")
        if b.get("kitapciklar"):  # her testi ayrı PDF olan belge (alan, DHBT): kitapcikUrl yok, test başına adres
            if b.get("kitapcikUrl") is not None or set(b["kitapciklar"]) != set(b["testler"]):
                hatalar.append(f"{b['id']}: kitapciklar testlerle uyuşmuyor ya da kitapcikUrl dolu")
            for t, u in b["kitapciklar"].items():
                if not str(u).startswith("https://"):
                    hatalar.append(f"{b['id']}: kitapciklar[{t}] https değil")
        elif not str(b.get("kitapcikUrl", "")).startswith("https://"):
            hatalar.append(f"{b['id']}: kitapcikUrl https değil")
        if not str(b.get("yayimUrl", "")).startswith("https://"):
            hatalar.append(f"{b['id']}: yayimUrl https değil")
        if b.get("cozumUrl") is not None and not str(b["cozumUrl"]).startswith("https://"):
            hatalar.append(f"{b['id']}: cozumUrl https değil")
        testler = {kod for kod, _, _ in TESTLER.get(b["oturum"], [])}
        for t in b.get("testler", []):
            if t not in testler:
                hatalar.append(f"{b['id']}: {t} testi {b['oturum']} için tanımlı değil")
        for d in b["dersler"]:
            if d not in katalog:
                hatalar.append(f"{b['id']}: ders {d} katalogda yok")

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
        metin = None
        mp = METIN_DIZINI / f"{b['id']}.json"
        if mp.exists():
            metin = oku(mp)
        if adet == 0:  # ÖABT: adet PDF'ten (metin.json "adet")
            adet = (metin or {}).get("adet", {}).get(test)
        nolar = [s["no"] for s in e["sorular"]]
        bek = beklenen(b, test, adet) if adet else None
        if adet is None or len(set(nolar)) != len(nolar) or not all(1 <= n <= adet for n in nolar) or (bek is not None and len(nolar) != bek):
            hatalar.append(f"{yol.name}: numaralar tekil, 1..{adet} ve {bek if bek is not None else 'kitapçıktaki'} adet olmalı ({sorted(nolar)})")
        if metin:
            yayimlanan = sorted(int(n) for n in metin["anahtar"][test])
            if sorted(nolar) != yayimlanan:
                hatalar.append(f"{yol.name}: numaralar kitapçıktaki yayımlanan sorularla aynı değil ({yayimlanan})")
        for s in e["sorular"]:
            ad = f"{yol.name} #{s['no']}"
            fazla = set(s) - ETIKET_SORU_ALANLARI
            if fazla:
                hatalar.append(f"{ad}: tanınmayan alan {sorted(fazla)}")
            konu = s.get("konu", "")
            ders, _, anahtar = konu.partition(".")
            if not KONU_DESENI.match(konu) or ders not in b["dersler"]:
                hatalar.append(f"{ad}: konu {konu} belgenin dersleriyle uyumsuz")
            elif anahtar not in katalog.get(ders, {}).get("konular", {}):
                hatalar.append(f"{ad}: konu {konu} katalogda yok")
            elif test not in ders_testleri(katalog[ders]):
                hatalar.append(f"{ad}: konu {konu} {test} testine ait değil")
            ek = s.get("ekKonu")
            if ek is not None:
                ed, _, ea = ek.partition(".")
                if not KONU_DESENI.match(ek) or ek == konu or ea not in katalog.get(ed, {}).get("konular", {}) or ed not in b["dersler"] or test not in ders_testleri(katalog[ed]):
                    hatalar.append(f"{ad}: ekKonu {ek}")
            if s.get("altKonu") is not None:
                hatalar.append(f"{ad}: KPSS'de altKonu tanımlı değil")
            if s.get("etiket") not in ETIKET_TURLERI:
                hatalar.append(f"{ad}: etiket {s.get('etiket')}")
            if s.get("iptal"):
                if s.get("cevap") is not None:
                    hatalar.append(f"{ad}: iptal ama cevap var")
            elif s.get("cevap") not in HARFLER:
                hatalar.append(f"{ad}: cevap {s.get('cevap')}")
            if metin:
                kitapcik = metin["anahtar"][test].get(str(s["no"]), "yok")
                if kitapcik == "İPTAL":
                    if not s.get("iptal") or s.get("cevap") is not None:
                        hatalar.append(f"{ad}: kitapçık anahtarında İPTAL, etikette iptal={s.get('iptal')} cevap={s.get('cevap')}")
                elif s.get("iptal") or kitapcik != s.get("cevap"):
                    hatalar.append(f"{ad}: cevap {s.get('cevap')}, kitapçık anahtarı {kitapcik}")
                sf = next((q["sayfa"] for q in metin["sorular"].get(test, []) if q["no"] == s["no"]), None)
                if sf != s.get("sayfa"):
                    hatalar.append(f"{ad}: sayfa {s.get('sayfa')}, kitapçıkta {sf}")
    if RAPOR.exists():  # görsel tutarlılığı: her sorunun kırpması tamam, dosya var, boyutlar rapordakiyle aynı (iptal soru görselsiz olabilir)
        rapor = oku(RAPOR)
        for yol in etiket_dosyalari():
            e = oku(yol)
            for s in e["sorular"]:
                k = f"{e['belge']}-{e['test']}-{s['no']}"
                r = rapor.get(k)
                if r is None or r.get("durum") != "tamam":
                    if not s.get("iptal"):
                        hatalar.append(f"{k}: görsel yok ({(r or {}).get('durum', 'kirp.json kaydı yok')})")
                elif not (GORSEL_DIZINI / f"{k}.webp").exists():
                    hatalar.append(f"{k}: görsel dosyası yok")
    for b in bler.values():
        for t in b.get("testler", []):
            if (b["id"], t) not in gorulen:
                hatalar.append(f"{b['id']}: {t} etiket dosyası yok")
    return hatalar


def baglantilari_denetle() -> list[str]:
    """Her kitapçık adresi (belge ya da test başına) `%PDF` imzasıyla yanıt vermeli; yayım sayfası 200 dönmeli."""
    import httpx

    hatalar: list[str] = []
    for b in belgeler():
        adresler = {b["kitapcikUrl"]} if b.get("kitapcikUrl") else set(b.get("kitapciklar", {}).values())
        for u in sorted(adresler):
            try:
                with httpx.stream("GET", u, timeout=60, follow_redirects=True) as y:
                    bas = next(y.iter_bytes(), b"")[:5]
                    if y.status_code != 200 or bas != b"%PDF-":
                        hatalar.append(f"{b['id']}: {u} PDF değil ({y.status_code})")
            except httpx.HTTPError as ex:
                hatalar.append(f"{b['id']}: {u} ağ hatası {ex}")
        try:
            if httpx.get(b["yayimUrl"], timeout=60, follow_redirects=True).status_code != 200:
                hatalar.append(f"{b['id']}: yayimUrl 200 değil")
        except httpx.HTTPError as ex:
            hatalar.append(f"{b['id']}: yayimUrl ağ hatası {ex}")
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
