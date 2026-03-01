"""Process just one PDF file for testing"""
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

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Load settings
settings = yaml.safe_load(open("config/settings.yaml"))

INPUT = settings["paths"]["input"]
OUTPUT = settings["paths"]["output"]
PENDING_DIR = os.path.join(OUTPUT, "pending")

os.makedirs(OUTPUT, exist_ok=True)
os.makedirs(PENDING_DIR, exist_ok=True)

def run():
    files = os.listdir(INPUT)
    pdf_files = [f for f in files if f.lower().endswith(".pdf")]
    
    # Process ONLY Aditya Birla files
    aditya_files = [f for f in pdf_files if "aditya birla" in f.lower()][:1]  # Just 1 file
    
    if not aditya_files:
        print("ERROR: No Aditya Birla PDF found")
        return
    
    logger.info(f"Processing {len(aditya_files)} PDF file(s)")
    
    for file in aditya_files:
        try:
            logger.info(f"Processing: {file}")
            pdf_path = os.path.join(INPUT, file)
            
            # Step 1: Extract text
            text = extract_text(pdf_path)
            if not text.strip():
                logger.warning(f"Empty text extracted from {file}")
                continue
            
            # Step 2: LLM extraction
            print(f"\nExtracting with LLM (this takes 2-3 minutes)...")
            data = extract_insurance_data(text)
            
            if not data.get("plan_name"):
                logger.warning(f"No plan name extracted from {file}")
                continue
            
            # Show what was extracted
            print(f"\nExtracted:")
            print(f"  Plan: {data.get('plan_name')}")
            print(f"  Type: {data.get('plan_type')}")
            print(f"  Policy Period Years: {data.get('policy_period_years')}")
            print(f"  Benefits: {len(data.get('benefits', []))}")
            
            # Step 3: Map to FHIR
            print(f"Mapping to FHIR...")
            bundle = map_to_fhir(data)
            
            # Step 4: Save
            output_file = os.path.join(PENDING_DIR, f"{file.replace('.pdf', '.json')}")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(bundle, f, indent=2)
            logger.info(f"Saved to {output_file}")
            
            # Step 5: Check for fixes
            print(f"\n" + "="*80)
            print(f"VERIFICATION")
            print(f"="*80)
            
            insurance_plan = bundle["entry"][1]["resource"]
            
            period = insurance_plan.get("period")
            if period:
                print(f"[OK] Period PRESENT: {period['start']} to {period['end']}")
            else:
                print(f"[FAIL] Period MISSING")
            
            # Check limits
            benefits = insurance_plan["coverage"][0]["benefit"]
            has_zero = False
            for idx, benefit in enumerate(benefits[:3]):
                for limit in benefit.get("limit", []):
                    if limit.get("value", {}).get("value") == 0.0:
                        has_zero = True
                        print(f"[FAIL] Benefit {idx+1} has 0.0 limit")
            
            if not has_zero:
                print(f"[OK] No 0.0 limits found")
            
            print(f"="*80 + "\n")
            
        except Exception as e:
            logger.error(f"Error processing {file}: {e}", exc_info=True)

if __name__ == "__main__":
    run()
