"""Quick test of single PDF processing"""
import os
import json
import yaml
from extractor.pdf import extract_text
from llm.openai_llm import extract_insurance_data
from mapper.nhcx_mapper import map_to_fhir

# Load settings
settings = yaml.safe_load(open("config/settings.yaml"))
INPUT = settings["paths"]["input"]
OUTPUT = settings["paths"]["output"]
PENDING_DIR = os.path.join(OUTPUT, "pending")

# Find Aditya Birla PDF
pdf_files = [f for f in os.listdir(INPUT) if "Aditya Birla" in f and f.endswith(".pdf")]
if not pdf_files:
    print("ERROR: No Aditya Birla PDF found")
    exit(1)

pdf_path = os.path.join(INPUT, pdf_files[0])
print(f"Processing: {pdf_path}\n")

# Step 1: Extract text
text = extract_text(pdf_path)
print(f"OK: Extracted {len(text)} characters\n")

# Step 2: LLM extraction
print("Extracting with LLM...")
data = extract_insurance_data(text)

# Show extracted data summary
print(f"\nExtracted Data Summary:")
print(f"  Plan name: {data.get('plan_name')}")
print(f"  Plan type: {data.get('plan_type')}")
print(f"  Policy period years: {data.get('policy_period_years')}")
print(f"  Period start date: {data.get('period_start_date')}")
print(f"  Period end date: {data.get('period_end_date')}")
print(f"  Sum insured: {data.get('sum_insured')}")
print(f"  Benefits count: {len(data.get('benefits', []))}")
print(f"  Exclusions count: {len(data.get('exclusions', []))}")

# Show first few benefits
if data.get('benefits'):
    print(f"\nFirst 3 Benefits:")
    for i, benefit in enumerate(data.get('benefits')[:3]):
        print(f"  {i+1}. {benefit.get('name')}")
        print(f"     limit_amount: {benefit.get('limit_amount')}")
        print(f"     limit_unit: {benefit.get('limit_unit')}")

# Step 3: Map to FHIR
print("\n\nMapping to FHIR Bundle...")
bundle = map_to_fhir(data)
print("OK: Bundle created\n")

# Save output
output_file = os.path.join(PENDING_DIR, "test_aditya_birla_fixed.json")
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(bundle, f, indent=2)
print(f"OK: Saved to {output_file}\n")

# Check for period
if "entry" in bundle and len(bundle["entry"]) > 1:
    insurance_plan = bundle["entry"][1].get("resource", {})
    if insurance_plan.get("resourceType") == "InsurancePlan":
        period = insurance_plan.get("period")
        print(f"InsurancePlan.period: {period}")
        if period:
            print(f"  [OK] Period PRESENT: {period['start']} to {period['end']}")
        else:
            print(f"  [ERROR] Period MISSING")
        
        # Check first benefit limit
        if insurance_plan.get("coverage"):
            benefits = insurance_plan["coverage"][0].get("benefit", [])
            if benefits:
                limit = benefits[0].get("limit", [])
                if limit:
                    print(f"\nFirst Benefit Limit:")
                    print(f"  {json.dumps(limit[0], indent=4)}")

