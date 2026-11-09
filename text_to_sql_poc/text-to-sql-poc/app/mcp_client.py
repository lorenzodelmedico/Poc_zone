import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import timedelta

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.errors import AppError
from app.settings import ROOT


@asynccontextmanager
async def metadata_session():
    # Ne pas transmettre les identifiants LLM/BDD au sous-processus de métadonnées.
    env = {key: value for key, value in os.environ.items() if key in {
        "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE",
        "VIRTUAL_ENV", "PYTHONPATH", "METADATA_PATH",
    }}
    params = StdioServerParameters(command=sys.executable, args=["-m", "app.mcp_server"],
                                   cwd=str(ROOT), env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=15)) as session:
            await session.initialize()
            yield session


async def call_metadata_tool(session, name):
    result = await session.call_tool(name, arguments={})
    if result.isError:
        raise AppError("MCP_TOOL", "Le MCP n'a pas pu fournir les métadonnées ; vérifier le fichier local.", 502)
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    for content in result.content:
        if getattr(content, "type", None) == "text":
            try:
                data = json.loads(content.text)
                if isinstance(data, dict):
                    return data
            except ValueError:
                pass
    raise AppError("MCP_FORMAT", "Le MCP n'a pas retourné un objet JSON exploitable.", 502)
