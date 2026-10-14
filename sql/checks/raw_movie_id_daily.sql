-- Run after each load. Expected: about 1M rows and exactly one source file per date.
SELECT
    snapshot_date,
    COUNT(*)                    AS row_count,
    COUNT(DISTINCT source_file) AS source_files,
    MIN(loaded_at)              AS first_loaded,
    MAX(loaded_at)              AS last_loaded
FROM raw.movie_ids_daily
GROUP BY snapshot_date
ORDER BY snapshot_date DESC;