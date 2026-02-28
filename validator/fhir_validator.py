"""
FHIR Validator for NHCX InsurancePlan bundles.

Two layers of validation:
1. FHIR R4 structural validation — using fhir.resources Pydantic models
   (ensures the JSON is valid FHIR R4)
2. NHCX profile validation — custom checks for NHCX-specific requirements
   (meta.profile, mandatory fields, coding systems, etc.)
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────
# NHCX profile URLs we expect
# ──────────────────────────────────────────────────
NHCX_INSURANCE_PLAN_PROFILE = "https://nrces.in/ndhm/fhir/r4/StructureDefinition/InsurancePlan"
NHCX_ORGANIZATION_PROFILE = "https://nrces.in/ndhm/fhir/r4/StructureDefinition/Organization"


def validate(bundle: dict) -> List[str]:
    """
    Validate a FHIR Bundle containing Organization + InsurancePlan.
    Returns a list of error strings. Empty list = valid.
    """
    errors = []

    # ── Bundle-level checks ──
    errors.extend(_validate_bundle_structure(bundle))

    # ── Per-resource validation ──
    for i, entry in enumerate(bundle.get("entry", [])):
        resource = entry.get("resource", {})
        res_type = resource.get("resourceType", "Unknown")

        # Check fullUrl
        if not entry.get("fullUrl"):
            errors.append(f"entry[{i}] ({res_type}): missing fullUrl")

        # FHIR R4 Pydantic model validation
        errors.extend(_validate_fhir_model(resource, i))

        # NHCX profile-specific checks
        if res_type == "Organization":
            errors.extend(_validate_nhcx_organization(resource, i))
        elif res_type == "InsurancePlan":
            errors.extend(_validate_nhcx_insurance_plan(resource, i))

    logger.info(f"Validation complete: {len(errors)} error(s) found")
    return errors


def _validate_bundle_structure(bundle: dict) -> List[str]:
    """Check top-level Bundle structure."""
    errors = []

    if bundle.get("resourceType") != "Bundle":
        errors.append("Bundle: resourceType must be 'Bundle'")

    if not bundle.get("id"):
        errors.append("Bundle: missing id")

    if bundle.get("type") not in ("collection", "transaction", "document"):
        errors.append(f"Bundle: type '{bundle.get('type')}' is not valid for NHCX (expected collection/transaction/document)")

    entries = bundle.get("entry", [])
    if not entries:
        errors.append("Bundle: no entries found")
        return errors

    # Must have at least Organization + InsurancePlan
    resource_types = [e.get("resource", {}).get("resourceType") for e in entries]
    if "Organization" not in resource_types:
        errors.append("Bundle: missing Organization resource")
    if "InsurancePlan" not in resource_types:
        errors.append("Bundle: missing InsurancePlan resource")

    return errors


def _validate_fhir_model(resource: dict, entry_index: int) -> List[str]:
    """
    Validate a resource against the fhir.resources Pydantic model.
    This catches structural FHIR R4 issues (wrong types, missing required fields).
    """
    errors = []
    res_type = resource.get("resourceType", "")

    try:
        if res_type == "Bundle":
            from fhir.resources.bundle import Bundle
            Bundle.model_validate(resource)
        elif res_type == "Organization":
            from fhir.resources.organization import Organization
            Organization.model_validate(resource)
        elif res_type == "InsurancePlan":
            from fhir.resources.insuranceplan import InsurancePlan
            InsurancePlan.model_validate(resource)
        else:
            errors.append(f"entry[{entry_index}]: unknown resourceType '{res_type}'")
    except Exception as e:
        # Extract readable validation errors from Pydantic
        err_msg = str(e)
        # Truncate very long error messages for readability
        if len(err_msg) > 500:
            err_msg = err_msg[:500] + "..."
        errors.append(f"entry[{entry_index}] ({res_type}) FHIR model validation failed: {err_msg}")

    return errors


def _validate_nhcx_organization(resource: dict, entry_index: int) -> List[str]:
    """NHCX-specific checks for Organization."""
    errors = []
    prefix = f"entry[{entry_index}] (Organization)"

    # meta.profile must reference NHCX profile
    profiles = resource.get("meta", {}).get("profile", [])
    if NHCX_ORGANIZATION_PROFILE not in profiles:
        errors.append(f"{prefix}: meta.profile must include {NHCX_ORGANIZATION_PROFILE}")

    # Must have a name
    if not resource.get("name"):
        errors.append(f"{prefix}: missing name")

    # Should have an identifier
    if not resource.get("identifier"):
        errors.append(f"{prefix}: missing identifier (recommended for NHCX)")

    return errors


def _validate_nhcx_insurance_plan(resource: dict, entry_index: int) -> List[str]:
    """NHCX-specific checks for InsurancePlan."""
    errors = []
    prefix = f"entry[{entry_index}] (InsurancePlan)"

    # meta.profile must reference NHCX profile
    profiles = resource.get("meta", {}).get("profile", [])
    if NHCX_INSURANCE_PLAN_PROFILE not in profiles:
        errors.append(f"{prefix}: meta.profile must include {NHCX_INSURANCE_PLAN_PROFILE}")

    # Must have status
    if resource.get("status") not in ("active", "draft", "retired"):
        errors.append(f"{prefix}: status must be active/draft/retired")

    # Must have name
    if not resource.get("name"):
        errors.append(f"{prefix}: missing name")

    # Must have ownedBy
    if not resource.get("ownedBy", {}).get("reference"):
        errors.append(f"{prefix}: missing ownedBy.reference to Organization")

    # Coverage checks
    coverages = resource.get("coverage", [])
    if not coverages:
        errors.append(f"{prefix}: missing coverage (at least one required)")
    else:
        for ci, cov in enumerate(coverages):
            # coverage.type should have coding
            cov_type = cov.get("type", {})
            if not cov_type.get("coding"):
                errors.append(f"{prefix}: coverage[{ci}].type should have coding (not just text)")

            benefits = cov.get("benefit", [])
            if not benefits:
                errors.append(f"{prefix}: coverage[{ci}] has no benefits")
            else:
                for bi, ben in enumerate(benefits):
                    if not ben.get("type"):
                        errors.append(f"{prefix}: coverage[{ci}].benefit[{bi}] missing type")

    # Plan section checks (optional but recommended)
    plans = resource.get("plan", [])
    if not plans:
        logger.warning(f"{prefix}: no plan section (exclusions/costs will be missing)")

    return errors


def format_validation_report(errors: List[str]) -> str:
    """Format errors into a human-readable report."""
    if not errors:
        return "Validation PASSED — no errors found."

    report = f"Validation FAILED — {len(errors)} error(s):\n"
    for i, err in enumerate(errors, 1):
        report += f"  {i}. {err}\n"
    return report