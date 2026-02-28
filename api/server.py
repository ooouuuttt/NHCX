"""
NHCX Insurance Plan PDF-to-FHIR REST API

Endpoints:
    POST /convert         — Upload a PDF, get back an NHCX FHIR Bundle JSON
    POST /validate        — Validate an existing FHIR Bundle JSON
    GET  /health          — Health check

Launch with:
    uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import sys
import logging
import tempfile
import shutil
from datetime import datetime, timezone

from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List

# Ensure project root is on sys.path so imports work regardless of CWD
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_PROJECT_ROOT)  # set CWD to project root for relative config paths
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from utils.logger import setup_logging
from extractor.pdf import extract_text
from llm.openai_llm import extract_insurance_data
from mapper.nhcx_mapper import map_to_fhir
from validator.fhir_validator import validate, format_validation_report

# ── Setup logging (creates logs/ dir first) ──
setup_logging(log_file="logs/api.log")
logger = logging.getLogger(__name__)


# ── FastAPI App ──
app = FastAPI(
    title="NHCX Insurance Plan Converter",
    description=(
        "Converts insurance plan PDFs into NHCX-compliant FHIR InsurancePlan bundles. "
        "Supports automated extraction, mapping, and validation."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── Response Models ──
class ConvertResponse(BaseModel):
    success: bool
    filename: str
    bundle: dict
    validation_errors: List[str]
    validation_passed: bool


class ValidateResponse(BaseModel):
    valid: bool
    errors: List[str]
    report: str


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str


# ── Endpoints ──

@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        version="1.0.0"
    )


@app.post("/convert", response_model=ConvertResponse, tags=["Conversion"])
async def convert_pdf(file: UploadFile = File(..., description="Insurance plan PDF file")):
    """
    Upload an insurance plan PDF and receive an NHCX-compliant FHIR Bundle.

    Pipeline:
    1. Extract text from PDF
    2. Use LLM to parse structured insurance data
    3. Map to FHIR InsurancePlan bundle
    4. Validate against NHCX profiles
    5. Return the bundle with validation results
    """
    # Validate file type
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    # Save uploaded file to temp location
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, file.filename)

    try:
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        logger.info(f"API: Processing {file.filename} ({len(content)} bytes)")

        # Step 1 — Extract text
        text = extract_text(temp_path)
        if not text.strip():
            raise HTTPException(status_code=422, detail="Could not extract text from PDF.")

        # Step 2 — LLM extraction
        data = extract_insurance_data(text)
        if not data.get("plan_name") and not data.get("benefits"):
            raise HTTPException(status_code=422, detail="No insurance data could be extracted from this PDF.")

        # Step 3 — Map to FHIR
        bundle = map_to_fhir(data)

        # Step 4 — Validate
        errors = validate(bundle)
        validation_passed = len(errors) == 0

        logger.info(f"API: {file.filename} — validation {'passed' if validation_passed else f'failed ({len(errors)} errors)'}")

        return ConvertResponse(
            success=True,
            filename=file.filename,
            bundle=bundle,
            validation_errors=errors,
            validation_passed=validation_passed
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API: Failed processing {file.filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
    finally:
        # Cleanup temp file
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.post("/validate", response_model=ValidateResponse, tags=["Validation"])
async def validate_bundle(bundle: dict):
    """
    Validate an existing FHIR Bundle JSON against NHCX profiles.
    Accepts a raw FHIR Bundle JSON body.
    """
    try:
        errors = validate(bundle)
        report = format_validation_report(errors)

        return ValidateResponse(
            valid=len(errors) == 0,
            errors=errors,
            report=report
        )
    except Exception as e:
        logger.error(f"API: Validation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")
