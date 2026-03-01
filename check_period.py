"""Check if period is in InsurancePlan"""
import json

d = json.load(open('test_compliance_output.json'))
ip = next((e['resource'] for e in d['entry'] if e['resource'].get('resourceType') == 'InsurancePlan'), None)

if ip:
    print('=== InsurancePlan Period Verification ===')
    if 'period' in ip:
        print(f"✓ Period is PRESENT")
        print(f"  Start: {ip['period'].get('start')}")
        print(f"  End:   {ip['period'].get('end')}")
    else:
        print('❌ Period is MISSING')
        print('Available fields:', list(ip.keys()))
else:
    print('❌ InsurancePlan not found')
