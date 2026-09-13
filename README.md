# nos-data

Nos Tercih (iOS/Android uygulaması) ve [nostercih.com](https://nostercih.com) için ortak
veri kaynağı. Türkiye'deki tüm lisans ve önlisans programlarının 2023-2025 yerleştirme
sonuçlarını ve 2026 kontenjan/koşullarını çeker, doğrular ve tek bir SQLite dosyası
(`nos.db`) olarak **GitHub Releases** üzerinden yayınlar. Backend yok, veritabanı sunucusu yok.

```
YÖK Atlas API (K1) + ÖSYM 2026 Kılavuzu PDF (K2)
        │  uv run python run.py
        ▼
dist/ (nos.db, meta.json, fold_fixture.json, programs.json, validation_report.md)
        │  scripts/release.sh
        ▼
GitHub Release  v{schemaVersion}-{YYYY-MM-DD}
        ├── nos-academy   build: pnpm sync-db (pin'li tag)   runtime: releases/latest
        └── nostercih     build: pnpm fetch-db (pin'li tag), Vercel prebuild
```

## Kurulum

Python 3.11 ve [uv](https://docs.astral.sh/uv/) gerekir.

```bash
uv sync
```

## Pipeline

```bash
uv run python run.py                 # tam koşu: fetch -> merge -> validate -> build -> test -> dist/
uv run python run.py --skip-fetch    # raw/'tan yeniden üret (ağ yok, ~1 dk; idempotans testi)
uv run python run.py --until merge   # yalnız fetch + merge
uv run python run.py --only DİL      # tek puan türü (hızlı bounded test)
uv run python run.py --skip-netler   # net çekimini atla (net_profiles boş)
```

Pipeline atomiktir: her şey `dist.tmp/` altında üretilir, VALIDATE ve TEST kapıları geçmeden
`dist/` değişmez. Kaynaklar, alan anlamları ve bilinen veri tuhaflıkları için
`docs/VERI_NOTLARI.md`. ÖSYM kılavuzu `docs/kontkilavuz_yktd21072026.pdf` otoriter kaynaktır
(kontenjan, koşul, süre, puan türü); `--kilavuz-pdf` ile farklı dosya verilebilir.

`raw/`, `logs/`, `dist/`, `dist.tmp/`, `.venv/` git dışıdır. `dist/` çıktısı release olarak yayınlanır,
git geçmişine binary girmez.

## Yayın

```bash
scripts/release.sh --dry-run   # tag ve hash'i göster
scripts/release.sh             # gh release create, --latest
```

Tag biçimi `v{schemaVersion}-{exportedAt tarihi}`, örn. `v8-2026-07-26`. Release'e beş dosya
eklenir: `nos.db`, `meta.json`, `fold_fixture.json`, `validation_report.md`, `programs.json`.
`validation_report.md` PASS içermiyorsa veya `nos.db` hash'i `meta.sha256_db` ile uyuşmuyorsa
script durur.

Script sonunda tüketiciler için `nos-data.json` pin içeriğini basar:

```json
{ "repo": "emrbli/nos-data", "tag": "v8-2026-07-26", "schemaVersion": 8, "sha256_db": "67a8…" }
```

## Tüketiciler

| Repo | Build zamanı | Çalışma zamanı |
|---|---|---|
| nos-academy (Expo) | `nos-data.json` pin'indeki tag'den `assets/db/nos.db` indirilir, sha256 doğrulanır, uygulamaya gömülür. EAS'ta `eas-build-pre-install` hook'u. | Uygulama offline çalışır. `src/lib/update.ts` `releases/latest/download/meta.json`'a bakar; `sha256_json` farklı ve `schemaVersion` eşitse `nos.db`'yi indirip bir sonraki açılışta değiştirir. |
| nostercih (Next.js) | `prebuild`'de aynı pin'den `data/nos.db` indirilir; SSG sayfalar ve `public/data/*.json` shard'ları build sunucusunda üretilir. | DB tarayıcıya gitmez. |

Yeni veri yayınlandığında tüketici repolarda `nos-data.json` güncellenir ve yeniden build alınır.

## `meta.json` sözleşmesi

| Alan | Anlam |
|---|---|
| `schemaVersion` | DDL sürümü. Tüketiciler kendi beklediği sürümle karşılaştırır. |
| `sha256_json` | Veri içeriği hash'i. `exportedAt`'ten bağımsız; veri değişmedikçe sabit. Uygulama güncelleme **tespitini** bununla yapar. |
| `sha256_db` | `nos.db` dosya hash'i. Her build'de değişir. İndirme **doğrulaması** bununla yapılır. |
| `exportedAt`, `dataYear`, `programCount` | Bilgi amaçlı. |

## Şema versiyonlama

- Kolon veya tablo **eklemek** güvenlidir, `schemaVersion` artmaz. Eski uygulama sürümleri yeni
  kolonu görmez, çalışmaya devam eder.
- Kolon **silmek, yeniden adlandırmak veya tip değiştirmek** `SCHEMA_VERSION`'ı (`run.py`) artırır.
  Bu durumda uygulamadaki `src/lib/schema.ts` `CURRENT_SCHEMA_VERSION` ve nostercih'teki tipler de
  güncellenip **önce uygulama store'a çıkar, sonra release yayınlanır**. Aksi halde eski uygulama
  `schema-mismatch` alır ve güncellemeyi reddeder (veri bozulmaz, sadece eski veriyle kalır).

## Dizin

```
run.py            orkestratör, SCHEMA_VERSION burada
pipeline/         fetch, fetch_netler, parse_kilavuz, merge, validate, build_sqlite, net_katsayi, tests, turkish
scripts/          release.sh
docs/             VERI_NOTLARI.md, ÖSYM kılavuz PDF, briefs/
```
