"""NOS veri pipeline paketi.

Fazlar:
  fetch  -> K1 (YÖK Atlas JSON API, raw/k1/{RESULT_YEAR}/) + netler
            K2 (ÖSYM kılavuzu PDF, otoriter; XLS yalnız çapraz kontrol)
  merge  -> dedup (kilavuz_kodu), tarihsel arşiv doldurma (archive/), kılavuz
            uygulaması, türetmeler, Türkçe fold, programs.json
  validate / build_sqlite / tests -> yayın kapıları, nos.db, DB testleri
Yıl konfigürasyonu TEK yerde: pipeline/years.py (literal yıl yazma).
"""
