"""Validate the generated JSON file for period and limits"""
import json

json_file = "output/pending/Aditya Birla(G)_03.json"

try:
    with open(json_file, 'r', encoding='utf-8') as f:
        bundle = json.load(f)
    
    print("=" * 80)
    print("VALIDATION REPORT FOR: Aditya Birla(G)_03.json")
    print("=" * 80)
    
    # Check for InsurancePlan  
    if "entry" in bundle and len(bundle["entry"]) > 1:
        insurance_plan = bundle["entry"][1].get("resource", {})
        if insurance_plan.get("resourceType") == "InsurancePlan":
            
            # Check Period
            period = insurance_plan.get("period")
            print("\n1. PERIOD CHECK:")
            if period:
                print(f"   [OK] Period PRESENT")
                print(f"   Start: {period.get('start')}")
                print(f"   End:   {period.get('end')}")
            else:
                print(f"   [FAIL] Period MISSING - This is required for NHCX!")
            
            # Check Benefit Limits
            print("\n2. BENEFIT LIMITS CHECK:")
            if insurance_plan.get("coverage"):
                for cov_idx, coverage in enumerate(insurance_plan["coverage"][:2]):
                    benefits = coverage.get("benefit", [])
                    print(f"\n   Coverage {cov_idx + 1}: {len(benefits)} benefits")
                    
                    for b_idx, benefit in enumerate(benefits[:3]):
                        limit = benefit.get("limit", [])
                        if limit:
                            limit_val = limit[0].get("value", {})
                            if "value" in limit_val:
                                print(f"   Benefit {b_idx+1}: {benefit.get('type', {}).get('text', 'N/A')}")
                                print(f"     Limit value: {limit_val.get('value')}")
                                if limit_val.get('value') == 0.0:
                                    print(f"     [FAIL] This is a 0.0 limit!")
                            else:
                                print(f"   Benefit {b_idx+1}: {benefit.get('type', {}).get('text', 'N/A')}")
                                print(f"     [OK] Textual limit (no numeric value)")
                        else:
                            print(f"   Benefit {b_idx+1}: {benefit.get('type', {}).get('text', 'N/A')}")
                            print(f"     [No limit fields]")
            
            print("\n" + "=" * 80)
            
except Exception as e:
    print(f"ERROR: {e}")
