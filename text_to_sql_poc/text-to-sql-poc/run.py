import logging

import uvicorn

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    # Un seul worker, pas de reloader : durée de vie du MCP identique au backend.
    uvicorn.run("app.api:app", host="127.0.0.1", port=8000, access_log=False)
