"""Kitapçıktan künye ve anahtar: pipeline/cikmis/yerel/metin/<belge>.json.

Çıktı (YEREL, commit ve release edilmez): her test için cevap anahtarı; etiketlenen
testlerin her sorusu için başladığı PDF sayfası ve etiketlemede okunacak metin
parçası. Yöntem (2019-2026 TYT'de doğrulandı):
- Soru numarası metin katmanında tek başına bir satırdır ("17."). Numaralar
  ardışık izlenir; 1'e dönüş yalnız önceki test tamamlandıysa yeni testtir, böylece
  soru içindeki numaralı listeler ve test yönergesi ("1. Bu testte ...") karışmaz.
- Sayfadaki soru metinleri seçenek satırlarına göre bölünür: her "E)" satırı bir
  sorunun sonudur. Parça sayısı numara sayısını tutmazsa sayfanın tamamı verilir
  (`bolundu: false`).
- Anahtar son sayfadadır: test başlığından sonra "N. Harf"; "N. İPTAL" anahtarında
  o numara eksik olan TEK teste bağlanır.
"""

from __future__ import annotations

import json
import re

from pypdf import PdfReader

from .ortak import METIN_DIZINI, PDF_DIZINI, TESTLER, belgeler

NO_SATIRI = re.compile(r"^\s*(\d{1,2})\.\s*$")


def sayfalar(yol) -> list[str]:
    r = PdfReader(str(yol))
    if r.is_encrypted:
        r.decrypt("")
    return [(p.extract_text() or "") for p in r.pages]


def numaralar(metin: str) -> list[int]:
    return [int(m.group(1)) for m in map(NO_SATIRI.match, metin.split("\n")) if m]


def anahtar(son_sayfa: str, testler) -> dict[str, dict[int, str | None]]:
    t = son_sayfa.replace("\xa0", " ")
    konumlar = [(kod, re.search(desen + r"\s+TEST", t)) for kod, _, desen in testler]
    if not all(m for _, m in konumlar):
        raise SystemExit("anahtar sayfasında test başlıkları eksik")
    sonuc: dict[str, dict[int, str | None]] = {}
    for i, (kod, m) in enumerate(konumlar):
        bitis = konumlar[i + 1][1].start() if i + 1 < len(konumlar) else len(t)
        sonuc[kod] = {int(n): h for n, h in re.findall(r"(\d{1,2})\.\s+([A-E])\b", t[m.end():bitis])}
    for n in (int(x) for x in re.findall(r"(\d{1,2})\.\s+İPTAL", t)):
        eksik = [kod for kod, adet, _ in testler if n <= adet and n not in sonuc[kod]]
        if len(eksik) != 1:
            raise SystemExit(f"İPTAL {n} tek teste bağlanamadı: {eksik}")
        sonuc[eksik[0]][n] = None
    return sonuc


def isle(belge: dict) -> dict:
    testler = TESTLER[belge["oturum"]]
    s = sayfalar(PDF_DIZINI / f"{belge['id']}.pdf")
    anahtarlar = anahtar(s[-1], testler)
    adetler = [adet for _, adet, _ in testler]
    t, son_no, kabul = 0, 0, {}
    for i in range(len(s) - 1):
        for n in numaralar(s[i]):
            if n == son_no + 1 and n <= adetler[t]:
                son_no = n
            elif n == 1 and t + 1 < len(adetler) and son_no == adetler[t]:
                t, son_no = t + 1, 1
            else:
                continue
            kabul.setdefault(i, []).append((t, n))
    sorular: dict[str, list[dict]] = {kod: [] for kod in belge["testler"]}
    for i, liste in sorted(kabul.items()):
        for ti, (kod, _, _) in enumerate(testler):
            if kod not in sorular:
                continue
            nos = [n for tt, n in liste if tt == ti]
            if not nos:
                continue
            satirlar = [x for x in s[i].split("\n") if not NO_SATIRI.match(x)]
            parcalar, akim = [], []
            for x in satirlar:
                akim.append(x)
                if "E)" in x:
                    parcalar.append("\n".join(akim))
                    akim = []
            bolundu = len(parcalar) == len(nos) == len(liste)
            for j, n in enumerate(nos):
                sorular[kod].append({"no": n, "sayfa": i + 1, "bolundu": bolundu, "metin": parcalar[j] if bolundu else s[i]})
    return {"belge": belge["id"], "anahtar": anahtarlar, "sorular": sorular}


def main() -> None:
    METIN_DIZINI.mkdir(parents=True, exist_ok=True)
    for b in belgeler():
        sonuc = isle(b)
        (METIN_DIZINI / f"{b['id']}.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
        for kod, liste in sonuc["sorular"].items():
            beklenen = next(adet for k, adet, _ in TESTLER[b["oturum"]] if k == kod)
            nolar = [q["no"] for q in liste]
            iptal = [n for n, h in sonuc["anahtar"][kod].items() if h is None]
            print(
                f"{b['id']} {kod}: soru {len(liste)}/{beklenen}, sıra {'tamam' if nolar == list(range(1, beklenen + 1)) else 'BOZUK'}, "
                f"bölünemeyen {sum(1 for q in liste if not q['bolundu'])}, anahtar {len(sonuc['anahtar'][kod])}, iptal {iptal}"
            )


if __name__ == "__main__":
    main()
