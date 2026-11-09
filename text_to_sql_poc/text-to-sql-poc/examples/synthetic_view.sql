-- Exemple fictif facultatif, à exécuter uniquement sur une base de test.
-- Ne modifie aucune table métier et ne s'exécute jamais au démarrage du POC.
CREATE VIEW public.v_metric_demo AS
SELECT * FROM (VALUES
    ('A'::text, DATE '2025-01-10', 2.5::numeric),
    ('A'::text, DATE '2025-02-10', 1.5::numeric),
    ('B'::text, DATE '2025-01-15', 3.0::numeric),
    ('B'::text, DATE '2025-02-15', 2.0::numeric),
    ('A'::text, DATE '2024-12-20', 9.0::numeric)
) AS synthetic(category, event_date, measure);

-- Exemple de droits, à appliquer avec un rôle déjà créé :
-- GRANT USAGE ON SCHEMA public TO "<ROLE_LECTURE>";
-- GRANT SELECT ON public.v_metric_demo TO "<ROLE_LECTURE>";
-- Ces GRANT n'enlèvent aucun privilège préexistant du rôle.
