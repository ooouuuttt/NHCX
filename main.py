"""
NHCX Insurance Plan PDF-to-FHIR Pipeline

Usage:
    python main.py                 — process all PDFs
    streamlit run reviewer/review_ui.py  — launch review UI
"""

import os
import json
import yaml
import logging
from tqdm import tqdm

from utils.logger import setup_logging
from extractor.pdf import extract_text
from llm.openai_llm import extract_insurance_data
from mapper.nhcx_mapper import map_to_fhir
from validator.fhir_validator import validate, format_validation_report

# ── Setup logging ──
setup_logging()
logger = logging.getLogger(__name__)

# ── Load settings ──
settings = yaml.safe_load(open("config/settings.yaml"))

INPUT = settings["paths"]["input"]
OUTPUT = settings["paths"]["output"]
ENABLE_VALIDATION = settings.get("pipeline", {}).get("enable_validation", True)
ENABLE_REVIEW = settings.get("pipeline", {}).get("enable_human_review", False)

PENDING_DIR = os.path.join(OUTPUT, "pending")

os.makedirs(OUTPUT, exist_ok=True)
os.makedirs(PENDING_DIR, exist_ok=True)
os.makedirs("logs", exist_ok=True)


def run():
    files = os.listdir(INPUT)
    pdf_files = [f for f in files if f.lower().endswith(".pdf")]

    logger.info(f"Found {len(pdf_files)} PDF files in {INPUT}")

    success_count = 0
    fail_count = 0

    for file in tqdm(pdf_files, desc="Processing PDFs"):
        try:
            logger.info(f"Processing: {file}")
            pdf_path = os.path.join(INPUT, file)

            # Step 1 — Extract text from PDF
            text = extract_text(pdf_path)

            if not text.strip():
                logger.warning(f"Empty text extracted from {file}, skipping")
                continue

            # Step 2 — LLM extraction (structured data)
            data = extract_insurance_data(text)

            if not data.get("plan_name") and not data.get("benefits"):
                logger.warning(f"No meaningful data extracted from {file}, skipping")
                continue

            # Step 3 — Map to NHCX FHIR Bundle
            bundle = map_to_fhir(data)

            # Step 4 — Validate
            if ENABLE_VALIDATION:
                errors = validate(bundle)
                report = format_validation_report(errors)
                logger.info(f"Validation for {file}: {report}")

                # Log errors but don't skip — save with warnings
                if errors:
                    logger.warning(f"{file} has {len(errors)} validation error(s)")

            # Step 5 — Save output
            output_file = file.replace(".pdf", ".json")

            if ENABLE_REVIEW:
                # Save to pending folder for human review
                output_path = os.path.join(PENDING_DIR, output_file)
                logger.info(f"Saved to pending review: {output_path}")
            else:
                # Save directly to output
                output_path = os.path.join(OUTPUT, output_file)
                logger.info(f"Saved: {output_path}")

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(bundle, f, indent=2, ensure_ascii=False)

            # Print the final NHCX FHIR bundle JSON to stdout
            print(f"\n--- GENERATED FHIR BUNDLE FOR {file} ---")
            print(json.dumps(bundle, indent=2, ensure_ascii=False))
            print("-" * 50)

            success_count += 1

        except Exception as e:
            fail_count += 1
            logger.error(f"FAILED: {file} — {str(e)}", exc_info=True)

    # Summary
    logger.info(f"\nPipeline complete: {success_count} succeeded, {fail_count} failed")

    if ENABLE_REVIEW and success_count > 0:
        logger.info(f"Bundles saved to {PENDING_DIR}/ — launch review UI with:")
        logger.info("  streamlit run reviewer/review_ui.py")


if __name__ == "__main__":
    run()