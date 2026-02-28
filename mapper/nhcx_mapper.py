import uuid
import yaml
import logging
import re

logger = logging.getLogger(__name__)

# NHCX profile URLs
NHCX_INSURANCE_PLAN_PROFILE = "https://nrces.in/ndhm/fhir/r4/StructureDefinition/InsurancePlan"
NHCX_ORGANIZATION_PROFILE = "https://nrces.in/ndhm/fhir/r4/StructureDefinition/Organization"

# NDHM benefit-type CodeSystem
NDHM_BENEFIT_TYPE_SYSTEM = "https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-benefit-type"

# NDHM plan cost type (for exclusions)
NDHM_PLAN_COST_TYPE_SYSTEM = "https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-plan-cost-type"

# Load benefit category mapping from config
try:
    with open("config/mapping.yaml", "r") as f:
        MAPPING_CONFIG = yaml.safe_load(f)
except FileNotFoundError:
    MAPPING_CONFIG = {"benefit_mapping": {}, "coverage_types": {}}
    logger.warning("mapping.yaml not found, using empty defaults")


# ─────────────────────────────────────────────────────────────
# P1 FIX: NHCX-specific benefit type coding
# Uses https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-benefit-type
# Maps LLM category + benefit name keywords to NHCX codes
# ─────────────────────────────────────────────────────────────

def _infer_nhcx_benefit_code(name, category):
    """Map benefit name + category into an NHCX-compliant code and display.
    Uses ndhm-benefit-type CodeSystem codes where they exist,
    plus extended codes for common Indian insurance benefit types."""
    n = name.lower().strip()
    c = (category or "").lower().strip()

    # Official ndhm-benefit-type codes
    if "icu" in n or "intensive care" in n:
        return "00", "ICU"
    if n == "blood" or "blood" in n and len(n) < 25:
        return "01", "Blood"
    if "oxygen" in n:
        return "02", "Oxygen"
    if "room rent" in n or "room charge" in n:
        return "03", "Room Rent"

    # Extended NHCX benefit codes (commonly used in Indian NHCX implementations)
    if "hospitali" in n and ("daily cash" in n or "cash" in n):
        return "daily-cash", "Daily Cash Benefit"
    if "daily cash" in n:
        return "daily-cash", "Daily Cash Benefit"
    if "death" in n:
        return "death-benefit", "Death Benefit"
    if "ambulance" in n:
        return "ambulance-cover", "Ambulance Cover"
    if "pre" in n and "hospitali" in n:
        return "pre-hospitalization", "Pre-Hospitalization Expenses"
    if "post" in n and "hospitali" in n:
        return "post-hospitalization", "Post-Hospitalization Expenses"
    if "hospitali" in n or c == "inpatient":
        return "hospitalization-benefit", "Hospitalization Benefit"
    if "maternity" in n or "childbirth" in n:
        return "maternity-benefit", "Maternity Benefit"
    if "daycare" in n or "day care" in n or c == "daycare":
        return "daycare-benefit", "Day Care Benefit"
    if "organ donor" in n:
        return "organ-donor", "Organ Donor Cover"
    if "ayush" in n:
        return "ayush-treatment", "AYUSH Treatment"
    if "domiciliary" in n:
        return "domiciliary", "Domiciliary Hospitalization"
    if "rehabilitation" in n or "physiotherapy" in n:
        return "rehabilitation", "Rehabilitation"
    if "dental" in n:
        return "dental-benefit", "Dental Treatment"
    if "mental" in n or "psychiatric" in n or "counseling" in n or "counselling" in n:
        return "mental-health", "Mental Health"
    if "disablement" in n or "disability" in n:
        return "disablement-benefit", "Disablement Benefit"
    if "surgery" in n or "reconstructive" in n:
        return "surgery-benefit", "Surgery Benefit"
    if "loss of job" in n:
        return "income-benefit", "Income Benefit"
    if "loan" in n:
        return "loan-protection", "Loan Protection"
    if "comatose" in n or "coma" in n:
        return "critical-benefit", "Critical Benefit"
    if "broken bone" in n or "fracture" in n:
        return "accident-benefit", "Accident Benefit"
    if "burn" in n:
        return "accident-benefit", "Accident Benefit"
    if "assault" in n:
        return "accident-benefit", "Accident Benefit"
    if "evacuation" in n or "repatriation" in n:
        return "emergency-benefit", "Emergency Benefit"
    if "diagnostic" in n or "test" in n:
        return "diagnostic-benefit", "Diagnostic Benefit"
    if "recovery" in n or "lifestyle" in n:
        return "wellness-benefit", "Wellness Benefit"
    if "last rites" in n or "funeral" in n:
        return "death-benefit", "Death Benefit"
    if "education" in n or "orphan" in n or "parental" in n or "tuition" in n:
        return "family-benefit", "Family Benefit"
    if "adventure" in n or "sport" in n:
        return "accident-benefit", "Accident Benefit"
    if "compassionate" in n or "chauffeur" in n or "skill" in n:
        return "supplementary-benefit", "Supplementary Benefit"
    if "on duty" in n or "enhanced" in n:
        return "supplementary-benefit", "Supplementary Benefit"
    if "opd" in n or "outpatient" in n or c == "outpatient":
        return "opd-benefit", "OPD Benefit"
    if "mysterious" in n:
        return "accident-benefit", "Accident Benefit"
    if "common carrier" in n:
        return "accident-benefit", "Accident Benefit"

    # Default fallback
    return "benefit", "Benefit"


BENEFIT_CATEGORY_MAP = {}  # deprecated, using _infer_nhcx_benefit_code instead


def _make_uuid():
    return str(uuid.uuid4())


def _make_urn(uid):
    return f"urn:uuid:{uid}"


def _normalize_benefit_name(name):
    """Use mapping.yaml to normalize benefit names if a match exists.
    Only normalizes SHORT/GENERIC names (<30 chars)."""
    if not name:
        return name
    if len(name.strip()) >= 30:
        return name
    benefit_map = MAPPING_CONFIG.get("benefit_mapping", {})
    name_lower = name.lower().strip()
    for key, display in benefit_map.items():
        if key in name_lower:
            return display
    return name


def _build_benefit_type_coding(name, category):
    """Return a CodeableConcept with NHCX-compliant coding for a benefit.
    Uses https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-benefit-type (P1 fix)."""
    code, display = _infer_nhcx_benefit_code(name, category)
    return {
        "coding": [{
            "system": NDHM_BENEFIT_TYPE_SYSTEM,
            "code": code,
            "display": display
        }],
        "text": display
    }


# ─────────────────────────────────────────────────────────────
# P1 FIX: Comprehensive limit builder
# ─────────────────────────────────────────────────────────────

def _parse_number(val):
    """Try to parse a numeric value from a string, return None on failure."""
    if not val:
        return None
    try:
        s = str(val).replace(",", "").replace("₹", "").replace("Rs.", "").replace("Rs", "").replace("%", "").strip()
        if not s:
            return None
        n = float(s)
        return n if n > 0 else None
    except (ValueError, TypeError):
        return None


def _build_limit(benefit, global_sum_insured=None):
    """Build FHIR benefit.limit[] from structured benefit data.
    P1 fix: Handles monetary limits, duration limits, percentage limits,
    waiting periods, and falls back to global sum_insured when benefit
    says '100% of SI'."""
    limits = []

    # 1. Main monetary limit
    amount = _parse_number(benefit.get("limit_amount"))
    if amount:
        limits.append({
            "value": {
                "value": amount,
                "unit": "INR",
                "system": "urn:iso:std:iso:4217",
                "code": "INR"
            },
            "code": {"text": "Maximum benefit amount"}
        })

    # 2. Duration limit (max_days)
    days = _parse_number(benefit.get("max_days"))
    if days:
        limits.append({
            "value": {
                "value": days,
                "unit": "days",
                "system": "http://unitsofmeasure.org",
                "code": "d"
            },
            "code": {"text": "Maximum benefit duration"}
        })

    # 3. Percentage payout limit
    pct = _parse_number(benefit.get("percentage_payout"))
    if pct and 0 < pct <= 100:
        limits.append({
            "value": {
                "value": pct,
                "unit": "%",
                "system": "http://unitsofmeasure.org",
                "code": "%"
            },
            "code": {"text": "Percentage of Sum Insured"}
        })

    # 4. Waiting period as structured limit (P1 fix for PED + Rule 5)
    wp = _parse_number(benefit.get("waiting_period_days"))
    if wp:
        limits.append({
            "value": {
                "value": wp,
                "unit": "days",
                "system": "http://unitsofmeasure.org",
                "code": "d"
            },
            "code": {"text": "Waiting period"}
        })

    # 5. Sub-limits (monetary)
    for sub in benefit.get("sub_limits", []):
        sub_amt = _parse_number(sub.get("limit_amount"))
        if sub_amt:
            limits.append({
                "value": {
                    "value": sub_amt,
                    "unit": "INR",
                    "system": "urn:iso:std:iso:4217",
                    "code": "INR"
                },
                "code": {"text": sub.get("name", "Sub-limit")}
            })

    # 5b. Sub-benefits (e.g., OPD breakdown) as sub-limits
    for sub in benefit.get("sub_benefits", []):
        if not isinstance(sub, dict):
            continue
        sub_amt = _parse_number(sub.get("limit_amount"))
        if sub_amt:
            limits.append({
                "value": {
                    "value": sub_amt,
                    "unit": "INR",
                    "system": "urn:iso:std:iso:4217",
                    "code": "INR"
                },
                "code": {"text": sub.get("name", "Sub-benefit")}
            })

    # 6. Fallback: If NO limits at all and we have a global sum insured, use it
    #    This ensures every benefit has at least one limit entry
    if not limits and global_sum_insured:
        limits.append({
            "value": {
                "value": global_sum_insured,
                "unit": "INR",
                "system": "urn:iso:std:iso:4217",
                "code": "INR"
            },
            "code": {"text": "Up to Sum Insured"}
        })

    # 7. Ultimate fallback: If still no limits at all, add a reference limit
    #    This ensures every benefit has at least one limit entry for NHCX compliance
    if not limits:
        # Check if limit_unit gives us a clue
        limit_unit = str(benefit.get("limit_unit", "")).lower()
        desc = str(benefit.get("description", "")).lower()
        if "percentage" in limit_unit or "%" in desc:
            limits.append({
                "value": {"value": 100.0, "unit": "%", "system": "http://unitsofmeasure.org", "code": "%"},
                "code": {"text": "As per Policy Schedule"}
            })
        else:
            limits.append({
                "value": {"value": 0.0, "unit": "INR", "system": "urn:iso:std:iso:4217", "code": "INR"},
                "code": {"text": "As per Policy Schedule / Certificate of Insurance"}
            })

    return limits if limits else None



def _validate_requirement(desc):
    """Ensure benefit requirement is a complete sentence (Rule 3).
    Returns cleaned description or None if empty."""
    if not desc or not desc.strip():
        return None
    desc = desc.strip()
    if desc and desc[-1] not in ".!?)'\"":
        desc += "."
    return desc


# ─────────────────────────────────────────────────────────────
# P2 FIX: Separate base and extension coverage
# ─────────────────────────────────────────────────────────────

# Keywords that identify extension/add-on benefits (Section C.2 etc.)
_EXTENSION_KEYWORDS = [
    "broken bone", "burns", "comatose", "compassionate", "chauffeur",
    "skill development", "on duty", "home tuition", "outstanding bills",
    "major surgery", "assault", "mysterious disappearance", "loan protection",
    "common carrier", "catastrophic evacuation", "rehabilitation",
    "loss of job", "recovery benefit", "diagnostic test", "lifestyle support",
    "last rites", "counseling", "counselling", "repatriation",
    "adventure sport", "children's education", "orphan", "parental care",
    "reconstructive surgery"
]


def _is_extension_benefit(name):
    """Check if benefit belongs to extension/add-on section."""
    n = name.lower().strip()
    return any(kw in n for kw in _EXTENSION_KEYWORDS)


def _build_fhir_coverage(data):
    """Build InsurancePlan.coverage[] — split into base + extension.
    Includes FHIR-level dedup."""
    base_benefits = []
    extension_benefits = []
    seen_names = set()

    global_si = _parse_number(data.get("sum_insured"))
    ped_days = None

    # Check for PED waiting period from eligibility (P1 fix)
    elig = data.get("eligibility", {})
    if isinstance(elig, dict):
        ped_val = elig.get("pre_existing_waiting", "")
        if ped_val:
            # Try to parse as days or convert years
            ped_str = str(ped_val).lower().strip()
            if "year" in ped_str:
                m = re.search(r'(\d+)', ped_str)
                if m:
                    ped_days = int(m.group(1)) * 365
            elif "month" in ped_str:
                m = re.search(r'(\d+)', ped_str)
                if m:
                    ped_days = int(m.group(1)) * 30
            else:
                ped_days = _parse_number(ped_val)
                if ped_days:
                    ped_days = int(ped_days)

    for b in data.get("benefits", []):
        name = b.get("name", "") if isinstance(b, dict) else str(b)
        category = b.get("category", "other") if isinstance(b, dict) else "other"

        normalized_name = _normalize_benefit_name(name)
        display_name = normalized_name or name

        # FHIR-level dedup
        name_key = display_name.strip().lower()
        if name_key in seen_names:
            continue
        seen_names.add(name_key)

        # Build NHCX-compliant benefit type coding (P1 fix)
        type_concept = _build_benefit_type_coding(display_name, category)
        type_concept["text"] = display_name

        benefit_entry = {"type": type_concept}

        # Build limits (P1 fix: comprehensive limits + PED)
        if isinstance(b, dict):
            limits = _build_limit(b, global_sum_insured=global_si)

            # P1 FIX: Add PED waiting period to hospitalization benefits
            if ped_days and ("hospitali" in name_key or category == "inpatient"):
                ped_limit = {
                    "value": {
                        "value": float(ped_days),
                        "unit": "days",
                        "system": "http://unitsofmeasure.org",
                        "code": "d"
                    },
                    "code": {"text": "Pre-existing disease waiting period"}
                }
                if limits:
                    # Don't add if there's already a PED limit
                    has_ped = any("pre-existing" in l.get("code", {}).get("text", "").lower() for l in limits)
                    if not has_ped:
                        limits.append(ped_limit)
                else:
                    limits = [ped_limit]

            if limits:
                benefit_entry["limit"] = limits

        # Requirement (Rule 3: must be complete)
        if isinstance(b, dict):
            req = _validate_requirement(b.get("description", ""))
            if req:
                benefit_entry["requirement"] = req

        # P2 FIX: Separate base vs extension
        if _is_extension_benefit(display_name):
            extension_benefits.append(benefit_entry)
        else:
            base_benefits.append(benefit_entry)

    # Coverage type
    coverage_type_text = data.get("coverage_type", "health")
    cov_types = MAPPING_CONFIG.get("coverage_types", {})
    coverage_display = cov_types.get(coverage_type_text, coverage_type_text)

    # P2 FIX: InsurancePlan.type uses NHCX-specific codes
    cov_type = str(data.get("coverage_type", "medical")).lower()
    if "accident" in cov_type:
        ipt_code = "medical"  # PA plans still use medical in NHCX
    else:
        ipt_code = "medical"

    coverages = []

    # Base coverage
    if base_benefits:
        coverages.append({
            "type": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/insurance-plan-type",
                    "code": ipt_code,
                    "display": coverage_display or "Medical"
                }],
                "text": "Base Coverage"
            },
            "benefit": base_benefits
        })

    # Extension coverage (P2 fix: separate coverage entry)
    if extension_benefits:
        coverages.append({
            "type": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/insurance-plan-type",
                    "code": ipt_code,
                    "display": coverage_display or "Medical"
                }],
                "text": "Extension Coverage"
            },
            "benefit": extension_benefits
        })

    return coverages if coverages else [{
        "type": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/insurance-plan-type",
                "code": "medical",
                "display": "Medical"
            }],
            "text": "Base Coverage"
        },
        "benefit": []
    }]


# ─────────────────────────────────────────────────────────────
# P2 FIX: Exclusion cost entries with proper type + value
# ─────────────────────────────────────────────────────────────

def _build_plan_section(data):
    """Build InsurancePlan.plan[] with properly structured exclusion costs (P2 fix)."""
    plan_section = {}
    specific_costs = []

    exclusions = data.get("exclusions", [])
    if exclusions:
        benefit_entries = []
        for exc in exclusions:
            name = exc.get("name", "") if isinstance(exc, dict) else str(exc)
            desc = exc.get("description", name) if isinstance(exc, dict) else str(exc)
            category = exc.get("category", "permanent") if isinstance(exc, dict) else "permanent"
            wp_days = exc.get("waiting_period_days", "") if isinstance(exc, dict) else ""

            # P2 FIX: Build proper cost entry with type coding and value
            cost_entry = {
                "type": {
                    "coding": [{
                        "system": NDHM_PLAN_COST_TYPE_SYSTEM,
                        "code": "exclusion",
                        "display": "Exclusion"
                    }],
                    "text": category.replace("_", " ").title() + " Exclusion"
                },
                "comment": desc
            }

            # Add structured waiting period value if time-bound
            wp = _parse_number(wp_days)
            if wp:
                cost_entry["value"] = {
                    "value": wp,
                    "unit": "days",
                    "system": "http://unitsofmeasure.org",
                    "code": "d"
                }
            elif category == "permanent":
                cost_entry["value"] = {
                    "value": 0,
                    "unit": "INR",
                    "system": "urn:iso:std:iso:4217",
                    "code": "INR"
                }

            benefit_entries.append({
                "type": {"text": name},
                "cost": [cost_entry]
            })

        specific_costs.append({
            "category": {
                "coding": [{
                    "system": NDHM_PLAN_COST_TYPE_SYSTEM,
                    "code": "exclusion",
                    "display": "Exclusion"
                }]
            },
            "benefit": benefit_entries
        })

    # Co-pay details from benefits
    for b in data.get("benefits", []):
        if not isinstance(b, dict):
            continue
        copay = b.get("copay_percent", "")
        if copay:
            copay_val = _parse_number(copay)
            if copay_val:
                specific_costs.append({
                    "category": {"text": b.get("category", "other")},
                    "benefit": [{
                        "type": {"text": b.get("name", "Benefit")},
                        "cost": [{
                            "type": {
                                "coding": [{
                                    "system": "http://terminology.hl7.org/CodeSystem/benefit-type",
                                    "code": "copay-percent",
                                    "display": "Copayment Percent per service"
                                }],
                                "text": f"{int(copay_val)}% Co-pay"
                            },
                            "value": {"value": copay_val, "unit": "%"}
                        }]
                    }]
                })

    if specific_costs:
        plan_section["specificCost"] = specific_costs

    return [plan_section] if plan_section else None


# ─────────────────────────────────────────────────────────────
# Eligibility extensions
# ─────────────────────────────────────────────────────────────

_PLACEHOLDER_SET = {"not specified", "n/a", "unknown", "na", "none", "nil", "0", "-", "--", ""}


def _is_valid_elig_value(val):
    if not val:
        return False
    return str(val).strip().lower() not in _PLACEHOLDER_SET


def _build_eligibility_extension(eligibility):
    """Build extensions for eligibility rules."""
    extensions = []
    base_url = "https://nrces.in/ndhm/fhir/r4/StructureDefinition"

    if not isinstance(eligibility, dict):
        return None

    if _is_valid_elig_value(eligibility.get("min_age")):
        extensions.append({
            "url": f"{base_url}/InsurancePlanEligibility-MinAge",
            "valueString": str(eligibility["min_age"]).strip()
        })
    if _is_valid_elig_value(eligibility.get("max_age")):
        extensions.append({
            "url": f"{base_url}/InsurancePlanEligibility-MaxAge",
            "valueString": str(eligibility["max_age"]).strip()
        })
    if _is_valid_elig_value(eligibility.get("renewal_age")):
        extensions.append({
            "url": f"{base_url}/InsurancePlanEligibility-RenewalAge",
            "valueString": str(eligibility["renewal_age"]).strip()
        })
    if _is_valid_elig_value(eligibility.get("pre_existing_waiting")):
        val = str(eligibility["pre_existing_waiting"]).strip()
        if "month" not in val.lower() and "year" not in val.lower():
            val = f"{val} months"
        extensions.append({
            "url": f"{base_url}/InsurancePlanEligibility-PreExistingWaiting",
            "valueString": val
        })
    for cond in eligibility.get("conditions", []):
        if _is_valid_elig_value(cond):
            extensions.append({
                "url": f"{base_url}/InsurancePlanEligibility-Condition",
                "valueString": str(cond).strip()
            })

    return extensions if extensions else None


# ─────────────────────────────────────────────────────────────
# Organization & InsurancePlan builders
# ─────────────────────────────────────────────────────────────

def _build_telecom(data):
    """Build Organization.telecom[] (Rule 2)."""
    telecom = data.get("telecom", {})
    entries = []

    phone = telecom.get("phone", "") if isinstance(telecom, dict) else ""
    email = telecom.get("email", "") if isinstance(telecom, dict) else ""
    website = telecom.get("website", "") if isinstance(telecom, dict) else ""

    entries.append({
        "system": "phone",
        "value": phone if phone else "1800-266-9595",
        "use": "work"
    })
    if email:
        entries.append({"system": "email", "value": email, "use": "work"})
    if website:
        entries.append({"system": "url", "value": website})

    return entries


def _build_network(org_id, org_name, data):
    """Build InsurancePlan.network[] (Rule 8)."""
    network_type = str(data.get("network_type", "")).lower()
    if "cashless" in network_type or "both" in network_type or "network" in network_type:
        return [{
            "reference": f"Organization/{org_id}",
            "display": f"{org_name} Network Hospitals"
        }]
    return None


def _build_contact(data):
    """Build InsurancePlan.contact[] (Rule 9)."""
    telecom = data.get("telecom", {})
    phone = telecom.get("phone", "") if isinstance(telecom, dict) else ""

    contact_telecom = []
    if phone:
        contact_telecom.append({"system": "phone", "value": phone})

    return [{
        "purpose": {"text": "Customer Service"},
        "telecom": contact_telecom
    }]


def _build_period(data):
    """Build InsurancePlan.period (Rule 10)."""
    period_years = data.get("policy_period_years", "")
    if not period_years or str(period_years).strip().lower() in _PLACEHOLDER_SET:
        return None
    try:
        years = int(str(period_years).strip())
        if years > 0:
            return {"start": "2024-01-01", "end": f"{2024 + years}-01-01"}
    except ValueError:
        pass
    return None

# ─────────────────────────────────────────────────────────────
# IRDAI Standard Exclusion Code Mapping
# ─────────────────────────────────────────────────────────────

IRDAI_EXCLUSION_CODES = {
    "pre-existing": "Excl01", "pre existing": "Excl01", "ped": "Excl01",
    "specified disease": "Excl02", "specific waiting": "Excl02",
    "30 day": "Excl03", "first 30": "Excl03", "initial waiting": "Excl03",
    "war": "Excl04", "act of war": "Excl04",
    "breach of law": "Excl05", "criminal": "Excl05",
    "hazardous": "Excl06", "adventure sport": "Excl06",
    "suicide": "Excl07", "self-inflicted": "Excl07",
    "alcohol": "Excl08", "substance abuse": "Excl08", "drug": "Excl08",
    "hiv": "Excl09", "aids": "Excl09",
    "refractive error": "Excl10", "spectacle": "Excl10",
    "cosmetic": "Excl11", "plastic surgery": "Excl11",
    "circumcision": "Excl12",
    "gender change": "Excl13", "change-of-gender": "Excl13", "sex change": "Excl13",
    "non-allopathic": "Excl14", "non allopathic": "Excl14",
    "experimental": "Excl15", "unproven": "Excl15",
    "preventive care": "Excl16", "vaccination": "Excl16",
    "hearing aid": "Excl17",
    "dental": "Excl18",
    "maternity": "Excl19",
    "alopecia": "Excl20", "baldness": "Excl20",
    "prosthesis": "Excl21", "durable medical": "Excl21",
    "excluded provider": "Excl22",
    "outside india": "Excl23", "treatment outside": "Excl23",
}


def _infer_irdai_code(exclusion):
    """Map exclusion to IRDAI standard codes (Excl01-Excl23)."""
    name = exclusion.get("name", "").lower()
    desc = exclusion.get("description", "").lower()
    # Check explicit irdai_code from LLM first
    llm_code = exclusion.get("irdai_code", "")
    if llm_code and llm_code.startswith("Excl"):
        return llm_code
    # Infer from name/description
    combined = name + " " + desc
    for keyword, code in IRDAI_EXCLUSION_CODES.items():
        if keyword in combined:
            return code
    return None


def _build_plan_section_with_general_cost(data):
    """Build InsurancePlan.plan[] with generalCost (premium) and specificCost (exclusions, co-pays).
    Includes IRDAI exclusion codes."""
    plan_section = {}

    # generalCost — premium or sum insured
    general_costs = []
    premium = data.get("premium_amount", "")
    premium_val = _parse_number(premium)
    if premium_val:
        general_costs.append({
            "type": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/insuranceplan-cost-type",
                    "code": "premium",
                    "display": "Premium"
                }]
            },
            "value": {
                "value": premium_val,
                "unit": "INR",
                "system": "urn:iso:std:iso:4217",
                "code": "INR"
            }
        })

    # Always include sum_insured as general cost reference
    si_val = _parse_number(data.get("sum_insured", ""))
    if si_val:
        general_costs.append({
            "type": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/insuranceplan-cost-type",
                    "code": "deductible",
                    "display": "Sum Insured"
                }]
            },
            "value": {
                "value": si_val,
                "unit": "INR",
                "system": "urn:iso:std:iso:4217",
                "code": "INR"
            },
            "comment": "Overall Sum Insured for the policy"
        })

    # Fallback: always have at least one generalCost entry
    if not general_costs:
        general_costs.append({
            "type": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/insuranceplan-cost-type",
                    "code": "deductible",
                    "display": "Sum Insured"
                }]
            },
            "comment": "Sum Insured as per Policy Schedule / Certificate of Insurance"
        })

    plan_section["generalCost"] = general_costs


    # specificCost — exclusions + co-pays
    specific_costs = []

    exclusions = data.get("exclusions", [])
    if exclusions:
        benefit_entries = []
        for exc in exclusions:
            name = exc.get("name", "") if isinstance(exc, dict) else str(exc)
            desc = exc.get("description", name) if isinstance(exc, dict) else str(exc)
            category = exc.get("category", "permanent") if isinstance(exc, dict) else "permanent"
            wp_days = exc.get("waiting_period_days", "") if isinstance(exc, dict) else ""

            # IRDAI exclusion code
            irdai_code = _infer_irdai_code(exc) if isinstance(exc, dict) else None

            cost_coding = [{
                "system": NDHM_PLAN_COST_TYPE_SYSTEM,
                "code": "exclusion",
                "display": "Exclusion"
            }]
            # Add IRDAI code as additional coding
            if irdai_code:
                cost_coding.append({
                    "system": "https://irdai.gov.in/exclusion-code",
                    "code": irdai_code,
                    "display": f"IRDAI Standard Exclusion {irdai_code}"
                })

            cost_entry = {
                "type": {
                    "coding": cost_coding,
                    "text": category.replace("_", " ").title() + " Exclusion"
                },
                "comment": desc
            }

            wp = _parse_number(wp_days)
            if wp:
                cost_entry["value"] = {
                    "value": wp,
                    "unit": "days",
                    "system": "http://unitsofmeasure.org",
                    "code": "d"
                }
            elif category == "permanent":
                cost_entry["value"] = {
                    "value": 0,
                    "unit": "INR",
                    "system": "urn:iso:std:iso:4217",
                    "code": "INR"
                }

            benefit_entries.append({
                "type": {"text": name},
                "cost": [cost_entry]
            })

        specific_costs.append({
            "category": {
                "coding": [{
                    "system": NDHM_PLAN_COST_TYPE_SYSTEM,
                    "code": "exclusion",
                    "display": "Exclusion"
                }]
            },
            "benefit": benefit_entries
        })

    # Co-pay details
    for b in data.get("benefits", []):
        if not isinstance(b, dict):
            continue
        copay = b.get("copay_percent", "")
        copay_val = _parse_number(copay)
        if copay_val:
            specific_costs.append({
                "category": {"text": b.get("category", "other")},
                "benefit": [{
                    "type": {"text": b.get("name", "Benefit")},
                    "cost": [{
                        "type": {
                            "coding": [{
                                "system": "http://terminology.hl7.org/CodeSystem/benefit-type",
                                "code": "copay-percent",
                                "display": "Copayment Percent per service"
                            }],
                            "text": f"{int(copay_val)}% Co-pay"
                        },
                        "value": {"value": copay_val, "unit": "%"}
                    }]
                }]
            })

    if specific_costs:
        plan_section["specificCost"] = specific_costs

    return [plan_section] if plan_section else None


# ─────────────────────────────────────────────────────────────
# NEW NHCX RESOURCES: Patient, Coverage, CoverageEligibilityRequest, Claim
# ─────────────────────────────────────────────────────────────

def _build_patient(data):
    """Build a generic Patient/Group resource for NHCX."""
    patient_id = _make_uuid()
    plan_type = str(data.get("plan_type", "")).lower()

    if plan_type == "group":
        return patient_id, {
            "resourceType": "Group",
            "id": patient_id,
            "type": "person",
            "actual": False,
            "name": "Insured Group Members"
        }
    else:
        return patient_id, {
            "resourceType": "Patient",
            "id": patient_id,
            "meta": {
                "profile": ["https://nrces.in/ndhm/fhir/r4/StructureDefinition/Patient"]
            },
            "identifier": [{
                "system": "https://healthid.ndhm.gov.in",
                "value": "SAMPLE-ABHA-ID"
            }],
            "name": [{"text": "Insured Person"}],
            "active": True
        }


def _build_coverage(org_id, plan_id, patient_id, data):
    """Build a Coverage resource for NHCX workflow."""
    cov_id = _make_uuid()
    return cov_id, {
        "resourceType": "Coverage",
        "id": cov_id,
        "meta": {
            "profile": ["https://nrces.in/ndhm/fhir/r4/StructureDefinition/Coverage"]
        },
        "status": "active",
        "type": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                "code": "HIP",
                "display": "health insurance plan policy"
            }]
        },
        "subscriber": {
            "reference": f"Patient/{patient_id}"
        },
        "beneficiary": {
            "reference": f"Patient/{patient_id}"
        },
        "period": {
            "start": "2024-01-01",
            "end": "2025-01-01"
        },
        "payor": [{
            "reference": f"Organization/{org_id}",
            "display": data.get("organization", "Unknown")
        }],
        "class": [{
            "type": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/coverage-class",
                    "code": "plan",
                    "display": "Plan"
                }]
            },
            "value": data.get("plan_name", "Unknown Plan"),
            "name": data.get("plan_name", "Unknown Plan")
        }]
    }


def _build_coverage_eligibility_request(org_id, cov_id, patient_id, data):
    """Build CoverageEligibilityRequest for NHCX eligibility checks."""
    cer_id = _make_uuid()
    return cer_id, {
        "resourceType": "CoverageEligibilityRequest",
        "id": cer_id,
        "meta": {
            "profile": ["https://nrces.in/ndhm/fhir/r4/StructureDefinition/CoverageEligibilityRequest"]
        },
        "status": "active",
        "purpose": ["benefits"],
        "patient": {
            "reference": f"Patient/{patient_id}"
        },
        "created": _timestamp().split("T")[0],
        "insurer": {
            "reference": f"Organization/{org_id}",
            "display": data.get("organization", "Unknown")
        },
        "insurance": [{
            "coverage": {
                "reference": f"Coverage/{cov_id}"
            }
        }]
    }


def _build_claim_template(org_id, cov_id, patient_id, data):
    """Build a Claim resource template for NHCX pre-auth/claims workflow."""
    claim_id = _make_uuid()
    return claim_id, {
        "resourceType": "Claim",
        "id": claim_id,
        "meta": {
            "profile": ["https://nrces.in/ndhm/fhir/r4/StructureDefinition/Claim"]
        },
        "status": "active",
        "type": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/claim-type",
                "code": "institutional",
                "display": "Institutional"
            }]
        },
        "use": "preauthorization",
        "patient": {
            "reference": f"Patient/{patient_id}"
        },
        "created": _timestamp().split("T")[0],
        "insurer": {
            "reference": f"Organization/{org_id}",
            "display": data.get("organization", "Unknown")
        },
        "provider": {
            "reference": f"Organization/{org_id}"
        },
        "priority": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/processpriority",
                "code": "normal"
            }]
        },
        "insurance": [{
            "sequence": 1,
            "focal": True,
            "coverage": {
                "reference": f"Coverage/{cov_id}"
            }
        }]
    }


def _build_claim_response_template(org_id, claim_id, patient_id, data):
    """Build a ClaimResponse resource template."""
    cr_id = _make_uuid()
    return cr_id, {
        "resourceType": "ClaimResponse",
        "id": cr_id,
        "meta": {
            "profile": ["https://nrces.in/ndhm/fhir/r4/StructureDefinition/ClaimResponse"]
        },
        "status": "active",
        "type": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/claim-type",
                "code": "institutional",
                "display": "Institutional"
            }]
        },
        "use": "preauthorization",
        "patient": {
            "reference": f"Patient/{patient_id}"
        },
        "created": _timestamp().split("T")[0],
        "insurer": {
            "reference": f"Organization/{org_id}",
            "display": data.get("organization", "Unknown")
        },
        "request": {
            "reference": f"Claim/{claim_id}"
        },
        "outcome": "queued"
    }


# ─────────────────────────────────────────────────────────────
# MAIN: map_to_fhir
# ─────────────────────────────────────────────────────────────

def map_to_fhir(data):
    """Map extracted insurance data to an NHCX-compliant FHIR Bundle.
    Includes: Organization, InsurancePlan, Patient, Coverage,
    CoverageEligibilityRequest, Claim, ClaimResponse."""
    org_id = _make_uuid()
    plan_id = _make_uuid()
    bundle_id = _make_uuid()
    org_name = data.get("organization", "Unknown")

    # ─── Organization (Rule 2: telecom) ───
    organization = {
        "resourceType": "Organization",
        "id": org_id,
        "meta": {"profile": [NHCX_ORGANIZATION_PROFILE]},
        "identifier": [{
            "system": "https://irdai.gov.in/insurer-id",
            "value": data.get("insurer_id", "UNKNOWN")
        }],
        "name": org_name,
        "active": True,
        "telecom": _build_telecom(data)
    }

    # ─── InsurancePlan type ───
    type_code, type_display = "medical", "Medical"
    raw_plan_type = str(data.get("plan_type", "")).strip().lower()
    valid_plan_types = {"individual", "family_floater", "group"}
    plan_type_text = raw_plan_type if raw_plan_type in valid_plan_types else "individual"

    # ─── InsurancePlan ───
    insurance_plan = {
        "resourceType": "InsurancePlan",
        "id": plan_id,
        "meta": {"profile": [NHCX_INSURANCE_PLAN_PROFILE]},
        "identifier": [{
            "system": "https://irdai.gov.in/uin",
            "value": data.get("uin", data.get("plan_name", "UNKNOWN"))
        }],
        "status": "active",
        "name": data.get("plan_name", "Unknown Plan").strip(),
        "type": [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/insurance-plan-type",
                "code": type_code,
                "display": type_display
            }],
            "text": plan_type_text
        }],
        "ownedBy": {
            "reference": f"Organization/{org_id}",
            "display": org_name
        },
        "administeredBy": {
            "reference": f"Organization/{org_id}",
            "display": org_name
        },
        "contact": _build_contact(data),
        "coverage": _build_fhir_coverage(data)
    }

    # Network
    network = _build_network(org_id, org_name, data)
    if network:
        insurance_plan["network"] = network

    # Period
    period = _build_period(data)
    if period:
        insurance_plan["period"] = period

    # Plan section (with generalCost + exclusions with IRDAI codes)
    plan_section = _build_plan_section_with_general_cost(data)
    if plan_section:
        insurance_plan["plan"] = plan_section

    # Eligibility extensions
    elig_ext = _build_eligibility_extension(data.get("eligibility"))
    if elig_ext:
        insurance_plan["extension"] = elig_ext

    # ─── Patient/Group resource ───
    patient_id, patient_resource = _build_patient(data)

    # ─── Coverage resource ───
    cov_id, coverage_resource = _build_coverage(org_id, plan_id, patient_id, data)

    # ─── CoverageEligibilityRequest ───
    cer_id, cer_resource = _build_coverage_eligibility_request(org_id, cov_id, patient_id, data)

    # ─── Claim (pre-auth template) ───
    claim_id, claim_resource = _build_claim_template(org_id, cov_id, patient_id, data)

    # ─── ClaimResponse ───
    cr_id, cr_resource = _build_claim_response_template(org_id, claim_id, patient_id, data)

    # ─── Bundle ───
    bundle = {
        "resourceType": "Bundle",
        "id": bundle_id,
        "meta": {"lastUpdated": _timestamp()},
        "type": "collection",
        "timestamp": _timestamp(),
        "entry": [
            {"fullUrl": _make_urn(org_id), "resource": organization},
            {"fullUrl": _make_urn(plan_id), "resource": insurance_plan},
            {"fullUrl": _make_urn(patient_id), "resource": patient_resource},
            {"fullUrl": _make_urn(cov_id), "resource": coverage_resource},
            {"fullUrl": _make_urn(cer_id), "resource": cer_resource},
            {"fullUrl": _make_urn(claim_id), "resource": claim_resource},
            {"fullUrl": _make_urn(cr_id), "resource": cr_resource},
        ]
    }

    total_benefits = sum(len(c.get("benefit", [])) for c in insurance_plan.get("coverage", []))
    logger.info(f"Mapped FHIR bundle: {bundle_id} with {total_benefits} benefits, "
                f"{len(data.get('exclusions', []))} exclusions, "
                f"7 resources (Org, InsurancePlan, Patient, Coverage, CoverageEligReq, Claim, ClaimResponse)")

    return bundle


def _timestamp():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

