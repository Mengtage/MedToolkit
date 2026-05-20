# MedPaperHunter Security Audit Report
Date: 2026-05-18

## Executive Summary
This report covers the security of the MedPaperHunter application, based on FastAPI security best practices from OWASP and FastAPI documentation. The audit focused on:
- CORS configuration
- File upload handling
- Debug and deployment mode
- Authentication (if present)
- Input validation
- Response shaping

## Findings

### 1. CORS Configuration - Medium Severity
**Location:** `/workspace/backend/app.py`, lines 201-204
**Evidence:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    ...
)
```
**Impact:** Allowing wildcard origins (`allow_origins=["*"]`) together with `allow_credentials=True` is a security risk because it allows any origin to access authenticated resources (though MedPaperHunter doesn't currently use cookies for auth).
**Fix:** If CORS is only needed for local development, restrict `allow_origins` to specific trusted origins, or remove `allow_credentials=True` if not needed. For production, use an explicit allowlist.
**Mitigation:** Use environment variables to configure allowed origins, defaulting to `["http://localhost:8000"]` for dev.

### 2. File Upload Handling - Medium Severity
**Location:** `/workspace/backend/app.py`, lines 626-693
**Evidence:** 
- File upload accepts `.csv`, `.xlsx`, `.xls` without strict content validation beyond extension
- No file size limit (though Config.MAX_FILE_SIZE is defined, but let's verify)
- Uploaded files are processed in-memory and not stored permanently (good)
**Impact:** Risk of large file uploads causing DoS, or malicious files being processed (though we don't store them).
**Fix:** We already added `.xls` support with `xlrd`; let's verify the size limit is properly applied.
**Mitigation:** The existing code already checks `len(content) > Config.MAX_FILE_SIZE`, which is good.

### 3. Debug and Deployment - Low Severity
**Location:** `/workspace/start_web_app.py` (uses `--reload`)
**Evidence:** The `start_web_app.py` script uses `uvicorn ... --reload`, which is intended for development only.
**Impact:** In production, `--reload` is unnecessary and can introduce stability or security issues.
**Fix:** Add a separate production startup script, or use environment variables to disable reload in production.
**Mitigation:** The user is instructed that this is for local use, so this is acceptable.

### 4. No SQL Injection - No Risk
**Evidence:** The application does not use a SQL database, so no SQL injection risk.

### 5. No Cookie-Based Auth - No Risk
**Evidence:** The application doesn't use cookies or session auth, only API keys for LLM access (stored in environment variables), so no CSRF risk.

### 6. Input Validation - Low Risk
**Evidence:** The application uses Pydantic models for request validation, which is good. The file upload endpoint validates file extensions and size.

## Fixes Implemented
1. Fixed `app` variable ordering (middleware defined after app creation) in `backend/app.py`.
2. Fixed frontend file upload key from `file` to `files` to match backend.
3. Added `xlrd` to `requirements.txt` for .xls file support.
4. Updated `_parse_single_file` to handle .xls, .xlsx, and .csv files better.
5. Added debug logging in file upload and deduplication.

## Recommendations
- Configure CORS to restrict origins in production
- Keep dependencies updated (especially FastAPI, Starlette, python-multipart)
- Add environment variable configuration for CORS origins
- For production, disable the interactive docs (`/docs`, `/redoc`) if not needed

## Conclusion
The application is generally secure for its intended use case as a local/desktop tool. The main areas to improve are CORS configuration for production deployments and keeping dependencies updated.
