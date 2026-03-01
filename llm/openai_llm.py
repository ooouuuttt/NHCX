import os
import json
import time
import logging
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError, APIError

load_dotenv()

logger = logging.getLogger(__name__)

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

####################################################
# SETTINGS
####################################################

MODEL = "gpt-4o-mini"

CHUNK_SIZE = 12000   # bigger chunks = fewer requests

MAX_RETRIES = 6

BASE_DELAY = 10   # seconds

KEYWORDS = [
    "benefit", "coverage", "sum insured", "limit",
    "hospital", "expenses", "eligibility", "exclusion",
    "room rent", "icu", "ambulance", "treatment", "claim",
    "co-pay", "copay", "deductible", "waiting period",
    "sub-limit", "sublimit", "maternity", "daycare",
    "pre-existing", "network", "cashless", "uin", "registration", "irdai",
    "product name", "plan name", "shield", "scope of cover", "what is covered",
    "contact", "toll free", "1800", "email", "website", "customer service",
    "irdai reg", "reg.", "cin no", "section ii", "cancer", "heart", "income protect",
    "credit protect", "cardiac", "major illness"
]


####################################################
# SYSTEM PROMPT — detailed instructions for LLM
####################################################

SYSTEM_PROMPT = """You are an expert health insurance policy parser for Indian insurance plans.

Extract ONLY real information found in the text. Do NOT hallucinate or invent data.

Return a JSON object with this EXACT structure:

{
  "organization": "Name of the insurance company",
  "insurer_id": "IRDAI Registration Number — look for 'IRDAI Reg. No.' or 'Registration No.' (e.g. '153', '115'). This is NOT the UIN.",
  "uin": "Unique Identification Number (UIN) of the product (e.g. 'ADIHLGP22023V032122')",
  "plan_name": "Exact product name from the PDF title/header",
  "plan_type": "individual | family_floater | group",
  "coverage_type": "health | accident | critical_illness | life",
  "sum_insured": "Overall sum insured amount as string e.g. '500000'",
  "currency": "INR",
  "premium_amount": "Annual premium amount if mentioned in the document",
  "telecom": {
    "phone": "Toll-free or customer service phone number",
    "email": "Customer service email address",
    "website": "Insurer website URL"
  },
  "benefits": [
    {
      "name": "Benefit name exactly as written in the PDF",
      "section": "Section reference (e.g. 'Section I', 'Section II.2', 'C.2.1')",
      "category": "inpatient | outpatient | daycare | maternity | ambulance | ayush | dental | mental_health | organ_donor | rehabilitation | domiciliary | pre_hospitalization | post_hospitalization | other",
      "description": "COMPLETE description — full sentences from the PDF. Copy the ENTIRE paragraph. Never truncate. Never end mid-sentence. Include all conditions, sublimits, and qualifying criteria.",
      "limit_amount": "Monetary limit in INR. If 'up to Sum Insured', put the actual SI number. Leave empty if not stated.",
      "limit_unit": "amount | percentage_of_si | days",
      "max_days": "Maximum number of days if applicable (e.g. '30', '60', '90')",
      "percentage_payout": "Percentage payout if applicable (e.g. '50' for 50%)",
      "sub_benefits": [
        {
          "name": "Sub-benefit name (e.g. 'Doctor Consultation', 'Diagnostic Tests', 'Pharmacy')",
          "limit_amount": "Sub-benefit specific limit amount",
          "limit_unit": "amount | percentage_of_si",
          "description": "Sub-benefit description"
        }
      ],
      "sub_limits": [],
      "copay_percent": "",
      "waiting_period_days": "Waiting period in DAYS. Convert: 1 year=365, 2 years=730, 30 days=30, 90 days=90. Only if explicitly stated for THIS benefit.",
      "deductible_days": "Deductible/survival period in days if applicable",
      "options": [
        {
          "option_name": "Option 1 / Option 2 etc.",
          "covered_conditions": ["list of covered conditions"],
          "payout_stages": [
            {"stage": "Early Stage", "percentage": "50"},
            {"stage": "Major Stage", "percentage": "100"}
          ]
        }
      ],
      "is_optional": false
    }
  ],
  "exclusions": [
    {
      "name": "Exclusion name",
      "irdai_code": "IRDAI standard exclusion code (e.g. 'Excl01', 'Excl02', ... 'Excl18')",
      "description": "Full description of what is excluded — COMPLETE text from PDF, never truncated",
      "category": "permanent | time_bound",
      "waiting_period_days": "If time_bound, waiting period in days (e.g. '730' for 2 years)"
    }
  ],
  "eligibility": {
    "min_age": "",
    "max_age": "",
    "renewal_age": "",
    "pre_existing_waiting": "",
    "conditions": []
  },
  "network_type": "cashless | reimbursement | both",
  "portability": null,
  "policy_period_years": "Duration of the policy in years, e.g. '1'",
  "period_start_date": "Policy period start date if explicitly mentioned (YYYY-MM-DD format, e.g. '2024-01-01')",
  "period_end_date": "Policy period end date if explicitly mentioned (YYYY-MM-DD format)"
}

=== MANDATORY HARD RULES ===

1. plan_name MUST exactly equal the product name from the PDF title.

2. insurer_id is the IRDAI Registration Number (e.g. '153', '115', '144').
   - Look for "IRDAI Reg. No." or "Registration No." or "IRDA Reg No."
   - This is NOT the UIN. It is typically a 2-3 digit number.

3. NEVER invent or fabricate benefits.

4. Extract benefits from ALL numbered sections:
   - Section I, Section II, Section III, etc.
   - Including: Cancer Secure, Heart Secure, Income Protect, Credit Protect
   - Including sub-sections like II.2, II.3, II.5, II.9
   - Benefit schedule sections (Section C, C.2.1 through C.2.17)
   DO NOT extract from: Definitions, Glossary, Examples.

5. Benefit descriptions MUST be COMPLETE:
   - Copy the FULL paragraph from the PDF. Include ALL conditions.
   - Never end mid-sentence. If text says "has been.", include the full sentence.
   - Include monetary amounts, percentages, conditions, and qualifying criteria.

6. Extract ALL types of limits — every benefit MUST have at least one:
   - If benefit says "up to Sum Insured" → put the actual SI number in limit_amount
   - If benefit says percentage (50%, 100%, 150%) → put in percentage_payout
   - If benefit has day limits (30/60/90/180 days) → put in max_days
   - If benefit has waiting period → put in waiting_period_days
   - Only omit limit_amount if truly no limit is mentioned

7. For Cancer/Heart/Income covers with multiple OPTIONS:
   - Include ALL options in the "options" array
   - Include ALL covered conditions per option
   - Include stage-wise payouts (Early Stage 50%, Major Stage 100%, etc.)

8. For OPD benefits, break into sub_benefits:
   - Doctor Consultation with its specific limit
   - Diagnostic Tests with its specific limit  
   - Pharmacy Expenses with its specific limit

9. For exclusions, map to IRDAI standard codes where possible:
   - Pre-existing disease = Excl01
   - Specific waiting period diseases = Excl02
   - First 30 days waiting = Excl03
   - War = Excl04, Breach of law = Excl05
   - Hazardous activities = Excl06, etc.

10. Extract premium if mentioned.

11. DO NOT duplicate benefits.

12. DO NOT use placeholder values. Use "" if not found.

13. waiting_period_days should ONLY be set if the PDF explicitly states a waiting period
    for that specific benefit. Do NOT assume waiting periods.

14. MONETARY AMOUNT EXTRACTION:
    - Extract numeric values EXACTLY: 500000 not \"5 lakh\"
    - If PDF says \"Rs. 5,00,000\" extract as \"500000\"
    - If PDF says \"5 Lakh\" extract as \"500000\"
    - If PDF says \"up to Sum Insured\" use the actual SI value instead
    - Never use text like Lakh, Crore. Always convert to plain number.
    - If unknown, leave empty, never use 0 or N/A.
"""




####################################################
# STEP 1: Extract relevant sections
####################################################

def extract_relevant_sections(text):
    lines = text.split("\n")
    
    # ALWAYS include the first 20 lines — they contain the product name, UIN, etc.
    header_lines = lines[:20]
    # ALWAYS include the last 15 lines — they contain IRDAI Reg No, CIN, etc.
    footer_lines = lines[-15:] if len(lines) > 15 else []
    
    relevant = []
    for line in lines:
        if any(k in line.lower() for k in KEYWORDS):
            relevant.append(line)

    # If filtering removes too much → use full text
    if len(relevant) < 50:
        return text

    # Prepend header + append footer to ensure IRDAI Reg and product name are always captured
    header_text = "\n".join(header_lines)
    footer_text = "\n".join(footer_lines)
    body_text = "\n".join(relevant)
    return header_text + "\n\n" + body_text + "\n\n" + footer_text


####################################################
# STEP 2: Chunk text
####################################################

def chunk_text(text):
    chunks = []
    start = 0

    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start = end

    return chunks


####################################################
# STEP 3: Safe LLM call with exponential backoff
####################################################

def call_llm(prompt):
    delay = BASE_DELAY

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ]
            )

            return json.loads(response.choices[0].message.content)

        except RateLimitError:
            logger.warning(f"Rate limit hit. Waiting {delay}s (attempt {attempt+1})")
            time.sleep(delay)
            delay *= 2

        except APIError as e:
            logger.error(f"API error: {e}")
            time.sleep(delay)

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

    logger.error("Failed after all retries.")
    return None


####################################################
# STEP 4: Extract chunk
####################################################

def extract_chunk(chunk, chunk_index=0, total_chunks=1):
    prompt = f"""Extract insurance plan structured data from the following text.
Return the JSON object as specified in your instructions.

CRITICAL REMINDERS:
- plan_name = the PRODUCT NAME from the PDF title/header (e.g. "Group Protect", "Family Shield").
  It is NOT a benefit name. Look at the first page or document header.
- insurer_id = IRDAI Registration Number (2-3 digit number, NOT the UIN).
  Look for "IRDAI Reg. No." or "Registration No." in the text.
- Extract EVERY benefit section: Section I, II, III, Cancer Secure, Heart Secure,
  Income Protect, Credit Protect, OPD, Ambulance, etc.
- For each benefit, COPY THE FULL DESCRIPTION. Never truncate.
  Include all qualifying conditions, sublimits, and criteria.
- Every benefit MUST have limit_amount filled if any monetary value exists.
  If benefit says "up to Sum Insured", use the actual sum insured amount.
- For multi-option covers (Cancer Secure Options 1-2, Heart Secure Options 1-8),
  include ALL options with their covered conditions and stage-wise payouts.
- For OPD, break out sub-benefits: Doctor Consultation, Diagnostic Tests, Pharmacy.
- For exclusions, include IRDAI codes (Excl01-Excl18) if referenced in text.
- waiting_period_days: ONLY set if explicitly stated for this specific benefit.
  Do NOT assume or invent waiting periods.
- plan_type: "individual", "family_floater", or "group" — not the template string.
- Use "" for any value not found in this chunk.

This is chunk {chunk_index + 1} of {total_chunks}.

TEXT:
{chunk}
"""

    result = call_llm(prompt)
    time.sleep(10)
    return result



####################################################
# STEP 5: Merge structured results from chunks
####################################################

# Placeholder / invalid values that should be treated as empty
_PLACEHOLDER_VALUES = {
    "not specified", "n/a", "unknown", "na", "none", "nil", "0", "-", "--",
    "not available", "not applicable", "not mentioned", "not found"
}


def _is_placeholder(value):
    """Check if a string value is a placeholder/invalid."""
    if not value:
        return True
    return str(value).strip().lower() in _PLACEHOLDER_VALUES


def _clean_value(value):
    """Return empty string if value is a placeholder, otherwise strip it."""
    if _is_placeholder(value):
        return ""
    return str(value).strip()


def _dedupe_by_name(items):
    """De-duplicate a list of dicts by their 'name' field (case-insensitive).
    Strictly enforces Rule 5: NEVER duplicate benefits.
    Keeps the entry with the most complete data when duplicates are found."""
    seen = {}  # name -> item
    for item in items:
        name = item.get("name", "").strip().lower()
        if not name:
            continue
        if name not in seen:
            seen[name] = item
        else:
            # Keep the version with more filled fields
            existing = seen[name]
            existing_score = sum(1 for v in existing.values() if v)
            new_score = sum(1 for v in item.values() if v)
            if new_score > existing_score:
                seen[name] = item
    return list(seen.values())


def _filter_benefits(benefits):
    """Remove benefits that are optional riders, placeholders, or invalid."""
    filtered = []
    for b in benefits:
        if not isinstance(b, dict):
            continue
        name = b.get("name", "").strip()
        # Skip empty names
        if not name or _is_placeholder(name):
            continue
        # Skip optional riders
        if b.get("is_optional", False):
            continue
        # Clean placeholder values within the benefit
        b["limit_amount"] = _clean_value(b.get("limit_amount", ""))
        b["description"] = _clean_value(b.get("description", ""))
        b["copay_percent"] = _clean_value(b.get("copay_percent", ""))
        b["waiting_period_days"] = _clean_value(b.get("waiting_period_days", ""))
        b["max_days"] = _clean_value(b.get("max_days", ""))
        b["percentage_payout"] = _clean_value(b.get("percentage_payout", ""))
        filtered.append(b)
    return filtered


def merge_results(results):
    final = {
        "organization": "",
        "insurer_id": "",
        "uin": "",
        "plan_name": "",
        "plan_type": "",
        "coverage_type": "",
        "sum_insured": "",
        "currency": "INR",
        "premium_amount": "",
        "telecom": {"phone": "", "email": "", "website": ""},
        "benefits": [],
        "exclusions": [],
        "eligibility": {
            "min_age": "",
            "max_age": "",
            "renewal_age": "",
            "pre_existing_waiting": "",
            "conditions": []
        },
        "network_type": "",
        "portability": None,
        "policy_period_years": "",
        "period_start_date": "",
        "period_end_date": ""
    }


    for r in results:
        if not r:
            continue

        # Scalar fields — take the first non-placeholder value
        for key in ["organization", "insurer_id", "uin", "plan_name", "plan_type", "coverage_type",
                     "sum_insured", "currency", "network_type", "policy_period_years", "period_start_date", 
                     "period_end_date", "premium_amount"]:
            val = _clean_value(r.get(key, ""))
            if val and not final[key]:
                final[key] = val

        if r.get("portability") is not None and final["portability"] is None:
            final["portability"] = r["portability"]

        # Telecom — merge non-empty fields
        telecom = r.get("telecom")
        if isinstance(telecom, dict):
            for tk in ["phone", "email", "website"]:
                tv = _clean_value(telecom.get(tk, ""))
                if tv and not final["telecom"][tk]:
                    final["telecom"][tk] = tv

        # Structured benefits
        for b in r.get("benefits", []):
            if isinstance(b, dict):
                final["benefits"].append(b)
            elif isinstance(b, str) and not _is_placeholder(b):
                final["benefits"].append({
                    "name": b, "category": "other", "description": b,
                    "limit_amount": "", "limit_unit": "", "sub_limits": [],
                    "copay_percent": "", "waiting_period_days": "",
                    "max_days": "", "percentage_payout": "",
                    "is_optional": False
                })

        # Structured exclusions
        for e in r.get("exclusions", []):
            if isinstance(e, dict):
                name = e.get("name", "").strip()
                if name and not _is_placeholder(name):
                    final["exclusions"].append(e)
            elif isinstance(e, str) and not _is_placeholder(e):
                final["exclusions"].append({
                    "name": e, "description": e,
                    "category": "permanent", "waiting_period_days": ""
                })

        # Eligibility — merge non-placeholder fields
        elig = r.get("eligibility")
        if isinstance(elig, dict):
            for key in ["min_age", "max_age", "renewal_age", "pre_existing_waiting"]:
                val = _clean_value(elig.get(key, ""))
                if val and not final["eligibility"].get(key):
                    final["eligibility"][key] = val
            for c in elig.get("conditions", []):
                if c and not _is_placeholder(c) and c not in final["eligibility"]["conditions"]:
                    final["eligibility"]["conditions"].append(c)
        elif isinstance(elig, str) and elig and not _is_placeholder(elig):
            final["eligibility"]["conditions"].append(elig)

    # Filter out invalid benefits, then de-duplicate
    final["benefits"] = _filter_benefits(final["benefits"])
    final["benefits"] = _dedupe_by_name(final["benefits"])
    final["exclusions"] = _dedupe_by_name(final["exclusions"])

    # Post-processing: Validate plan_name is not a generic description
    _GENERIC_PLAN_NAMES = {
        "health insurance", "health insurance policy", "health insurance plan",
        "insurance plan", "insurance policy", "general insurance",
        "group insurance", "personal accident policy", "personal accident plan",
    }
    plan_name = final.get("plan_name", "").strip()
    org_name = final.get("organization", "").strip()
    if org_name and plan_name.lower().startswith(org_name.lower()):
        suffix = plan_name[len(org_name):].strip()
        if suffix.lower() in _GENERIC_PLAN_NAMES:
            logger.warning(f"plan_name '{plan_name}' looks generic. Verify against PDF title.")

    return final



####################################################
# MAIN ENTRY
####################################################

def extract_insurance_data(full_text):
    logger.info("Extracting relevant sections...")
    relevant = extract_relevant_sections(full_text)

    chunks = chunk_text(relevant)
    logger.info(f"Split into {len(chunks)} chunks")

    results = []
    total = len(chunks)
    for i, chunk in enumerate(chunks):
        logger.info(f"Processing chunk {i+1}/{total}")
        result = extract_chunk(chunk, chunk_index=i, total_chunks=total)
        if result:
            results.append(result)

    final = merge_results(results)

    # ─── Post-processing: IRDAI Reg No from raw text (regex fallback) ───
    # The LLM often misidentifies this — scan the raw text directly
    import re
    irdai_patterns = [
        r'IRDAI\s*Reg\.?\s*(?:No\.?\s*)?(\d{2,4})',
        r'IRDA\s*Reg\.?\s*(?:No\.?\s*)?(\d{2,4})',
        r'Registration\s*No\.?\s*(\d{2,4})',
        r'IRDAI\s*Registration\s*(?:Number|No\.?)\s*(\d{2,4})',
    ]
    for pattern in irdai_patterns:
        m = re.search(pattern, full_text, re.IGNORECASE)
        if m:
            extracted_id = m.group(1).strip()
            if extracted_id != final.get("insurer_id", ""):
                logger.info(f"IRDAI Reg correction: LLM gave '{final.get('insurer_id', '')}', "
                           f"regex found '{extracted_id}' → using regex value")
                final["insurer_id"] = extracted_id
            break

    # ─── Post-processing: UIN from raw text (regex fallback) ───
    if not final.get("uin") or final["uin"] == "UNKNOWN":
        uin_patterns = [
            r'UIN\s*[:.]?\s*([A-Z]{3,6}\w{10,25})',
            r'([A-Z]{3}[A-Z]{2,4}[A-Z0-9]{10,20}V\d{5,8})',
        ]
        for pattern in uin_patterns:
            m = re.search(pattern, full_text)
            if m:
                final["uin"] = m.group(1).strip()
                break

    logger.info("Extraction complete")
    logger.debug(json.dumps(final, indent=2, ensure_ascii=False))

    return final
