"""Debug script to see what LLM extracts"""
import json
import os
from extractor.pdf import extract_text
from llm.openai_llm import extract_insurance_data

# Get the Aditya Birla PDF
input_dir = "input_pdfs/pdfs"
pdf_files = [f for f in os.listdir(input_dir) if "Aditya Birla" in f and f.endswith(".pdf")]

if not pdf_files:
    print("No Aditya Birla PDF found")
    exit(1)

pdf_path = os.path.join(input_dir, pdf_files[0])
print(f"Processing: {pdf_path}")

# Extract text
text = extract_text(pdf_path)
print(f"\nExtracted {len(text)} characters from PDF\n")

# LLM extraction
data = extract_insurance_data(text)

# Print extracted data
print("=" * 80)
print("EXTRACTED DATA FROM LLM")
print("=" * 80)
print(json.dumps(data, indent=2)[:5000])  # Print first 5000 chars
print("\n...")

# Check for specific fields
print("\n" + "=" * 80)
print("DATA VALIDATION")
print("=" * 80)
print(f"Plan Name: {data.get('plan_name')}")
print(f"Plan Type: {data.get('plan_type')}")
print(f"Insurer: {data.get('insurer_name')}")
print(f"Policy Period Years: {data.get('policy_period_years')}")
print(f"Period Start Date: {data.get('period_start_date')}")
print(f"Period End Date: {data.get('period_end_date')}")

# Check benefits
benefits = data.get('benefits', [])
print(f"\nNumber of Benefits: {len(benefits)}")

if benefits:
    print("\nFirst 3 Benefits:")
    for i, benefit in enumerate(benefits[:3]):
        print(f"\nBenefit {i+1}: {benefit.get('name')}")
        print(f"  Limit: {benefit.get('limit')}")
        print(f"  Type: {benefit.get('type')}")
        print(f"  Deductible: {benefit.get('deductible')}")
        print(f"  Coverage: {benefit.get('coverage_details')}")

print("\n" + "=" * 80)
print("CHECKING AMOUNT FIELDS")
print("=" * 80)

# Look for any amount-related fields in benefits
for i, benefit in enumerate(benefits[:5]):
    print(f"\nBenefit {i+1}: {benefit.get('name')}")
    for key, value in benefit.items():
        if any(word in key.lower() for word in ['limit', 'amount', 'cost', 'premium', 'sum', 'insured']):
            print(f"  {key}: {value}")
