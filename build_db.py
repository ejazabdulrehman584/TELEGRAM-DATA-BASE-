#!/usr/bin/env python3
"""
build_db.py  --  Unify all OSINT data sources into ONE clean, queryable database.

Sources
-------
1) TGDATA_BY_DEADLOX_P4.parquet   (107.4M rows, duckdb export)
2) master_index.csv               (1.81M rows: TelegramID, Phone, Source)
3) Telegram_Chelabinsk_*.csv      (42.9K rows: TG_ID, FIRST_NAME, TG_USERNAME, PHONE)
4) Telegram_(2).txt               (90K lines: ID/N/U/TEL dump)

Output
------
data/tgdata.parquet   -> unified schema, de-duplicated, phone-normalised
data/tgdata.duckdb    -> indexed DuckDB database for instant lookups (if space allows)

Unified schema
--------------
tg_id       BIGINT     Telegram numeric id
username    VARCHAR    lower-case, no '@'
first_name  VARCHAR
last_name   VARCHAR
phone       VARCHAR    digits only, E.164 (country code included)
email       VARCHAR
linked_id   VARCHAR
linked_name VARCHAR
source      VARCHAR    origin tag
"""
import os, sys, time, duckdb

SRC_PARQUET = "TGDATA_BY_DEADLOX_P4.parquet"
SRC_MASTER  = "master_index.csv"
SRC_CHEL    = "Telegram_Chelabinsk_Parsed_2022-fsbtool.csv"
SRC_TXT     = "Telegram_(2).txt"
OUT_DIR     = "data"
OUT_PARQUET = f"{OUT_DIR}/tgdata.parquet"
OUT_DUCKDB  = f"{OUT_DIR}/tgdata.duckdb"


def log(*a):
    print("[build]", *a, flush=True)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    con = duckdb.connect()
    con.execute("PRAGMA threads=2")
    con.execute("PRAGMA memory_limit='2600MB'")
    con.execute("PRAGMA temp_directory='data/tmp'")
    con.execute("PRAGMA max_temp_directory_size='2GB'")

    t0 = time.time()

    # ---------------------------------------------------------------- big parquet
    log("loading big parquet ...")
    con.execute(f"""
    CREATE OR REPLACE TABLE big AS
    SELECT
        user_id::BIGINT                                   AS tg_id,
        lower(regexp_replace(coalesce(username,''),'^@','')) AS username,
        trim(coalesce(first_name,''))                     AS first_name,
        trim(coalesce(last_name,''))                      AS last_name,
        regexp_replace(coalesce(phone,''),'[^0-9]','','g') AS phone,
        lower(trim(coalesce(email,'')))                   AS email,
        coalesce(linked_id,'')                            AS linked_id,
        coalesce(linked_name,'')                          AS linked_name,
        'deadlox_p4'                                      AS source
    FROM read_parquet('{SRC_PARQUET}')
    WHERE (phone IS NOT NULL AND phone <> '')
       OR (username IS NOT NULL AND username <> '')
       OR (first_name IS NOT NULL AND first_name <> '')
       OR (linked_id IS NOT NULL AND linked_id <> '')
    """)
    n_big = con.execute("SELECT count(*) FROM big").fetchone()[0]
    log(f"  big useful rows: {n_big:,}  ({round(time.time()-t0,1)}s)")

    # ---------------------------------------------------------------- master_index
    log("loading master_index.csv ...")
    con.execute(f"""
    CREATE OR REPLACE TABLE master AS
    SELECT
        TRY_CAST("TelegramID" AS BIGINT)                  AS tg_id,
        ''                                                AS username,
        ''                                                AS first_name,
        ''                                                AS last_name,
        regexp_replace(coalesce(CAST("Phone" AS VARCHAR),''),'[^0-9]','','g') AS phone,
        ''                                                AS email,
        ''                                                AS linked_id,
        ''                                                AS linked_name,
        CAST(coalesce("Source",'master_index') AS VARCHAR) AS source
    FROM read_csv('{SRC_MASTER}', header=true, quote='"', all_varchar=true)
    WHERE TRY_CAST("TelegramID" AS BIGINT) IS NOT NULL
      AND coalesce(CAST("Phone" AS VARCHAR),'') <> ''
    """)
    n_master = con.execute("SELECT count(*) FROM master").fetchone()[0]
    log(f"  master rows: {n_master:,}")

    # ---------------------------------------------------------------- chelabinsk
    log("loading chelabinsk csv ...")
    con.execute(f"""
    CREATE OR REPLACE TABLE chel AS
    SELECT
        TRY_CAST(TG_ID AS BIGINT)                         AS tg_id,
        lower(regexp_replace(coalesce(TG_USERNAME,''),'^@','')) AS username,
        trim(coalesce(FIRST_NAME,''))                     AS first_name,
        ''                                                AS last_name,
        regexp_replace(coalesce(CAST(PHONE AS VARCHAR),''),'[^0-9]','','g') AS phone,
        ''                                                AS email,
        ''                                                AS linked_id,
        ''                                                AS linked_name,
        'chelabinsk_2022'                                 AS source
    FROM read_csv('{SRC_CHEL}', header=true, all_varchar=true)
    WHERE TRY_CAST(TG_ID AS BIGINT) IS NOT NULL
      AND (coalesce(PHONE,'') <> '' OR coalesce(TG_USERNAME,'') <> '')
    """)
    n_chel = con.execute("SELECT count(*) FROM chel").fetchone()[0]
    log(f"  chelabinsk rows: {n_chel:,}")

    # ---------------------------------------------------------------- txt dump
    log("loading Telegram_(2).txt ...")
    con.execute(f"""
    CREATE OR REPLACE TABLE txt AS
    SELECT
        TRY_CAST(regexp_extract(line, 'ID:\\s*\\[(\\d+)\\]', 1) AS BIGINT) AS tg_id,
        lower(regexp_extract(line, 'U\\[\\s*@?([^\\s\\]]*)\\s*\\]', 1)) AS username,
        trim(regexp_extract(line, 'N:\\[(.*?)\\]', 1))               AS first_name,
        ''                                                          AS last_name,
        regexp_replace(regexp_extract(line, 'TEL:\\[([^\\]]*)\\]', 1),'[^0-9]','','g') AS phone,
        ''                                                          AS email,
        ''                                                          AS linked_id,
        ''                                                          AS linked_name,
        'txt_dump'                                                  AS source
    FROM read_csv('{SRC_TXT}', header=false, sep='\\x01',
                  columns={{'line':'VARCHAR'}}, quote='', escape='')
    WHERE regexp_extract(line, 'ID:\\s*\\[(\\d+)\\]', 1) <> ''
    """)
    n_txt = con.execute("SELECT count(*) FROM txt").fetchone()[0]
    log(f"  txt rows: {n_txt:,}")

    # ---------------------------------------------------------------- merge
    log("merging ...")
    con.execute("SET preserve_insertion_order=false")
    con.execute("""
    CREATE OR REPLACE TABLE allrows AS
    SELECT * FROM big
    UNION ALL SELECT * FROM master
    UNION ALL SELECT * FROM chel
    UNION ALL SELECT * FROM txt
    """)

    # de-dup exact duplicate rows (memory-safe DISTINCT, no DISTINCT-agg)
    log("de-duplicating ...")
    con.execute("""
    CREATE OR REPLACE TABLE unified AS
    SELECT DISTINCT
        tg_id, username, first_name, last_name, phone, email, linked_id, linked_name, source
    FROM allrows
    WHERE tg_id IS NOT NULL
    """)
    n_unified = con.execute("SELECT count(*) FROM unified").fetchone()[0]
    log(f"  unified rows: {n_unified:,}")

    # ---------------------------------------------------------------- write parquet
    log(f"writing {OUT_PARQUET} ...")
    con.execute(f"""
    COPY (SELECT * FROM unified ORDER BY tg_id) TO '{OUT_PARQUET}'
    (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 122880)
    """)
    sz = os.path.getsize(OUT_PARQUET) / 1e6
    log(f"  parquet size: {sz:.1f} MB")

    # ---------------------------------------------------------------- optional duckdb
    free = os.statvfs(OUT_DIR).f_bavail * os.statvfs(OUT_DIR).f_frsize
    log(f"  free disk: {free/1e9:.2f} GB")
    if free > 1.6e9:
        log(f"building indexed {OUT_DUCKDB} ...")
        try:
            if os.path.exists(OUT_DUCKDB):
                os.remove(OUT_DUCKDB)
            d = duckdb.connect(OUT_DUCKDB)
            d.execute("PRAGMA threads=2")
            d.execute(f"CREATE TABLE tgdata AS SELECT * FROM read_parquet('{OUT_PARQUET}')")
            d.execute("CREATE INDEX idx_tgid ON tgdata(tg_id)")
            d.execute("CREATE INDEX idx_user ON tgdata(username)")
            d.execute("CREATE INDEX idx_phone ON tgdata(phone)")
            d.close()
            log(f"  duckdb size: {os.path.getsize(OUT_DUCKDB)/1e6:.1f} MB")
        except Exception as e:
            log("  duckdb build skipped:", e)
    else:
        log("  not enough disk for indexed duckdb -> API will query parquet directly")

    log(f"DONE in {round(time.time()-t0,1)}s")


if __name__ == "__main__":
    main()
