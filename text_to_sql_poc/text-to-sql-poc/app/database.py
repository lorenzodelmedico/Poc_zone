from app.errors import AppError


def connect_with_custom_token(settings, token):
    """Point d'adaptation si le jeton n'est pas un mot de passe PostgreSQL.

    La connexion retournée doit être compatible avec psycopg.Connection.
    Pour une API HTTP intermédiaire, adapter execute_query dans ce fichier.
    """
    raise AppError("TOKEN_ADAPTER_REQUIRED", "Le mécanisme custom doit être implémenté dans app/database.py.")


def open_connection(settings, token_provider):
    import psycopg

    for attempt in range(2):
        token = token_provider.get_token()
        try:
            if settings.db_token_mode == "custom":
                return connect_with_custom_token(settings, token)
            kwargs = {
                "host": settings.db_host, "port": settings.db_port,
                "dbname": settings.db_name, "user": settings.db_user,
                "password": token, "sslmode": settings.db_sslmode,
                "connect_timeout": settings.db_connect_timeout,
                "options": "-c search_path=pg_catalog -c default_transaction_read_only=on",
            }
            if settings.db_sslrootcert:
                kwargs["sslrootcert"] = settings.db_sslrootcert
            return psycopg.connect(**kwargs)
        except psycopg.Error as exc:
            # Renouveler uniquement sur une erreur d'authentification structurée
            # durant la connexion. Aucune requête métier n'a encore été exécutée.
            if attempt == 0 and exc.sqlstate and exc.sqlstate.startswith("28"):
                token_provider.invalidate()
                continue
            raise AppError("DB_CONNECTION", "Connexion PostgreSQL refusée ; vérifier réseau, TLS, rôle et mécanisme du jeton.", 502) from None


def execute_query(settings, token_provider, sql):
    import psycopg

    try:
        with open_connection(settings, token_provider) as connection:
            connection.read_only = True
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL statement_timeout = {int(settings.statement_timeout_ms)}")
                cursor.execute("SET LOCAL lock_timeout = 1000")
                cursor.execute("SET LOCAL TIME ZONE 'UTC'")
                cursor.execute(sql)
                names = [col.name for col in cursor.description]
                rows = cursor.fetchmany(settings.max_rows + 1)
        if names != ["x", "y"]:
            raise AppError("RESULT_SHAPE", "La base doit retourner exactement les colonnes x et y.", 422)
        if len(rows) > settings.max_rows:
            raise AppError("RESULT_LIMIT", "Trop de groupes ; préciser les filtres ou la période. Aucun graphique partiel n'est affiché.", 422)
        return [dict(zip(names, row)) for row in rows]
    except psycopg.errors.QueryCanceled:
        raise AppError("DB_TIMEOUT", "La requête a dépassé la durée autorisée.", 504) from None
    except psycopg.Error:
        raise AppError("DB_QUERY", "PostgreSQL a refusé la requête ; vérifier types, SQL et règles de la vue.", 422) from None
