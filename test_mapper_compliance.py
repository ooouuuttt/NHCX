"""Test mapper compliance with NDHM standards"""
import json
import sys
sys.path.insert(0, '.')

from mapper.nhcx_mapper import map_to_fhir

# Sample insurance data
sample_data = {
    "organization": "Aditya Birla Health Insurance Co. Limited",
    "insurer_id": "IRDAIRA001",
    "plan_name": "Group Protect",
    "uin": "ABHI-P00001/GRP/001",
    "plan_type": "group",
    "sum_insured": 500000,
    "premium_amount": 25000,
    "policy_period_years": 1,
    "telecom": {
        "phone": "+91-1800-266-9595",
        "email": "support@aditya birla.co.in",
        "website": "www.adityabirlahealth.com"
    },
    "benefits": [
        {
            "name": "ICU",
            "category": "inpatient",
            "limit_amount": 100000,
            "description": "ICU coverage for critical care.",
            "copay_percent": 0
        },
        {
            "name": "Room Rent",
            "category": "inpatient",
            "limit_amount": 5000,
            "max_days": 30,
            "description": "Daily room rent coverage.",
            "copay_percent": 10
        },
        {
            "name": "Ambulance Cover",
            "category": "transport",
            "limit_amount": 500,
            "description": "Emergency ambulance transport.",
            "copay_percent": 0
        }
    ],
    "exclusions": [
        {
            "name": "Pre-Existing Diseases",
            "description": "Diseases present before policy inception are excluded for 2 years.",
            "category": "time_bound",
            "waiting_period_days": 730
        },
        {
            "name": "War and Civil Unrest",
            "description": "Coverage excludes claims due to war or civil riots.",
            "category": "permanent",
            "waiting_period_days": 0
        }
    ],
    "eligibility": {
        "min_age": 18,
        "max_age": 75,
        "renewal_age": 99,
        "pre_existing_waiting": "2 years",
        "conditions": ["Indian citizen", "Resident of India"]
    }
}

# Generate FHIR bundle
bundle = map_to_fhir(sample_data)

# Pretty print and save
output_path = "test_compliance_output.json"
with open(output_path, "w") as f:
    json.dump(bundle, f, indent=2)

print(f"✓ Generated compliant FHIR bundle to {output_path}")
print(f"\nBundle structure:")
print(f"  - Bundle profile: {bundle.get('meta', {}).get('profile', ['N/A'])[0]}")
print(f"  - Type: {bundle.get('type')}")
print(f"  - Entries: {len(bundle.get('entry', []))}")

# Check compliance requirements
issues = []

# 1. Check Bundle profile
if 'profile' not in bundle.get('meta', {}):
    issues.append("❌ Bundle.meta.profile is missing")
elif 'InsurancePlanBundle' not in bundle['meta']['profile'][0]:
    issues.append(f"❌ Wrong Bundle profile: {bundle['meta']['profile'][0]}")
else:
    print("✓ Bundle.meta.profile is correct")

# 2. Check InsurancePlan type uses NDHM system
ip_entry = next((e for e in bundle['entry'] if e['resource'].get('resourceType') == 'InsurancePlan'), None)
if ip_entry:
    ip_type_coding = ip_entry['resource'].get('type', [{}])[0].get('coding', [{}])[0]
    if 'ndhm-insuranceplan-type' in ip_type_coding.get('system', ''):
        print("✓ InsurancePlan.type uses NDHM code system")
    else:
        issues.append(f"❌ InsurancePlan.type uses wrong system: {ip_type_coding.get('system')}")

# 3. Check coverage type uses SNOMED
coverage_entry = ip_entry['resource'].get('coverage', [{}])[0] if ip_entry else {}
coverage_type_coding = coverage_entry.get('type', {}).get('coding', [{}])[0]
if 'snomed' in coverage_type_coding.get('system', '').lower() or '2.16.840.1.113883.6.96' in coverage_type_coding.get('system', ''):
    print("✓ Coverage.type uses SNOMED codes")
else:
    issues.append(f"❌ Coverage.type uses wrong system: {coverage_type_coding.get('system')}")

# 4. Check references use urn:uuid format
all_refs_correct = True
for idx, entry in enumerate(bundle['entry']):
    resource = entry['resource']
    if resource.get('resourceType') == 'InsurancePlan':
        owned_by = resource.get('ownedBy', {}).get('reference', '')
        admin_by = resource.get('administeredBy', {}).get('reference', '')
        if not owned_by.startswith('urn:uuid:'):
            issues.append(f"❌ InsurancePlan.ownedBy uses wrong format: {owned_by}")
            all_refs_correct = False
        if not admin_by.startswith('urn:uuid:'):
            issues.append(f"❌ InsurancePlan.administeredBy uses wrong format: {admin_by}")
            all_refs_correct = False
    
    if resource.get('resourceType') == 'Coverage':
        sub = resource.get('subscriber', {}).get('reference', '')
        if not sub.startswith('urn:uuid:'):
            issues.append(f"❌ Coverage.subscriber uses wrong format: {sub}")
            all_refs_correct = False

if all_refs_correct:
    print("✓ All references use urn:uuid: format")

# 5. Check Claim-Exclusion extensions
if ip_entry:
    extensions = ip_entry['resource'].get('extension', [])
    claim_excl_exts = [e for e in extensions if 'Claim-Exclusion' in e.get('url', '')]
    if claim_excl_exts:
        print(f"✓ Claim-Exclusion extensions present ({len(claim_excl_exts)} exclusions)")
    else:
        issues.append("⚠ No Claim-Exclusion extensions found (optional if no exclusions)")

# 6. Check Organization identifier type
org_entry = next((e for e in bundle['entry'] if e['resource'].get('resourceType') == 'Organization'), None)
if org_entry:
    org_id = org_entry['resource'].get('identifier', [{}])[0]
    if org_id.get('type'):
        print("✓ Organization.identifier has type coding")
    else:
        issues.append("❌ Organization.identifier missing type coding")

print("\n" + "="*60)
if issues:
    print("Issues found:")
    for issue in issues:
        print(f"  {issue}")
else:
    print("✓ All compliance checks passed!")
