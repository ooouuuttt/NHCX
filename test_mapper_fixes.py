"""Test the mapper fixes without LLM"""
import json
from mapper.nhcx_mapper import map_to_fhir

# Test data with minimal policy_period_years
test_data = {
    "organization": "Aditya Birla Health Insurance Co. Limited",
    "insurer_id": "153",
    "uin": "ADIHLGP22023V032122",
    "plan_name": "Group Protect",
    "plan_type": "group",
    "coverage_type": "health",
    "sum_insured": "500000",
    "policy_period_years": "1",  # This is key - should generate period
    "currency": "INR",
    "telecom": {
        "phone": "1800 270 7000",
        "email": "care.healthinsurance@adityabirlacapital.com",
        "website": "www.adityabirlahealth.com/healthinsurance"
    },
    "benefits": [
        {
            "name": "OPD Expenses",
            "section": "Section I",
            "category": "outpatient",
            "description": "OPD coverage",
            "limit_amount": "",  # Empty - should not add 0.0
            "limit_unit": "amount",
            "max_days": "",
            "percentage_payout": "",
            "sub_benefits": [],
            "waiting_period_days": "",
            "is_optional": False
        },
        {
            "name": "Hospitalization",
            "section": "Section II",
            "category": "inpatient",
            "description": "Inpatient hospitalization",
            "limit_amount": "500000",  # Real amount
            "limit_unit": "amount",
            "max_days": "90",
            "sub_benefits": [],
            "waiting_period_days": "",
            "is_optional": False
        }
    ],
    "exclusions": [
        {
            "name": "Pre-existing Disease",
            "description": "PED treatment excluded for first 2 years",
            "category": "permanent",
            "waiting_period_days": "730"
        }
    ]
}

print("=" * 80)
print("TESTING MAPPER FIXES")
print("=" * 80)
print("\nTest Data:")
print(f"  policy_period_years: {test_data.get('policy_period_years')}")
print(f"  Benefit 1 limit_amount: '{test_data['benefits'][0].get('limit_amount')}'")
print(f"  Benefit 2 limit_amount: '{test_data['benefits'][1].get('limit_amount')}'")

print("\nMapping to FHIR...")
bundle = map_to_fhir(test_data)

# Extract InsurancePlan
insurance_plan = bundle["entry"][1]["resource"]

print("\n" + "=" * 80)
print("RESULTS")
print("=" * 80)

# CHECK 1: Period Present
period = insurance_plan.get("period")
print("\n1. PERIOD (FIX #2 - Always include period):")
if period:
    print(f"   [OK] Period PRESENT!")
    print(f"   Start: {period['start']}")
    print(f"   End:   {period['end']}")
else:
    print(f"   [FAIL] Period MISSING")

# CHECK 2: Benefit Limits
print("\n2. BENEFIT LIMITS (FIX #1 - Don't use 0.0 for missing amounts):")
benefits = insurance_plan["coverage"][0]["benefit"]

for idx, benefit in enumerate(benefits):
    name = benefit.get("type", {}).get("text", "Unknown")
    limit_list = benefit.get("limit", [])
    
    print(f"\n   Benefit {idx+1}: {name}")
    if limit_list:
        for i, limit in enumerate(limit_list):
            value = limit.get("value", {})
            if "value" in value:
                amt = value.get("value")
                if amt == 0.0:
                    print(f"      [FAIL] Limit {i+1} has 0.0 value - This is WRONG!")
                else:
                    print(f"      [OK] Limit {i+1}: {amt} {value.get('unit')}")
            else:
                code_text = limit.get("code", {}).get("text")
                print(f"      [OK] Limit {i+1}: Textual only ({code_text})")
    else:
        print(f"      [ERROR] No limit data!")

print("\n" + "=" * 80)

# Save for inspection
with open("output/pending/test_mapper_fixes.json", "w") as f:
    json.dump(bundle, f, indent=2)
print("\nTest output saved to: output/pending/test_mapper_fixes.json")
