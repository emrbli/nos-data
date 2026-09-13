# nos-data

Nos Tercih uygulaması ve nostercih.com için ortak veri pipeline'ı. Çıktı `dist/nos.db`,
dağıtım GitHub Releases. Ayrıntı ve tüketici akışı için `README.md`, veri kararları için
`docs/VERI_NOTLARI.md`.

## Kurallar

- Pipeline atomiktir: `dist.tmp/` altında üret, VALIDATE ve TEST geçmeden `dist/`'e dokunma.
  Bu düzeni bozan değişiklik yapma.
- ÖSYM kılavuzu (K2, `docs/*.pdf`) kontenjan/koşul/süre/puan türü için otoriter; YÖK Atlas (K1)
  yerleştirme istatistikleri için. Çakışmada K2 kazanır (`pipeline/merge.py`).
- DDL değişikliği yapıyorsan `run.py` içindeki `SCHEMA_VERSION` yorumunu oku. Kolon ekleme
  sürüm artırmaz; silme/yeniden adlandırma artırır ve iki tüketici repoda koordineli değişiklik ister.
- `dist/`, `raw/`, `logs/` commit edilmez. Yayın yalnız `scripts/release.sh` ile.
- Bağımlılık eklemeden önce `pyproject.toml`'a bak; `uv add` kullan, `uv.lock` commit edilir.
- Türkçe büyük/küçük harf ve aksan katlama `pipeline/turkish.py` `fold()` ile yapılır;
  `fold_fixture.json` uygulamadaki TS eşdeğerinin sözleşmesidir, ikisi birlikte değişir.
