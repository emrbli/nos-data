"""BUILD SQLITE — Plan §5 Faz 4 + §4 DDL (birebir).

programs.json içeriğinden `nos.db` üretir. Bundle edilecek tek dosya olduğu için
DELETE journal (WAL yan dosyaları bundle'a giremez), page_size=4096, sonda
VACUUM + ANALYZE. FTS5 external-content indeksi 'rebuild' ile doldurulur.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Callable

from .merge import MergeResult
from .net_katsayi import compute_net_katsayi

# --- §4 şema (plan DDL'i BİREBİR) --------------------------------------------
SCHEMA_SQL = """
CREATE TABLE meta   (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE config (key TEXT PRIMARY KEY, value REAL NOT NULL);
CREATE TABLE programs (
  id            INTEGER PRIMARY KEY,
  uni           TEXT NOT NULL,
  uni_tur       TEXT NOT NULL CHECK (uni_tur IN ('DEVLET','VAKIF','KKTC','YURTDISI')),
  prog          TEXT NOT NULL,
  grup          TEXT NOT NULL,
  fakulte       TEXT,
  il            TEXT NOT NULL, ilce TEXT,
  puan_turu     TEXT NOT NULL CHECK (puan_turu IN ('SAY','EA','SÖZ','DİL','TYT')),
  birim_tur     TEXT NOT NULL CHECK (birim_tur IN ('LISANS','ONLISANS')),
  dil           TEXT,
  ogr_tur       TEXT NOT NULL,
  burs          TEXT,
  sure          INTEGER CHECK (sure BETWEEN 2 AND 6),
  kosul         TEXT NOT NULL DEFAULT '[]',
  kont2026      INTEGER,
  mtok          INTEGER NOT NULL DEFAULT 0,
  kktc_uyruklu  INTEGER NOT NULL DEFAULT 0,
  son_yil       INTEGER,
  son_siralama  INTEGER,
  son_puan      REAL,
  trend         TEXT CHECK (trend IN ('yukselen') OR trend IS NULL),
  uni_norm TEXT NOT NULL, prog_norm TEXT NOT NULL, grup_norm TEXT NOT NULL,
  -- schema v2 ek nullable alanlar (mevcut CHECK/NOT NULL'lar dokunulmadı):
  prof            INTEGER,   -- akademik kadro: profesör sayısı
  doc             INTEGER,   -- doçent
  dou             INTEGER,   -- dr. öğr. üyesi
  ar_gor          INTEGER,   -- araştırma görevlisi
  kpss1           REAL,      -- istihdam yüzdesi
  kontenjan_obs   INTEGER,   -- OBP kontenjan alt-kırılımı
  kontenjan_y34   INTEGER,   -- Y34 kontenjan alt-kırılımı
  osym_kilavuz_id INTEGER,   -- kararlı ÖSYM birleştirme anahtarı
  akreditasyon    TEXT,      -- program akreditasyon kodu
  akreditasyon_ack TEXT,     -- akreditasyon açıklaması
  uni_akreditasyon TEXT,     -- üniversite akreditasyonu
  universite_id   INTEGER,   -- YÖK Atlas üniversite logosu endpoint'i için (universite-logo?universiteId=)
  -- schema v3 ek nullable alanlar: ÖSYM 2026 kılavuzu (K2, artık OTORİTER)
  -- kaynaklı. Bkz. OUTBOX/pipeline/parse_kilavuz.py.
  ucret               REAL,     -- vakıf/KKTC yıllık öğrenim ücreti (TL); DEVLET NULL
  ucret_aciklama      TEXT,     -- ücret notu (kılavuz AÇIKLAMA sütunu)
  kont_sehit_gazi     INTEGER,  -- şehit/gazi eş-çocuğu kontenjanı (kılavuz Tablo 3/4)
  kont_okul_birincisi INTEGER,  -- okul birincisi kontenjanı (kılavuz Tablo 3/4)
  tyc                 TEXT,     -- Türkiye Yeterlilikler Çerçevesi düzeyi
  uni_web             TEXT      -- üniversite resmi web adresi (denormalize)
);
CREATE TABLE yearly_stats (
  program_id INTEGER NOT NULL REFERENCES programs(id),
  yil        INTEGER NOT NULL CHECK (yil IN (2022,2023,2024,2025)),
  puan_turu  TEXT NOT NULL,
  kontenjan INTEGER, yerlesen INTEGER,
  puan  REAL    CHECK (puan IS NULL OR (puan >= 100.0 AND puan <= 560.0)),
  sira  INTEGER CHECK (sira IS NULL OR sira > 0),
  PRIMARY KEY (program_id, yil)
) WITHOUT ROWID;
CREATE TABLE kosul_sozluk (kod TEXT PRIMARY KEY, aciklama TEXT NOT NULL);
CREATE TABLE baraj (grup_pattern TEXT NOT NULL, puan_turu TEXT NOT NULL,
                    baraj_sira INTEGER NOT NULL);
CREATE TABLE alias (takma TEXT PRIMARY KEY, hedef_norm TEXT NOT NULL);
-- schema v2: Net Sihirbazı (brief §10). Her satır bir programa o yıl en düşük
-- puanla YERLEŞEN öğrencinin ders bazlı net dökümüdür (kıyas referansı; puan
-- HESAPLAMA verisi DEĞİL). PK (kilavuz_kodu, yil, katsayi) — katsayi varyantları
-- ayrı satırlardır. FK ile programs'a bağlı (insert programs'tan SONRA).
CREATE TABLE net_profiles (
  kilavuz_kodu INTEGER NOT NULL REFERENCES programs(id),
  yil          INTEGER NOT NULL,
  katsayi      REAL,
  taban_puan   REAL,
  obp          REAL,
  tyt_trk_net  REAL, tyt_sos_net REAL, tyt_mat_net REAL, tyt_fen_net REAL,
  ayt_mat_net  REAL, ayt_fiz_net REAL, ayt_kim_net REAL, ayt_bio_net REAL,
  ayt_tde_net  REAL, ayt_trh1_net REAL, ayt_cog1_net REAL, ayt_trh2_net REAL,
  ayt_cog2_net REAL, ayt_fel_net REAL, ayt_din_net REAL,
  ydt_ydil_net REAL,
  PRIMARY KEY (kilavuz_kodu, yil, katsayi)
);
-- schema v4: Net Sihirbazı "Sıralamamı Bul" — net_profiles ground-truth'una
-- (yerleşen son öğrencinin gerçek netleri + gerçek taban_puan'ı) en küçük
-- kareler regresyonuyla oturtulmuş, yıl+puan türü başına afin net→puan
-- katsayıları (bkz. pipeline/net_katsayi.py). Salt türetilmiş/salt-okunur;
-- kaynak veri her zaman net_profiles'tır. `alan` gerçek ders alanlarının yanı
-- sıra 'intercept' ve 'obp' sözde-alanlarını da içerir (sabit terim + OBP
-- katsayısı) — böylece tahmini puan = Σ(katsayi × net) + obp_katsayi×OBP +
-- intercept tek tabloyla hesaplanır.
CREATE TABLE net_katsayi (
  yil       INTEGER NOT NULL,
  puan_turu TEXT    NOT NULL,
  alan      TEXT    NOT NULL,
  katsayi   REAL    NOT NULL,
  PRIMARY KEY (yil, puan_turu, alan)
);
-- Her (yıl,puan_türü) fit'inin tanı bilgisi + kullanıcı OBP girmediğinde
-- varsayılan (o yıl/türün ortalama OBP'si).
CREATE TABLE net_katsayi_meta (
  yil       INTEGER NOT NULL,
  puan_turu TEXT    NOT NULL,
  ort_obp   REAL    NOT NULL,
  n         INTEGER NOT NULL,
  r2        REAL    NOT NULL,
  rmse      REAL    NOT NULL,
  PRIMARY KEY (yil, puan_turu)
);
CREATE VIRTUAL TABLE program_fts USING fts5(
  uni_norm, prog_norm, grup_norm,
  content='programs', content_rowid='id',
  tokenize='unicode61', prefix='2 3'
);
CREATE INDEX idx_wizard ON programs(puan_turu, son_siralama)
  WHERE kont2026 IS NOT NULL;
CREATE INDEX idx_il    ON programs(il);
CREATE INDEX idx_grup  ON programs(grup);
CREATE INDEX idx_yearly ON yearly_stats(program_id);
CREATE INDEX idx_net_program ON net_profiles(kilavuz_kodu, yil);
CREATE INDEX idx_net_katsayi_meta ON net_katsayi_meta(puan_turu, yil);
"""

# net_profiles insert kolon sırası (SCHEMA_SQL ile birebir; merge_netler dict
# anahtarlarıyla aynı snake_case adlar).
_NET_COLUMNS: list[str] = [
    "kilavuz_kodu", "yil", "katsayi", "taban_puan", "obp",
    "tyt_trk_net", "tyt_sos_net", "tyt_mat_net", "tyt_fen_net",
    "ayt_mat_net", "ayt_fiz_net", "ayt_kim_net", "ayt_bio_net",
    "ayt_tde_net", "ayt_trh1_net", "ayt_cog1_net", "ayt_trh2_net",
    "ayt_cog2_net", "ayt_fel_net", "ayt_din_net", "ydt_ydil_net",
]

# config (K-10) — anahtarlar TS engine.ts / fixture ile birebir aynı.
CONFIG: list[tuple[str, float]] = [
    ("guven_carpan", 0.85),
    ("denge_ust", 1.10),
    ("hedef_ust", 1.11),
    ("trend_min_yil", 3),
    ("trend_max_sicrama", 0.40),
    ("trend_kont_tolerans", 0.25),
]

# alias (K-13) — [folded takma -> folded hedef substring]. Sorgu genişletme.
#
# KURAL: expandAliases (queries.ts) takma'yı hedefle DEĞİŞTİRİR ve hedefin her
# tokenı FTS'te ZORUNLU (AND) olur. Bu yüzden takma:
#   1) Corpus'ta kelime olarak GEÇMEYEN gerçek bir kısaltma olmalı (odtu, eee,
#      pdr...) — yoksa o kelimeyi içeren başka aramaları öldürür. Örn. eski
#      ("dis", "dis hekimligi") kaydı "Diş Protez", "Ağız ve Diş Sağlığı" ve
#      fold çakışmasıyla "Dış Ticaret" aramalarını 0 sonuca düşürüyordu;
#      ("kimya", "kimya muhendisligi") "Kimya Öğretmenliği"ni gizliyordu.
#   2) Prefix'in zaten kapsadığı genişletmeler gereksizdir ("dis*" diş
#      hekimliğini, "elektronik*" elektrik-elektronik'i zaten bulur).
#   3) Tek token olmalı — boşluklu takma hiç ateşlenmez (token-token bakılır).
# Sıralama önceliği alias işi değildir; queries.ts'teki yapısal katmanlar çözer.
ALIAS: list[tuple[str, str]] = [
    ("odtu", "orta dogu teknik"),
    ("itu", "istanbul teknik"),
    ("boun", "bogazici"),
    ("ytu", "yildiz teknik"),
    ("ktu", "karadeniz teknik"),
    ("deu", "dokuz eylul"),
    ("gtu", "gebze teknik"),
    ("iyte", "izmir yuksek teknoloji"),
    ("bilg", "bilgisayar"),
    ("muh", "muhendisligi"),
    ("eee", "elektrik elektronik"),
    ("pdr", "rehberlik ve psikolojik danismanlik"),
    ("ogretmenlik", "ogretmenligi"),
    ("radyoloji", "tibbi goruntuleme"),
]


def _clamp_sure(sure: Any) -> int | None:
    if sure is None:
        return None
    return sure if 2 <= sure <= 6 else None


def _clamp_puan(puan: Any) -> float | None:
    if puan is None:
        return None
    return puan if 100.0 <= puan <= 560.0 else None


def build(
    result: MergeResult,
    db_path: str | Path,
    *,
    exported_at: str,
    json_sha: str,
    schema_version: int = 1,
    net_profiles: list[dict[str, Any]] | None = None,
    logf: Callable[[str], None] | None = None,
) -> str:
    """nos.db üretir. Döndürür: DB dosyasının sha256'sı (bütünlük için).

    `net_profiles`: merge_netler çıktısı (net_profiles satırları). None/boş ise
    tablo yalnız oluşturulur (--skip-netler). Insert programs'tan SONRA yapılır
    (FK). merge_netler zaten known kilavuz_kodları'na filtrelediği için FK ihlali
    beklenmez; yine de savunmacı davranılır (ihlal loglanır, patlamaz).

    `net_katsayi`/`net_katsayi_meta` (schema v4): net_profiles doluysa, aynı
    listeden + result.records'tan (kilavuz_kodu->puan_türü) EK bir ağ/DB sorgusu
    olmadan pipeline.net_katsayi.compute_net_katsayi() ile türetilir (Net
    Sihirbazı "Sıralamamı Bul" — bkz. plan)."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    dropped_sure = dropped_puan = 0
    net_inserted = net_fk_dropped = 0
    katsayi_stats: dict[str, Any] = {}
    try:
        conn.execute("PRAGMA page_size=4096;")   # tablolar oluşmadan ÖNCE
        conn.execute("PRAGMA journal_mode=DELETE;")  # WAL YASAK (bundle tek dosya)
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.executescript(SCHEMA_SQL)

        conn.executemany("INSERT INTO config(key,value) VALUES (?,?)", CONFIG)
        conn.executemany("INSERT INTO alias(takma,hedef_norm) VALUES (?,?)", ALIAS)

        prog_rows = []
        year_rows = []
        for r in result.records:
            sure = _clamp_sure(r["sure"])
            if r["sure"] is not None and sure is None:
                dropped_sure += 1
            prog_rows.append((
                r["id"], r["uni"], r["uniTur"], r["prog"], r["grup"], r["fakulte"],
                r["il"], r["ilce"], r["puanTuru"], r["birimTur"], r["dil"], r["ogrTur"],
                r["burs"], sure, json.dumps(r["kosul"], ensure_ascii=False),
                r["kont2026"], r["mtok"], r["kktcUyruklu"], r["sonYil"], r["sonSiralama"],
                r["sonPuan"], r["trend"], r["uniNorm"], r["progNorm"], r["grupNorm"],
                r.get("prof"), r.get("doc"), r.get("dou"), r.get("arGor"), r.get("kpss1"),
                r.get("kontenjanObs"), r.get("kontenjanY34"), r.get("osymKilavuzId"),
                r.get("akreditasyon"), r.get("akreditasyonAck"), r.get("uniAkreditasyon"),
                r.get("universiteId"),
                r.get("ucret"), r.get("ucretAciklama"), r.get("kontSehitGazi"),
                r.get("kontOkulBirincisi"), r.get("tyc"), r.get("uniWeb"),
            ))
            for y in r["yillar"]:
                puan = _clamp_puan(y["p"])
                if y["p"] is not None and puan is None:
                    dropped_puan += 1
                year_rows.append((r["id"], y["y"], y["pt"], y["k"], y["z"], puan, y["s"]))

        conn.executemany(
            "INSERT INTO programs "
            "(id,uni,uni_tur,prog,grup,fakulte,il,ilce,puan_turu,birim_tur,dil,ogr_tur,"
            "burs,sure,kosul,kont2026,mtok,kktc_uyruklu,son_yil,son_siralama,son_puan,"
            "trend,uni_norm,prog_norm,grup_norm,"
            "prof,doc,dou,ar_gor,kpss1,kontenjan_obs,kontenjan_y34,osym_kilavuz_id,"
            "akreditasyon,akreditasyon_ack,uni_akreditasyon,universite_id,"
            "ucret,ucret_aciklama,kont_sehit_gazi,kont_okul_birincisi,tyc,uni_web) "
            "VALUES (" + ",".join(["?"] * 43) + ")",
            prog_rows,
        )
        conn.executemany(
            "INSERT INTO yearly_stats "
            "(program_id,yil,puan_turu,kontenjan,yerlesen,puan,sira) VALUES (?,?,?,?,?,?,?)",
            year_rows,
        )
        conn.executemany(
            "INSERT INTO kosul_sozluk(kod,aciklama) VALUES (?,?)",
            sorted(result.kosul_sozluk.items()),
        )
        conn.executemany(
            "INSERT INTO baraj(grup_pattern,puan_turu,baraj_sira) VALUES (?,?,?)",
            [(b["grupPattern"], b["puanTuru"], b["barajSira"]) for b in result.baraj],
        )

        # net_profiles (schema v2) — programs INSERT'inden SONRA (FK).
        if net_profiles:
            prog_ids = {r["id"] for r in result.records}
            net_tuples = []
            for row in net_profiles:
                if row["kilavuz_kodu"] not in prog_ids:
                    net_fk_dropped += 1  # merge_netler filtreledi; savunmacı ikinci kapı
                    continue
                net_tuples.append(tuple(row.get(col) for col in _NET_COLUMNS))
            conn.executemany(
                "INSERT INTO net_profiles (" + ",".join(_NET_COLUMNS) + ") "
                "VALUES (" + ",".join(["?"] * len(_NET_COLUMNS)) + ")",
                net_tuples,
            )
            net_inserted = len(net_tuples)

            # net_katsayi (schema v4) — net_profiles ground-truth'una oturtulan
            # afin net→puan katsayıları. Ayrı bir ağ/DB sorgusu gerekmez: aynı
            # `net_profiles` listesi + programs kilavuz_kodu->puan_türü haritası
            # yeterlidir (bkz. pipeline/net_katsayi.py).
            puan_turu_by_kilavuz = {r["id"]: r["puanTuru"] for r in result.records}
            katsayi_rows, katsayi_meta_rows, katsayi_stats = compute_net_katsayi(
                net_profiles, puan_turu_by_kilavuz, logf=logf,
            )
            conn.executemany(
                "INSERT INTO net_katsayi(yil,puan_turu,alan,katsayi) VALUES (?,?,?,?)",
                [(r["yil"], r["puan_turu"], r["alan"], r["katsayi"]) for r in katsayi_rows],
            )
            conn.executemany(
                "INSERT INTO net_katsayi_meta(yil,puan_turu,ort_obp,n,r2,rmse) VALUES (?,?,?,?,?,?)",
                [
                    (r["yil"], r["puan_turu"], r["ort_obp"], r["n"], r["r2"], r["rmse"])
                    for r in katsayi_meta_rows
                ],
            )
        conn.executemany(
            "INSERT INTO meta(key,value) VALUES (?,?)",
            [
                ("exportedAt", exported_at),
                ("sha256_json", json_sha),
                ("programCount", str(len(result.records))),
                ("schemaVersion", str(schema_version)),
                ("dataYear", "2025"),
            ],
        )

        # FTS5 external-content indeksini içerik tablosundan kur.
        conn.execute("INSERT INTO program_fts(program_fts) VALUES('rebuild');")
        conn.commit()

        conn.execute("ANALYZE;")
        conn.commit()
        conn.execute("VACUUM;")
        conn.commit()
        # Savunmacı: hiçbir WAL kalıntısı bundle'a girmesin (WAL YASAK — tek dosya).
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        journal = conn.execute("PRAGMA journal_mode=DELETE;").fetchone()[0]
        if str(journal).lower() != "delete":
            raise RuntimeError(f"journal_mode DELETE olmalı, {journal!r} bulundu")
        conn.commit()
    finally:
        conn.close()

    # -wal/-shm yan dosyaları OLMAMALI (bundle tek dosya). Sha'dan ÖNCE assert et.
    assert_no_sidecars(db_path)

    if dropped_sure or dropped_puan:
        _log(logf, f"  [uyarı] aralık dışı nulllandı: sure={dropped_sure}, puan={dropped_puan}")
    if net_fk_dropped:
        _log(logf, f"  [uyarı] net_profiles FK eşleşmeyen {net_fk_dropped} satır atlandı (savunmacı)")
    if katsayi_stats:
        min_r2 = katsayi_stats.get("minR2")
        r2_part = f", min R²={min_r2:.4f}" if min_r2 is not None else ""
        _log(logf, f"  net_katsayi: {katsayi_stats.get('groupCount')} grup (yıl×puan_türü){r2_part}")
    _log(logf, f"  nos.db yazıldı: {len(result.records)} program, {len(year_rows)} yearly_stats, "
               f"{len(result.kosul_sozluk)} koşul, {len(result.baraj)} baraj, "
               f"{net_inserted} net_profiles")

    # sha256_db TÜM DB açma işlemlerinden SONRA, son adım olarak (bkz. docs §3.4).
    return file_sha256(db_path)


def assert_no_sidecars(db_path: str | Path) -> None:
    """nos.db yanında -wal/-shm/-journal yan dosyası olmadığını doğrular.
    Varsa DB WAL'de açık kalmış demektir -> dosya hash'i kararsız olur."""
    db_path = Path(db_path)
    leftovers = [db_path.with_name(db_path.name + suf) for suf in ("-wal", "-shm", "-journal")]
    present = [p.name for p in leftovers if p.exists()]
    if present:
        raise RuntimeError(
            f"{db_path.name} yanında yan dosya bulundu {present}; DB WAL/journal'de "
            f"açık kalmış. Dosya hash'i kararsız — promote engellendi."
        )


def file_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _log(logf: Callable[[str], None] | None, msg: str) -> None:
    if logf:
        logf(msg)
