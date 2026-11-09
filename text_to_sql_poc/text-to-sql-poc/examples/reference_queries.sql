-- Noms et résultats correspondent exclusivement à synthetic_view.sql.
SELECT "category" AS x, SUM("measure") AS y
FROM "public"."v_metric_demo"
WHERE "event_date" >= CAST('2025-01-01' AS DATE)
  AND "event_date" < CAST('2026-01-01' AS DATE)
GROUP BY "category" ORDER BY x;
-- Attendu : A = 4 ; B = 5.

SELECT DATE_TRUNC('month', "event_date") AS x, SUM("measure") AS y
FROM "public"."v_metric_demo"
WHERE "event_date" >= CAST('2025-01-01' AS DATE)
  AND "event_date" < CAST('2026-01-01' AS DATE)
GROUP BY DATE_TRUNC('month', "event_date") ORDER BY x;
-- Attendu : janvier 2025 = 5.5 ; février 2025 = 3.5.
