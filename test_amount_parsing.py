"""Test INR amount parsing improvements"""
from mapper.nhcx_mapper import _parse_number

test_cases = [
    # (input, expected_output, description)
    ("500000", 500000, "Plain number"),
    ("5,00,000", 500000, "Indian format with commas"),
    ("₹500000", 500000, "Rupee symbol"),
    ("Rs. 500000", 500000, "Rs. prefix"),
    ("Rs 500000", 500000, "Rs prefix without dot"),
    ("5 Lakh", 500000, "5 Lakh"),
    ("50 Lakh", 5000000, "50 Lakh"),
    ("1 Crore", 10000000, "1 Crore"),
    ("10 Crore", 100000000, "10 Crore"),
    ("5,00,000 Lakh", 50000000000, "Indian format Lakh"),
    ("50%", 50, "Percentage"),
    ("100%", 100, "100 Percentage"),
    ("  500000  ", 500000, "With spaces"),
    ("0", None, "Zero (invalid)"),
    ("", None, "Empty string"),
    (None, None, "None"),
    ("N/A", None, "N/A placeholder"),
    ("not mentioned", None, "Text placeholder"),
]

print("=== INR Amount Parsing Test Suite ===\n")
passed = 0
failed = 0

for input_val, expected, description in test_cases:
    result = _parse_number(input_val)
    status = "✓" if result == expected else "❌"
    
    if result == expected:
        passed += 1
        print(f"{status} {description}")
        if expected is not None:
            print(f"   Input: '{input_val}' → Output: {result:,.0f}" if result else f"   Input: '{input_val}' → Output: {result}")
    else:
        failed += 1
        print(f"{status} {description} - FAILED")
        print(f"   Input: '{input_val}'")
        print(f"   Expected: {expected}")
        print(f"   Got: {result}")
    print()

print("="*60)
print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")
if failed == 0:
    print("✓ All amount parsing tests PASSED!")
else:
    print(f"❌ {failed} test(s) failed")
