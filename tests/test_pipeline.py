"""
Tests for the NHCX Insurance Plan PDF-to-FHIR pipeline.

Run with:  python -m pytest tests/ -v
"""

import pytest
import json
import os
import sys

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mapper.nhcx_mapper import (
    map_to_fhir, _normalize_benefit_name, _build_benefit_type_coding,
    _build_limit, _build_coverage, _build_plan_section, _build_eligibility_extension
)
from validator.fhir_validator import validate, format_validation_report
from llm.openai_llm import merge_results, _dedupe_by_name, extract_relevant_sections, chunk_text


# ─────────────────────────────────────────────
# Test fixtures
# ─────────────────────────────────────────────

@pytest.fixture
def sample_extracted_data():
    """Realistic structured data as the LLM would return."""
    return {
        "organization": "Bajaj Allianz General Insurance",
        "plan_name": "Health Guard Gold",
        "plan_type": "individual",
        "coverage_type": "health",
        "sum_insured": "500000",
        "currency": "INR",
        "benefits": [
            {
                "name": "In-Patient Hospitalization",
                "category": "inpatient",
                "description": "Covers all inpatient hospitalization expenses",
                "limit_amount": "500000",
                "limit_unit": "amount",
                "sub_limits": [
                    {"name": "Room Rent", "limit_amount": "5000", "limit_unit": "per_day"},
                    {"name": "ICU Charges", "limit_amount": "10000", "limit_unit": "per_day"}
                ],
                "copay_percent": "10",
                "waiting_period_days": "30",
                "is_optional": False
            },
            {
                "name": "Day Care Treatment",
                "category": "daycare",
                "description": "Covers day care procedures",
                "limit_amount": "",
                "limit_unit": "no_limit",
                "sub_limits": [],
                "copay_percent": "",
                "waiting_period_days": "",
                "is_optional": False
            },
            {
                "name": "Ambulance Cover",
                "category": "ambulance",
                "description": "Road ambulance up to Rs 2000 per hospitalization",
                "limit_amount": "2000",
                "limit_unit": "amount",
                "sub_limits": [],
                "copay_percent": "",
                "waiting_period_days": "",
                "is_optional": False
            }
        ],
        "exclusions": [
            {
                "name": "Cosmetic Surgery",
                "description": "Any cosmetic or aesthetic treatment",
                "category": "permanent",
                "waiting_period_days": ""
            },
            {
                "name": "Pre-existing Diseases",
                "description": "48 months waiting period",
                "category": "time_bound",
                "waiting_period_days": "1460"
            }
        ],
        "eligibility": {
            "min_age": "18",
            "max_age": "65",
            "renewal_age": "lifelong",
            "pre_existing_waiting": "48",
            "conditions": ["Must be Indian resident"]
        },
        "network_type": "both",
        "portability": True
    }


@pytest.fixture
def minimal_data():
    """Minimum viable data."""
    return {
        "organization": "Test Insurer",
        "plan_name": "Test Plan",
        "plan_type": "individual",
        "coverage_type": "health",
        "sum_insured": "",
        "currency": "INR",
        "benefits": [
            {
                "name": "Basic Hospitalization",
                "category": "inpatient",
                "description": "Basic coverage",
                "limit_amount": "",
                "limit_unit": "",
                "sub_limits": [],
                "copay_percent": "",
                "waiting_period_days": "",
                "is_optional": False
            }
        ],
        "exclusions": [],
        "eligibility": {
            "min_age": "",
            "max_age": "",
            "renewal_age": "",
            "pre_existing_waiting": "",
            "conditions": []
        },
        "network_type": "",
        "portability": None
    }


@pytest.fixture
def empty_data():
    """Edge case: no meaningful data extracted."""
    return {
        "organization": "",
        "plan_name": "",
        "plan_type": "",
        "coverage_type": "",
        "sum_insured": "",
        "currency": "INR",
        "benefits": [],
        "exclusions": [],
        "eligibility": {"min_age": "", "max_age": "", "renewal_age": "", "pre_existing_waiting": "", "conditions": []},
        "network_type": "",
        "portability": None
    }


# ─────────────────────────────────────────────
# Mapper tests
# ─────────────────────────────────────────────

class TestMapper:

    def test_map_to_fhir_produces_valid_bundle(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        assert bundle["resourceType"] == "Bundle"
        assert bundle["type"] == "collection"
        assert len(bundle["entry"]) == 2
        assert bundle["id"]
        assert bundle["meta"]["lastUpdated"]

    def test_bundle_has_fullurl(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        for entry in bundle["entry"]:
            assert entry["fullUrl"].startswith("urn:uuid:")

    def test_organization_resource(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        org = bundle["entry"][0]["resource"]
        assert org["resourceType"] == "Organization"
        assert org["name"] == "Bajaj Allianz General Insurance"
        assert org["meta"]["profile"][0].endswith("Organization")
        assert org["identifier"][0]["value"]
        assert org["active"] is True

    def test_insurance_plan_resource(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        assert plan["resourceType"] == "InsurancePlan"
        assert plan["name"] == "Health Guard Gold"
        assert plan["status"] == "active"
        assert plan["meta"]["profile"][0].endswith("InsurancePlan")
        assert plan["ownedBy"]["reference"].startswith("Organization/")

    def test_benefits_mapped(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        benefits = plan["coverage"][0]["benefit"]
        assert len(benefits) == 3

    def test_benefit_has_type_coding(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        benefit = plan["coverage"][0]["benefit"][0]
        assert "coding" in benefit["type"]
        assert benefit["type"]["coding"][0]["code"]
        assert benefit["type"]["coding"][0]["system"]

    def test_benefit_limit_present(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        benefit = plan["coverage"][0]["benefit"][0]  # inpatient with limit
        assert "limit" in benefit
        assert benefit["limit"][0]["value"]["value"] == 500000.0
        assert benefit["limit"][0]["value"]["code"] == "INR"

    def test_sublimits_present(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        benefit = plan["coverage"][0]["benefit"][0]
        # Main limit + 2 sub-limits = 3 total
        assert len(benefit["limit"]) == 3

    def test_exclusions_in_plan_section(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        assert "plan" in plan
        general_costs = plan["plan"][0]["generalCost"]
        assert len(general_costs) == 2
        assert general_costs[0]["type"]["text"] == "Cosmetic Surgery"

    def test_copay_in_specific_cost(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        specific_costs = plan["plan"][0]["specificCost"]
        assert len(specific_costs) >= 1

    def test_eligibility_extensions(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        assert "extension" in plan
        ext_urls = [e["url"] for e in plan["extension"]]
        assert any("MinAge" in u for u in ext_urls)
        assert any("MaxAge" in u for u in ext_urls)

    def test_minimal_data_produces_valid_bundle(self, minimal_data):
        bundle = map_to_fhir(minimal_data)
        assert bundle["resourceType"] == "Bundle"
        assert len(bundle["entry"]) == 2

    def test_empty_data_produces_bundle(self, empty_data):
        bundle = map_to_fhir(empty_data)
        assert bundle["resourceType"] == "Bundle"
        plan = bundle["entry"][1]["resource"]
        assert plan["name"] == ""  # empty but present

    def test_normalize_benefit_name(self):
        # These depend on mapping.yaml being loaded
        assert _normalize_benefit_name("opd consultation") == "OPD Expenses"
        assert _normalize_benefit_name("daycare procedures") == "Day Care Treatment"
        assert _normalize_benefit_name("unknown benefit xyz") == "unknown benefit xyz"

    def test_build_benefit_type_coding_known(self):
        result = _build_benefit_type_coding("inpatient")
        assert result["coding"][0]["code"] == "medical"

    def test_build_benefit_type_coding_unknown(self):
        result = _build_benefit_type_coding("nonexistent_category")
        assert result["coding"][0]["code"] == "benefit"  # falls back to "other"


# ─────────────────────────────────────────────
# FHIR Model Validation tests
# ─────────────────────────────────────────────

class TestFHIRModelValidation:

    def test_organization_passes_fhir_model(self, sample_extracted_data):
        from fhir.resources.organization import Organization
        bundle = map_to_fhir(sample_extracted_data)
        org = bundle["entry"][0]["resource"]
        result = Organization.model_validate(org)
        assert result.name == "Bajaj Allianz General Insurance"

    def test_insurance_plan_passes_fhir_model(self, sample_extracted_data):
        from fhir.resources.insuranceplan import InsurancePlan
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        result = InsurancePlan.model_validate(plan)
        assert result.name == "Health Guard Gold"

    def test_minimal_passes_fhir_model(self, minimal_data):
        from fhir.resources.insuranceplan import InsurancePlan
        bundle = map_to_fhir(minimal_data)
        plan = bundle["entry"][1]["resource"]
        InsurancePlan.model_validate(plan)  # should not raise


# ─────────────────────────────────────────────
# Validator tests
# ─────────────────────────────────────────────

class TestValidator:

    def test_valid_bundle_passes(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        errors = validate(bundle)
        assert errors == []

    def test_missing_plan_name_detected(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        bundle["entry"][1]["resource"]["name"] = ""
        errors = validate(bundle)
        assert any("missing name" in e for e in errors)

    def test_missing_fullurl_detected(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        del bundle["entry"][0]["fullUrl"]
        errors = validate(bundle)
        assert any("missing fullUrl" in e for e in errors)

    def test_wrong_bundle_type_detected(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        bundle["type"] = "searchset"
        errors = validate(bundle)
        assert any("not valid for NHCX" in e for e in errors)

    def test_missing_profile_detected(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        bundle["entry"][1]["resource"]["meta"]["profile"] = []
        errors = validate(bundle)
        assert any("meta.profile" in e for e in errors)

    def test_format_report_passed(self):
        report = format_validation_report([])
        assert "PASSED" in report

    def test_format_report_failed(self):
        report = format_validation_report(["error1", "error2"])
        assert "FAILED" in report
        assert "2 error" in report


# ─────────────────────────────────────────────
# LLM merge / utility tests
# ─────────────────────────────────────────────

class TestLLMUtils:

    def test_merge_results_single(self):
        results = [{
            "organization": "Test Corp",
            "plan_name": "Plan A",
            "plan_type": "individual",
            "coverage_type": "health",
            "sum_insured": "500000",
            "currency": "INR",
            "benefits": [{"name": "Benefit 1", "category": "inpatient", "description": "", "limit_amount": "", "limit_unit": "", "sub_limits": [], "copay_percent": "", "waiting_period_days": "", "is_optional": False}],
            "exclusions": [],
            "eligibility": {"min_age": "18", "max_age": "65", "renewal_age": "", "pre_existing_waiting": "", "conditions": []},
            "network_type": "",
            "portability": None
        }]
        final = merge_results(results)
        assert final["organization"] == "Test Corp"
        assert len(final["benefits"]) == 1

    def test_merge_results_deduplicates_benefits(self):
        results = [
            {"benefits": [{"name": "Inpatient", "category": "inpatient"}]},
            {"benefits": [{"name": "Inpatient", "category": "inpatient"}, {"name": "OPD", "category": "outpatient"}]}
        ]
        final = merge_results(results)
        assert len(final["benefits"]) == 2  # "Inpatient" deduplicated

    def test_merge_results_backward_compat_string_benefits(self):
        results = [{"benefits": ["Day Care", "Ambulance"]}]
        final = merge_results(results)
        assert len(final["benefits"]) == 2
        assert final["benefits"][0]["name"] == "Day Care"
        assert final["benefits"][0]["category"] == "other"

    def test_merge_results_eligibility_merge(self):
        results = [
            {"eligibility": {"min_age": "18", "max_age": "", "renewal_age": "", "pre_existing_waiting": "", "conditions": []}},
            {"eligibility": {"min_age": "", "max_age": "65", "renewal_age": "99", "pre_existing_waiting": "48", "conditions": ["Condition A"]}}
        ]
        final = merge_results(results)
        assert final["eligibility"]["min_age"] == "18"
        assert final["eligibility"]["max_age"] == "65"
        assert final["eligibility"]["pre_existing_waiting"] == "48"
        assert "Condition A" in final["eligibility"]["conditions"]

    def test_dedupe_by_name(self):
        items = [
            {"name": "Alpha", "value": 1},
            {"name": "Beta", "value": 2},
            {"name": "alpha", "value": 3},  # duplicate (case-insensitive)
        ]
        result = _dedupe_by_name(items)
        assert len(result) == 2

    def test_extract_relevant_sections_keeps_keywords(self):
        text = "This line has benefit info\nThis is random\nRoom rent is 5000\n"
        result = extract_relevant_sections(text)
        # With less than 50 relevant lines, returns full text
        assert "random" in result

    def test_chunk_text(self):
        text = "a" * 25000
        chunks = chunk_text(text)
        assert len(chunks) == 3  # 12000 + 12000 + 1000


# ─────────────────────────────────────────────
# PDF extractor tests (no actual PDF needed for unit test)
# ─────────────────────────────────────────────

class TestPDFExtractor:

    def test_import_works(self):
        from extractor.pdf import extract_text
        assert callable(extract_text)
