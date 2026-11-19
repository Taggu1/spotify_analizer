SELECT *,
    CASE
        WHEN LOWER(platform) LIKE '%playstation%' THEN 'PlayStation'
        WHEN LOWER(platform) LIKE '%android%' THEN 'Andorid'
        WHEN LOWER(platform) LIKE '%windows%' THEN 'Windows'
        WHEN LOWER(platform) LIKE '%osx%' THEN 'Mac os'
        WHEN LOWER(platform) LIKE '%linux%' THEN 'Linux'
        ELSE 'Other / Unknown'       
    END as normalized_platform
FROM streaming_history
LIMIT 10;