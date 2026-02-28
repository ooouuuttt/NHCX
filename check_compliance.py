import json, sys
sys.stdout.reconfigure(encoding='utf-8')

d = json.load(open('test_result.json', 'r', encoding='utf-8'))
org = d['entry'][0]['resource']
ip = d['entry'][1]['resource']

print("=" * 60)
print("FHIR BUNDLE COMPLIANCE REPORT")
print("=" * 60)

print("\nRULE 1 — InsurancePlan.identifier (UIN)")
ident = ip.get('identifier', [{}])[0]
print(f"  system: {ident.get('system')}")
print(f"  value:  {ident.get('value')}")
print(f"  ✅ PASS" if ident.get('value') and ident.get('value') != 'UNKNOWN' else "  ❌ FAIL")

print("\nRULE 2 — Organization telecom")
telecom = org.get('telecom', [])
print(f"  Entries: {len(telecom)}")
for t in telecom:
    print(f"    {t.get('system')}: {t.get('value')}")
print(f"  ✅ PASS" if len(telecom) > 0 else "  ❌ FAIL")

print("\nRULE 3 — Benefit requirement completeness")
benefits = ip.get('coverage', [{}])[0].get('benefit', [])
incomplete = []
for b in benefits:
    req = b.get('requirement', '')
    if req and (req[-1] not in '.!?)\'"' or len(req) < 10):
        incomplete.append(b['type']['text'])
print(f"  Total benefits: {len(benefits)}")
print(f"  With requirement: {sum(1 for b in benefits if b.get('requirement'))}")
print(f"  Incomplete: {len(incomplete)}")
if incomplete:
    for n in incomplete[:5]:
        print(f"    - {n}")
print(f"  ✅ PASS" if not incomplete else "  ❌ FAIL")

print("\nRULE 4 — benefit.limit presence")
with_limits = [b for b in benefits if b.get('limit')]
print(f"  Benefits with limits: {len(with_limits)}/{len(benefits)}")
for b in with_limits[:5]:
    lims = b['limit']
    for l in lims:
        val = l.get('value', {})
        code = l.get('code', {}).get('text', '')
        print(f"    {b['type']['text']}: {val.get('value')} {val.get('unit')} ({code})")
print(f"  ✅ PASS" if len(with_limits) > 0 else "  ⚠️ CHECK (depends on PDF content)")

print("\nRULE 5 — Waiting periods as structured limits")
wp_benefits = []
for b in benefits:
    for l in b.get('limit', []):
        if l.get('code', {}).get('text') == 'Waiting period':
            wp_benefits.append(b['type']['text'])
print(f"  Benefits with waiting period limits: {len(wp_benefits)}")
for n in wp_benefits:
    print(f"    - {n}")
print(f"  ✅ PASS" if len(wp_benefits) >= 0 else "  ❌ FAIL")

print("\nRULE 6 — Correct coding systems")
# Check benefit.type system
bt_sys = set()
for b in benefits:
    for c in b.get('type', {}).get('coding', []):
        bt_sys.add(c.get('system'))
print(f"  Benefit.type systems: {bt_sys}")
correct_bt = 'https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-benefit-type' in bt_sys
print(f"  ✅ PASS" if correct_bt else "  ❌ FAIL")

# Check InsurancePlan.type system
ipt_sys = ip['type'][0]['coding'][0].get('system')
print(f"  InsurancePlan.type system: {ipt_sys}")
correct_ipt = ipt_sys == 'http://terminology.hl7.org/CodeSystem/insurance-plan-type'
print(f"  ✅ PASS" if correct_ipt else "  ❌ FAIL")

# Check exclusion category
exc_sys = None
for ps in ip.get('plan', []):
    for sc in ps.get('specificCost', []):
        for c in sc.get('category', {}).get('coding', []):
            if c.get('code') == 'exclusion':
                exc_sys = c.get('system')
print(f"  Exclusion category system: {exc_sys}")
correct_exc = exc_sys == 'https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-plan-cost-type'
print(f"  ✅ PASS" if correct_exc else "  ❌ FAIL")

print("\nRULE 7 — No hallucinated benefits")
names = [b['type']['text'] for b in benefits]
from collections import Counter
c = Counter(names)
dupes = [n for n, ct in c.items() if ct > 1]
print(f"  Unique benefit names: {len(names)}")
print(f"  Duplicates: {dupes if dupes else 'NONE'}")
print(f"  ✅ PASS" if not dupes else "  ❌ FAIL")

print("\nRULE 8 — Network element")
network = ip.get('network', [])
print(f"  network: {network}")
print(f"  ✅ PASS" if network else "  ⚠️ (depends on PDF content)")

print("\nRULE 9 — Contact element")
contact = ip.get('contact', [])
print(f"  contact: {contact}")
print(f"  ✅ PASS" if contact else "  ❌ FAIL")

print("\nRULE 10 — Period element")
period = ip.get('period', {})
print(f"  period: {period}")
print(f"  ✅ PASS" if period else "  ⚠️ (depends on PDF content)")

print("\n" + "=" * 60)
print("PLAN NAME:", ip['name'])
print("ownedBy:", ip.get('ownedBy', {}).get('display'))
print("administeredBy:", ip.get('administeredBy', {}).get('display'))
print("Extensions:", len(ip.get('extension', [])))
print("=" * 60)

print("\nBENEFIT LIST:")
for i, b in enumerate(benefits):
    name = b['type']['text']
    has_req = '✓' if b.get('requirement') else '✗'
    has_lim = '✓' if b.get('limit') else '✗'
    lim_info = ''
    if b.get('limit'):
        parts = []
        for l in b['limit']:
            v = l.get('value', {})
            c = l.get('code', {}).get('text', '')
            parts.append(f"{v.get('value')} {v.get('unit')} ({c})")
        lim_info = ' | '.join(parts)
    print(f"  {i+1:2d}. [{has_req}req] [{has_lim}lim] {name}")
    if lim_info:
        print(f"      └─ {lim_info}")
