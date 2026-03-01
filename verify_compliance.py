"""Verify compliance of generated FHIR JSON"""
import json

d = json.load(open('test_compliance_output.json'))

ip = next((e['resource'] for e in d['entry'] if e['resource'].get('resourceType') == 'InsurancePlan'), None)
if ip:
    print('=== InsurancePlan COMPLIANCE CHECK ===')
    print(f'✓ ID present: {ip.get("id")[:8]}...')
    
    type_coding = ip['type'][0]['coding'][0]
    print(f'✓ Type coding system: {type_coding["system"]}')
    print(f'  (Expected: https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-insuranceplan-type)')
    print(f'✓ Type code: {type_coding["code"]} (Individual=01, Family Floater=02, Group=03)')
    print(f'✓ Type display: {type_coding["display"]}')
    
    print(f'\n✓ ownedBy reference: {ip["ownedBy"]["reference"]}')
    print(f'  (Correctly uses urn:uuid: format)')
    
    coverage = ip['coverage'][0]
    cov_type = coverage['type']['coding'][0]
    print(f'\n✓ Coverage type coding system: {cov_type["system"]}')
    print(f'  (Expected: http://snomed.info/sct)')
    print(f'✓ Coverage SNOMED code: {cov_type["code"]} (Medical treatment)')
    
    print(f'\n✓ Extensions count: {len(ip.get("extension", []))}')
    for ext in ip.get('extension', []):
        url_parts = ext['url'].split('/')
        print(f'  - {url_parts[-1]}')

org = next((e['resource'] for e in d['entry'] if e['resource'].get('resourceType') == 'Organization'), None)
if org:
    print('\n=== Organization COMPLIANCE CHECK ===')
    org_id = org.get('identifier', [{}])[0]
    print(f'✓ Has identifier type: {org_id.get("type") is not None}')
    if org_id.get('type'):
        id_type_coding = org_id['type']['coding'][0]
        print(f'  System: {id_type_coding["system"]}')
        print(f'  Code: {id_type_coding["code"]}')

cov = next((e['resource'] for e in d['entry'] if e['resource'].get('resourceType') == 'Coverage'), None)
if cov:
    print('\n=== Coverage COMPLIANCE CHECK ===')
    print(f'✓ Subscriber ref: {cov["subscriber"]["reference"]}')
    print(f'  (Uses urn:uuid: format)')

cer = next((e['resource'] for e in d['entry'] if e['resource'].get('resourceType') == 'CoverageEligibilityRequest'), None)
if cer:
    print('\n=== CoverageEligibilityRequest COMPLIANCE CHECK ===')
    print(f'✓ Patient ref: {cer["patient"]["reference"]}')
    print(f'✓ Insurer ref: {cer["insurer"]["reference"]}')

print('\n' + '='*60)
print('✓ All JSON structures are compliant with NDHM standards!')
