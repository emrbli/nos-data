# nosakademi-web çıkmış soru dizini: yer değiştirmiş 6 cevap

DURUM (2026-11-24): nosakademi-web'de `6c4ed0f` ("iki sütunlu sayfada yer değiştirmiş 7 cevap") bu 6 cevabı ve bir ÖABT sorusunu zaten düzeltmiş; düzeltilmiş dosyalar nos-data hattının sayfadan okuduğu cevaplarla yeniden karşılaştırıldı, fark yok. Bu dosya kanıt kaydıdır.

## Neden oldu
KPSS %10 kitapçıklarında sayfa iki sütunludur ve "DOĞRU CEVAP: X" satırı sorunun altındadır. İki yayımlı sorusu aynı sayfada, farklı sütunlarda olan sayfalarda metin katmanı (pypdf `extract_text`) sütunları sıra dışı verir; cevaplar numaralarla ters eşleşir. Doğrusu satırın sayfadaki konumundan: aynı sütunda, üstündeki en yakın "N." etiketi (nos-data `pipeline/cikmis/kpss/metin.py`).

## Kanıt (hepsi %10 kitapçık; sayfa = PDF sayfası)
| Belge | Test | No | PDF sayfası | Doğru cevap (sayfadaki kutu) | Eski dizin |
|---|---|---|---|---|---|
| 2022-onlisans | GY | 13 | 6 | A | C |
| 2022-onlisans | GY | 15 | 6 | C | A |
| 2022-onlisans | GK | 43 | 30 | C | E |
| 2022-onlisans | GK | 46 | 30 | E | C |
| 2025-lisans-gygk | GY | 14 | 6 | E | C |
| 2025-lisans-gygk | GY | 16 | 6 | C | E |

PDF'ler: 2022-onlisans `https://dokuman.osym.gov.tr/pdfdokuman/2022/KPSS/ONL/internetk09102022.pdf`; 2025 `https://dokuman.osym.gov.tr/pdfdokuman/2025/KPSS/GY-GK/gygk_07092025lsy.pdf`. Doğrulama: 2025 s.6'da sol sütundaki 14. sorunun (cümle sıralama) altında "DOĞRU CEVAP: E", sağ sütundaki 16. sorunun (ağırlık kaldırma parçası) altında "DOĞRU CEVAP: C" yazar (sayfa görseli incelendi).

## Tekrarı önlemek için
Cevap karşılaştırması: aynı sayfada iki cevap satırı olan her sayfa elle ya da konumla doğrulanmalı. nos-data'nın 2019-2026 KPSS cevapları (1016 soru) ÖSYM'nin satır konumundan ve 2019-2021 için sondaki anahtar tablosundan gelir; ikisi `pipeline/cikmis/kpss/denetle.py` ile kitapçıkla çapraz denetlenir.
