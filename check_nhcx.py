import json, sys
sys.stdout.reconfigure(encoding='utf-8')

d = json.load(open('test_result.json', 'r', encoding='utf-8'))

print("=" * 60)
print("NHCX COMPLETE COMPLIANCE REPORT")
print("=" * 60)

# Resources in Bundle
print(f"\nTotal resources in Bundle: {len(d['entry'])}")
for i, e in enumerate(d['entry']):
    r = e['resource']
    print(f"  {i+1}. {r['resourceType']} (id: {r['id'][:12]}...)")

ip = d['entry'][1]['resource']

# Check IRDAI Reg No
org = d['entry'][0]['resource']
print(f"\nIRDAI Reg No: {org['identifier'][0]['value']}")

# Check Coverage resource
cov_found = any(e['resource']['resourceType'] == 'Coverage' for e in d['entry'])
print(f"\nCoverage resource: {'YES' if cov_found else 'NO'}")
if cov_found:
    cov = [e['resource'] for e in d['entry'] if e['resource']['resourceType'] == 'Coverage'][0]
    print(f"  subscriber: {cov.get('subscriber', {})}")
    print(f"  payor: {cov.get('payor', [{}])[0].get('display', '')}")
    print(f"  class: {cov.get('class', [{}])[0].get('value', '')}")

# Check Patient/Group
pat_found = any(e['resource']['resourceType'] in ('Patient', 'Group') for e in d['entry'])
print(f"\nPatient/Group resource: {'YES' if pat_found else 'NO'}")

# Check Claim
claim_found = any(e['resource']['resourceType'] == 'Claim' for e in d['entry'])
print(f"Claim resource: {'YES' if claim_found else 'NO'}")

# Check ClaimResponse
cr_found = any(e['resource']['resourceType'] == 'ClaimResponse' for e in d['entry'])
print(f"ClaimResponse resource: {'YES' if cr_found else 'NO'}")

# Check CoverageEligibilityRequest
cer_found = any(e['resource']['resourceType'] == 'CoverageEligibilityRequest' for e in d['entry'])
print(f"CoverageEligibilityRequest: {'YES' if cer_found else 'NO'}")

# Coverage separation
covs = ip.get('coverage', [])
print(f"\nInsurancePlan.coverage entries: {len(covs)}")
for c in covs:
    print(f"  - {c['type']['text']}: {len(c['benefit'])} benefits")

# NHCX benefit system
bt_sys = set()
for c in covs:
    for b in c['benefit']:
        for cd in b['type']['coding']:
            bt_sys.add(cd['system'])
print(f"\nBenefit.type system: {bt_sys}")

# Limits summary
total = sum(len(c['benefit']) for c in covs)
with_lim = sum(1 for c in covs for b in c['benefit'] if b.get('limit'))
print(f"Benefits with limits: {with_lim}/{total}")

# IRDAI Exclusion codes
print(f"\nIRDAI Exclusion Codes:")
for ps in ip.get('plan', []):
    for sc in ps.get('specificCost', []):
        cat = sc.get('category', {}).get('coding', [{}])[0].get('code', '')
        if cat == 'exclusion':
            for be in sc.get('benefit', []):
                name = be['type']['text']
                codes = []
                for cost in be.get('cost', []):
                    for cd in cost.get('type', {}).get('coding', []):
                        if 'irdai' in cd.get('system', '').lower():
                            codes.append(cd['code'])
                irdai = codes[0] if codes else 'N/A'
                print(f"  {irdai}: {name}")

# generalCost
has_general = False
for ps in ip.get('plan', []):
    if 'generalCost' in ps:
        has_general = True
        for gc in ps['generalCost']:
            val = gc.get('value', {})
            print(f"\ngeneralCost (premium): {val.get('value', '')} {val.get('unit', '')}")
if not has_general:
    print(f"\ngeneralCost: Not present (no premium extracted)")

# Benefit names
print(f"\nBENEFIT LIST:")
for c in covs:
    print(f"\n  [{c['type']['text']}]")
    for i, b in enumerate(c['benefit']):
        name = b['type']['text']
        code = b['type']['coding'][0]['code']
        has_req = 'Y' if b.get('requirement') else 'N'
        has_lim = 'Y' if b.get('limit') else 'N'
        lim_info = ''
        if b.get('limit'):
            parts = []
            for l in b['limit']:
                v = l.get('value', {})
                ct = l.get('code', {}).get('text', '')
                parts.append(f"{v.get('value')} {v.get('unit')} ({ct})")
            lim_info = ' | '.join(parts)
        print(f"    {i+1:2d}. [{code}] [req:{has_req}] [lim:{has_lim}] {name}")
        if lim_info:
            print(f"        -> {lim_info}")
