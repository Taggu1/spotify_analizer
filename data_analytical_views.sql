SELECT COUNT(*), DATE_PART('day', played_at) FROM plays
GROUP BY DATE_PART('day', played_at)
ORDER BY COUNT(*) DESC
LIMIT 5;

SELECT
    (played_at AT TIME ZONE 'Africa/Cairo')::date AS day,
    COUNT(*) AS plays
FROM plays
GROUP BY 1
ORDER BY 2 DESC;