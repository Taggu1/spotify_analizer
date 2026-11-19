-- Every music play from both sources, no overlap
CREATE OR REPLACE VIEW all_plays AS
SELECT ts AS played_at, track_id, track_name, artist_name, album_name,
       ms_played, 'export' AS source
FROM streaming_history
WHERE track_id IS NOT NULL
UNION ALL
SELECT played_at, track_id, track_name, artist_name, album_name,
       NULL::int AS ms_played, 'api' AS source
FROM plays
WHERE played_at > (SELECT COALESCE(MAX(ts), '-infinity'::timestamptz)
                   FROM streaming_history);

-- Only real listens (30+ seconds)
CREATE OR REPLACE VIEW listens AS
SELECT * FROM all_plays
WHERE source = 'api' OR ms_played >= 30000;

-- Same three views as before, now built on the full history
CREATE OR REPLACE VIEW daily_plays AS
SELECT (played_at AT TIME ZONE 'Africa/Cairo')::date AS day,
       COUNT(*) AS plays
FROM listens
GROUP BY 1
ORDER BY 1 DESC;

CREATE OR REPLACE VIEW top_artists AS
SELECT artist_name, COUNT(*) AS plays
FROM listens
GROUP BY artist_name
ORDER BY plays DESC;

CREATE OR REPLACE VIEW plays_by_hour AS
SELECT EXTRACT(HOUR FROM played_at AT TIME ZONE 'Africa/Cairo') AS hour,
       COUNT(*) AS plays
FROM listens
GROUP BY 1
ORDER BY 1;

CREATE OR REPLACE VIEW plays_by_hour AS
SELECT TO_CHAR(played_at AT TIME ZONE 'Africa/Cairo','HH12 AM') as hour, COUNT(*) as plays FROM listens
GROUP BY 1
ORDER BY 1 DESC;