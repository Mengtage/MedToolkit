"""
MedPaperHunter - Main FastAPI Application
==========================================

Integrates all backend modules into a complete medical literature search system.

Endpoints:
    POST /api/search/analyze     - LLM analysis + PICO/PEO decomposition (NEW)
    POST /api/search/build       - Generate strategies from PICO concepts (NEW)
    POST /api/search/strategy    - Generate search strategies from natural language
    POST /api/search/execute     - Execute search on specified databases
    POST /api/search/import-csv  - Import articles from CSV
    POST /api/process/dedup      - Deduplicate articles
    POST /api/process/screen     - LLM screening
    POST /api/export/excel        - Export to Excel
    POST /api/export/strategies  - Export strategies to TXT
    POST /api/export/csv         - Export articles to CSV
    GET  /api/config/status      - Check configuration status
"""

from __future__ import annotations

import csv
import io
import logging
import os
import tempfile
from typing import Any
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from dedup import deduplicate_by_pmid, deduplicate_by_title, llm_screen
from exporter import articles_to_csv, export_strategies_txt, export_to_excel
from llm_medical_search import LLMClient, LLMConfig, LLMedicalSearchBuilder
from medical_search_strategy_builder import MedicalSearchStrategyBuilder
from pubmed_fetcher import fetch_pubmed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("medpaperhunter")

# ---------------------------------------------------------------------------
# Configuration from environment variables
# ---------------------------------------------------------------------------

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
# Set OUTPUT_DIR to project root/output by default
OUTPUT_DIR = os.getenv("OUTPUT_DIR", str(Path(__file__).parent.parent / "output"))

# ---------------------------------------------------------------------------
# Ensure output directory exists
# ---------------------------------------------------------------------------

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="MedPaperHunter",
    description="Medical literature search, deduplication, screening, and export system",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount frontend static files
frontend_path = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")

# Serve index.html at root
@app.get("/")
async def read_root():
    return FileResponse(str(frontend_path / "index.html"))

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _get_llm_client() -> LLMClient:
    """Create an LLM client if API key is configured.

    Returns:
        LLMClient instance.

    Raises:
        HTTPException: If LLM_API_KEY is not configured.
    """
    if not LLM_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="LLM API key is not configured. Set the LLM_API_KEY environment variable.",
        )
    config = LLMConfig(
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
        model=LLM_MODEL,
    )
    return LLMClient(config)


def _get_llm_builder() -> LLMedicalSearchBuilder:
    """Create an LLMedicalSearchBuilder if API key is configured.

    Returns:
        LLMedicalSearchBuilder instance.

    Raises:
        HTTPException: If LLM_API_KEY is not configured.
    """
    if not LLM_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="LLM API key is not configured. Set the LLM_API_KEY environment variable.",
        )
    return LLMedicalSearchBuilder(
        llm_api_key=LLM_API_KEY,
        llm_base_url=LLM_BASE_URL,
        llm_model=LLM_MODEL,
    )


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    question: str = Field(..., description="Natural language research question")
    databases: list[str] = Field(
        default=["pubmed", "embase", "cochrane", "wos", "arxiv"],
        description="Target databases for strategy generation",
    )


class AnalyzeResponse(BaseModel):
    framework: str = Field(..., description="PICO or PEO")
    research_type: str = Field(..., description="Research type description")
    concepts: dict[str, dict[str, Any]] = Field(..., description="PICO concepts")
    language: str = Field(..., description="Input language (zh/en)")
    english_question: str | None = Field(None, description="Translated English question")
    validation_tips: list[str] = Field(default_factory=list, description="Validation tips")


class BuildRequest(BaseModel):
    concepts: dict[str, dict[str, Any]] = Field(..., description="PICO concepts")
    framework: str = Field(default="PICO", description="Framework type (PICO/PEO)")
    databases: list[str] = Field(
        default=["pubmed", "embase", "cochrane", "wos", "arxiv"],
        description="Target databases",
    )
    question: str = Field(default="", description="Original research question")


class BuildResponse(BaseModel):
    strategies: dict[str, str] = Field(..., description="Database-specific search strategies")
    validation_tips: list[str] = Field(default_factory=list, description="Validation tips")
    language: str = Field(default="en", description="Input language")


class StrategyRequest(BaseModel):
    question: str = Field(..., description="Natural language research question")
    databases: list[str] = Field(
        default=["pubmed", "embase", "cochrane", "wos"],
        description="Target databases for strategy generation",
    )
    date_range: str = Field(default="", description="Date range filter, e.g. 2020/01/01-2024/12/31")


class ExecuteRequest(BaseModel):
    strategies: dict[str, str] = Field(..., description="Database-specific search strategies")
    databases: list[str] = Field(..., description="Databases to search")
    date_range: str = Field(default="", description="Date range filter")
    max_results: int = Field(default=500, description="Maximum results per database")


class DedupRequest(BaseModel):
    articles: list[dict[str, Any]] = Field(..., description="List of article dicts to deduplicate")


class ScreenRequest(BaseModel):
    articles: list[dict[str, Any]] = Field(..., description="List of article dicts to screen")
    question: str = Field(..., description="Research question for relevance screening")


class ExportArticlesRequest(BaseModel):
    articles: list[dict[str, Any]] = Field(..., description="List of article dicts to export")


class ExportStrategiesRequest(BaseModel):
    strategies: dict[str, str] = Field(..., description="Database-specific search strategies")





# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------





@app.post("/api/search/analyze", response_model=AnalyzeResponse)
async def analyze_question(request: AnalyzeRequest):
    """Analyze a research question using LLM to perform PICO/PEO decomposition.

    Returns structured PICO concepts that can be edited by the user before
    generating search strategies.
    """
    if not LLM_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="LLM API key is not configured. Set the LLM_API_KEY environment variable.",
        )

    try:
        builder = LLMedicalSearchBuilder(
            llm_api_key=LLM_API_KEY,
            llm_base_url=LLM_BASE_URL,
            llm_model=LLM_MODEL,
        )

        result = await builder.build_from_question(
            question=request.question,
            databases=request.databases,
        )

        return AnalyzeResponse(
            framework=result["analysis"].get("framework", "PICO"),
            research_type=result["analysis"].get("research_type", "interventional/therapeutic"),
            concepts=result["analysis"].get("concepts", {}),
            language=result.get("language", "en"),
            english_question=result.get("english_question"),
            validation_tips=result.get("validation_tips", []),
        )

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to analyze question")
        raise HTTPException(status_code=500, detail=f"Failed to analyze question: {e}")


@app.post("/api/search/build", response_model=BuildResponse)
async def build_strategies(request: BuildRequest):
    """Build search strategies from PICO concepts.

    This endpoint accepts user-edited PICO concepts and generates
    database-specific search strategies.
    """
    try:
        strategy_builder = MedicalSearchStrategyBuilder()

        result = strategy_builder.build(
            question=request.question or "User-provided concepts",
            concepts=request.concepts,
            framework=request.framework,
            databases=request.databases,
        )

        return BuildResponse(
            strategies=result.strategies,
            validation_tips=result.validation_tips,
            language=result.language,
        )

    except Exception as e:
        logger.exception("Failed to build strategies")
        raise HTTPException(status_code=500, detail=f"Failed to build strategies: {e}")


@app.post("/api/search/strategy")
async def generate_strategy(request: StrategyRequest):
    """Generate search strategies from a natural language research question.

    Uses LLMedicalSearchBuilder to analyze the question via LLM, validate
    MeSH terms, and produce database-specific search strategies.
    """
    try:
        builder = _get_llm_builder()
        result = await builder.build_from_question(
            question=request.question,
            databases=request.databases,
        )
        return {
            "strategies": result["strategies"],
            "analysis": result["analysis"],
            "mesh_validation": result.get("mesh_validation", {}),
            "validation_tips": result.get("validation_tips", []),
            "language": result.get("language", "en"),
        }
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate search strategy")
        raise HTTPException(status_code=500, detail=f"Failed to generate search strategy: {e}")


@app.post("/api/search/execute")
async def execute_search(request: ExecuteRequest):
    """Execute search on specified databases using provided strategies.

    PubMed is searched via NCBI E-utilities API. Other databases require
    direct network access from an institution with subscription.
    """
    all_articles: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    errors: list[dict[str, str]] = []

    for db in request.databases:
        strategy = request.strategies.get(db, "")
        if not strategy:
            logger.warning("No strategy provided for database: %s, skipping", db)
            continue

        try:
            if db == "pubmed":
                articles = await fetch_pubmed(
                    query=strategy,
                    max_results=request.max_results,
                    date_range=request.date_range,
                )
                all_articles.extend(articles)
                counts["pubmed"] = len(articles)
                logger.info("PubMed search returned %d articles", len(articles))

            elif db == "scopus":
                # Scopus requires institutional access - currently not implemented
                # Users should use CSV import with exported results
                error_msg = (
                    f"Scopus 检索暂不支持直接API访问。请通过Scopus官网执行检索后，"
                    f"将结果以CSV格式导入系统。Scopus官网: https://www.scopus.com"
                )
                logger.warning(error_msg)
                errors.append({
                    "database": db,
                    "error": error_msg,
                    "suggestion": "请在Scopus官网检索后导入CSV文件"
                })
                counts["scopus"] = 0

            elif db == "wos":
                # Web of Science requires institutional access - currently not implemented
                error_msg = (
                    f"Web of Science 检索暂不支持直接API访问。请通过Web of Science官网执行检索后，"
                    f"将结果以CSV格式导入系统。Web of Science官网: https://www.webofscience.com"
                )
                logger.warning(error_msg)
                errors.append({
                    "database": db,
                    "error": error_msg,
                    "suggestion": "请在Web of Science官网检索后导入CSV文件"
                })
                counts["wos"] = 0

            elif db == "cochrane":
                error_msg = (
                    f"Cochrane Library 检索暂不支持直接API访问。请通过Cochrane官网执行检索后，"
                    f"将结果以CSV格式导入系统。Cochrane Library官网: https://www.cochranelibrary.com"
                )
                logger.warning(error_msg)
                errors.append({
                    "database": db,
                    "error": error_msg,
                    "suggestion": "请在Cochrane Library官网检索后导入CSV文件"
                })
                counts["cochrane"] = 0

            elif db == "arxiv":
                error_msg = (
                    f"arXiv 检索暂不支持直接API访问。请通过arXiv官网执行检索后，"
                    f"将结果以CSV格式导入系统。arXiv官网: https://arxiv.org"
                )
                logger.warning(error_msg)
                errors.append({
                    "database": db,
                    "error": error_msg,
                    "suggestion": "请在arXiv官网检索后导入CSV文件"
                })
                counts["arxiv"] = 0

            else:
                error_msg = f"不支持的数据库: {db}"
                logger.warning(error_msg)
                errors.append({
                    "database": db,
                    "error": error_msg,
                    "suggestion": "请使用支持的数据库或导入CSV文件"
                })
                counts[db] = 0

        except Exception as e:
            logger.exception("Search failed for database: %s", db)
            error_msg = f"{db} 检索失败: {str(e)}"
            errors.append({
                "database": db,
                "error": error_msg,
                "suggestion": "请检查网络连接或稍后重试"
            })
            counts[db] = 0

    return {
        "articles": all_articles,
        "counts": counts,
        "total": len(all_articles),
        "errors": errors,
    }


@app.post("/api/search/import-file")
async def import_file(file: UploadFile = File(...)):
    """Import articles from a CSV or Excel file.

    Expects columns: Title, Authors, Journal, Publication Date, Abstract, DOI, PMID, Source.
    This endpoint is designed for manually exporting results from other databases.
    """
    filename = file.filename or ""
    is_excel = filename.lower().endswith((".xlsx", ".xls"))

    if not is_excel and not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV or Excel files are accepted.")

    try:
        content = await file.read()

        if is_excel:
            import openpyxl
            from io import BytesIO
            wb = openpyxl.load_workbook(BytesIO(content))
            ws = wb.active
            headers = [cell.value for cell in ws[1]]
            rows_data = [[cell.value for cell in row] for row in ws.iter_rows(min_row=2)]
            reader = [dict(zip(headers, row)) for row in rows_data if any(row)]
        else:
            text = content.decode("utf-8-sig")
            reader = list(csv.DictReader(io.StringIO(text)))

        articles: list[dict[str, Any]] = []
        for row in reader:
            row_lower = {k.lower().strip(): v for k, v in row.items()} if row else {}
            article: dict[str, Any] = {
                "source": row.get("Source", "import"),
                "pmid": row.get("PMID") or row.get("pmid") or row.get("PMID".lower()) or None,
                "title": row.get("Title") or row.get("title") or row.get("Title".lower()) or "",
                "authors": [],
                "journal": row.get("Journal", "") or row.get("journal", "") or "",
                "pub_date": row.get("Publication Date", "") or row.get("publication date", "") or "",
                "abstract": row.get("Abstract", "") or row.get("abstract", "") or "",
                "doi": row.get("DOI") or row.get("doi") or row.get("DOI".lower()) or None,
            }

            authors_raw = row.get("Authors", "") or row.get("authors", "") or ""
            if authors_raw:
                article["authors"] = [
                    a.strip() for a in str(authors_raw).replace(";", ",").split(",") if a.strip()
                ]

            if article["title"]:
                articles.append(article)

        return {
            "articles": articles,
            "count": len(articles),
        }

    except Exception as e:
        logger.exception("Failed to import file")
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {e}")


@app.post("/api/process/dedup")
async def deduplicate_articles(request: DedupRequest):
    """Deduplicate articles by PMID first, then by normalized title.

    For each deduplication step, the article with the most complete data
    is retained when duplicates are found.
    """
    if not request.articles:
        return {"articles": [], "removed": 0}

    original_count = len(request.articles)

    # Step 1: Deduplicate by PMID
    after_pmid = deduplicate_by_pmid(request.articles)

    # Step 2: Deduplicate remaining by title
    after_title = deduplicate_by_title(after_pmid)

    removed = original_count - len(after_title)

    return {
        "articles": after_title,
        "removed": removed,
        "original_count": original_count,
        "remaining_count": len(after_title),
    }


@app.post("/api/process/screen")
async def screen_articles(request: ScreenRequest):
    """Screen articles for relevance using LLM.

    Sends article titles and abstracts to the LLM in batches,
    asking whether each article is relevant to the research question.
    """
    if not request.articles:
        return {"articles": [], "total": 0}

    try:
        llm_client = _get_llm_client()
    except HTTPException:
        raise

    try:
        # Get all screened articles with screening_result field
        all_screened = []
        batch_size = 20
        
        from dedup import (
            SCREENING_SYSTEM_PROMPT,
            SCREENING_USER_TEMPLATE,
            _format_article_for_screening,
            _parse_screening_response,
            _call_llm,
        )
        
        for offset in range(0, len(request.articles), batch_size):
            batch = request.articles[offset : offset + batch_size]
            
            # Format articles for the prompt
            articles_text = "\n".join(
                _format_article_for_screening(i + 1, article)
                for i, article in enumerate(batch)
            )
            
            user_message = SCREENING_USER_TEMPLATE.format(
                question=request.question,
                count=len(batch),
                articles_text=articles_text,
            )
            
            messages = [
                {"role": "system", "content": SCREENING_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ]
            
            # Call the LLM
            response_text = await _call_llm(llm_client, messages)
            
            # Parse the response
            screened = _parse_screening_response(response_text, batch)
            all_screened.extend(screened)
        
        # Convert to frontend expected format
        articles_with_screening = []
        for article in all_screened:
            article_copy = dict(article)
            # Map screening_result to screening field (frontend expects this)
            article_copy["screening"] = "included" if article.get("screening_result") == "YES" else "excluded"
            articles_with_screening.append(article_copy)

        included_count = sum(1 for a in articles_with_screening if a["screening"] == "included")
        excluded_count = len(articles_with_screening) - included_count
        
        return {
            "articles": articles_with_screening,
            "total": len(articles_with_screening),
            "included_count": included_count,
            "excluded_count": excluded_count,
        }

    except Exception as e:
        logger.exception("LLM screening failed")
        raise HTTPException(status_code=500, detail=f"LLM screening failed: {e}")


@app.post("/api/export/excel")
async def export_excel(request: ExportArticlesRequest):
    """Export articles to a styled Excel file.

    Returns the Excel file as a downloadable binary stream.
    """
    if not request.articles:
        raise HTTPException(status_code=400, detail="No articles to export.")

    try:
        filepath = os.path.join(OUTPUT_DIR, "search_results.xlsx")
        export_to_excel(request.articles, filepath)

        def iterfile():
            with open(filepath, "rb") as f:
                yield from f

        return StreamingResponse(
            iterfile(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=search_results.xlsx"},
        )

    except Exception as e:
        logger.exception("Excel export failed")
        raise HTTPException(status_code=500, detail=f"Excel export failed: {e}")


@app.post("/api/export/strategies")
async def export_strategies(request: ExportStrategiesRequest):
    """Export search strategies to a text file.

    Returns the text file as a downloadable stream.
    """
    if not request.strategies:
        raise HTTPException(status_code=400, detail="No strategies to export.")

    try:
        filepath = os.path.join(OUTPUT_DIR, "search_strategies.txt")
        export_strategies_txt(request.strategies, filepath)

        def iterfile():
            with open(filepath, "rb") as f:
                yield from f

        return StreamingResponse(
            iterfile(),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=search_strategies.txt"},
        )

    except Exception as e:
        logger.exception("Strategy export failed")
        raise HTTPException(status_code=500, detail=f"Strategy export failed: {e}")


@app.post("/api/export/csv")
async def export_csv(request: ExportArticlesRequest):
    """Export articles to a CSV file.

    Returns the CSV file as a downloadable stream.
    """
    if not request.articles:
        raise HTTPException(status_code=400, detail="No articles to export.")

    try:
        filepath = os.path.join(OUTPUT_DIR, "search_results.csv")
        articles_to_csv(request.articles, filepath)

        def iterfile():
            with open(filepath, "rb") as f:
                yield from f

        return StreamingResponse(
            iterfile(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=search_results.csv"},
        )

    except Exception as e:
        logger.exception("CSV export failed")
        raise HTTPException(status_code=500, detail=f"CSV export failed: {e}")


@app.get("/api/config/status")
async def config_status():
    """Check what services and features are configured.

    Only returns boolean flags -- API keys and credentials are never exposed.
    """
    return {
        "llm_configured": bool(LLM_API_KEY),
        "llm_model": LLM_MODEL,
        "output_dir": OUTPUT_DIR,
    }


# ---------------------------------------------------------------------------
# Startup event
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def startup():
    """Log configuration status on startup (without exposing secrets)."""
    logger.info("MedPaperHunter starting up")
    logger.info("LLM configured: %s (model: %s)", bool(LLM_API_KEY), LLM_MODEL)
    logger.info("Output directory: %s", os.path.abspath(OUTPUT_DIR))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
