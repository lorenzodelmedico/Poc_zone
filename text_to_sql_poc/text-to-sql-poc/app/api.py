import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from app.auth import TokenProvider
from app.charts import resolve_chart
from app.database import execute_query
from app.errors import AppError
from app.formatter import format_result
from app.llm import generate_sql
from app.mcp_client import call_metadata_tool, metadata_session
from app.settings import ROOT, load_settings
from app.sql_validator import validate_sql

logger = logging.getLogger("poc")
logging.getLogger("httpx").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(application):
    settings = load_settings()
    application.state.settings = settings
    application.state.tokens = TokenProvider(settings)
    application.state.query_lock = asyncio.Lock()
    async with metadata_session() as session:
        application.state.mcp = session
        yield


app = FastAPI(title="POC Text-to-SQL", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "frontend"), name="static")


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=4000)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse({"status": "error", "code": exc.code, "message": exc.message}, status_code=exc.status)


@app.get("/")
def index():
    return FileResponse(ROOT / "frontend" / "index.html")


@app.get("/health")
def health():
    # Santé du processus ; ce point ne teste pas les accès LLM/BDD.
    return {"status": "ok", "echarts_ready": (ROOT / "frontend/vendor/echarts.min.js").is_file()}


@app.get("/api/catalog")
async def catalog():
    metadata = await call_metadata_tool(app.state.mcp, "get_view_metadata")
    charts = await call_metadata_tool(app.state.mcp, "get_chart_catalog")
    return {"view": metadata["view"], **charts}


@app.post("/api/query")
async def query(payload: QueryRequest):
    started = time.monotonic()
    request_id = uuid.uuid4().hex[:12]
    status = "error"
    try:
        # POC mono-utilisateur : sérialiser les demandes et les accès au MCP.
        async with app.state.query_lock:
            settings = app.state.settings
            settings.check_live()
            metadata = await call_metadata_tool(app.state.mcp, "get_view_metadata")
            charts = await call_metadata_tool(app.state.mcp, "get_chart_catalog")
            generation = await asyncio.to_thread(generate_sql, settings, metadata, payload.question, charts)
            if generation["status"] != "ok":
                status = generation["status"]
                return {**generation, "request_id": request_id, "rows": []}
            chart = resolve_chart(generation["chart"], charts)
            sql = validate_sql(generation["sql"], metadata, settings.max_rows, chart_id=chart["id"])
            raw_rows = await asyncio.to_thread(execute_query, settings, app.state.tokens, sql)
            rows = format_result(raw_rows, chart["id"])
            status = "ok"
            return {
                "status": "ok", "request_id": request_id, "sql": sql,
                "assumptions": generation["assumptions"],
                "chart": chart,
                "rows": rows, "row_count": len(rows),
            }
    except AppError:
        raise
    except Exception:
        # Aucune exception brute (URL, SQL, identifiant, réponse amont) dans les logs.
        raise AppError("PROCESSING_ERROR", "Échec du traitement ; contrôler configuration et disponibilité MCP/LLM/BDD.", 502) from None
    finally:
        logger.info("request_id=%s status=%s duration_ms=%d", request_id, status,
                    int((time.monotonic() - started) * 1000))
