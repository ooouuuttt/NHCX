# NHCX Insurance Plan PDF-to-FHIR Converter

An open-source micro-service that converts insurance plan PDFs into **NHCX-compliant FHIR InsurancePlan bundles**, enabling automated consumption within NHCX and ABDM ecosystems.

---

## Problem

Insurance plan details (benefits, limits, exclusions, co-pay rules) are published as PDFs. NHCX workflows require this data as structured FHIR bundles. Manual conversion requires FHIR expertise and is slow, error-prone, and doesn't scale.

## Solution

This utility automates the conversion:

```
PDF → Text Extraction → LLM Parsing → FHIR Mapping → Validation → Output JSON
```

### Key Features

- **PDF Ingestion** — Extracts text and structured tables from insurance plan PDFs (PyMuPDF)
- **LLM Extraction** — Uses GPT-4o-mini to parse benefits, limits, sub-limits, exclusions, eligibility, and co-pay rules into structured data
- **NHCX-Compliant FHIR Mapping** — Produces `InsurancePlan` + `Organization` in a FHIR Bundle with:
  - `meta.profile` referencing NRCeS NHCX StructureDefinitions
  - Coded benefit types (HL7 + NHCX CodeSystems)
  - Monetary limits, sub-limits, co-pay percentages
  - Exclusions in `plan.generalCost`
  - Eligibility rules as FHIR extensions
  - Proper `fullUrl` (URN UUID) on all entries
- **Validation** — Two-layer: FHIR R4 Pydantic model validation + NHCX profile-specific checks
- **Configuration-Driven** — `mapping.yaml` normalizes insurer-specific terminology to standard NHCX codes
- **Human Review UI** — Streamlit app for reviewing, editing, and approving bundles before final output
- **REST API** — FastAPI micro-service with Swagger docs

---

## Quick Start

### Prerequisites

- Python 3.10+
- OpenAI API key

### Installation

```bash
git clone <repo-url>
cd NHCX
pip install -r requirements.txt
```

### Configuration

1. Create `.env` with your OpenAI API key:
   ```
   OPENAI_API_KEY=sk-your-key-here
   ```

2. Edit `config/settings.yaml`:
   ```yaml
   llm:
     provider: openai
     model: gpt-4o-mini

   pipeline:
     enable_validation: true
     enable_human_review: false  # set true to require manual approval

   paths:
     input: input_pdfs/pdfs
     output: output
   ```

### Usage

#### CLI Pipeline
```bash
# Process all PDFs in input_pdfs/pdfs/
python main.py
```

#### REST API
```bash
# Start the API server
uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload

# Convert a PDF (curl example)
curl -X POST http://localhost:8000/convert \
  -F "file=@plan.pdf"

# Validate a bundle
curl -X POST http://localhost:8000/validate \
  -H "Content-Type: application/json" \
  -d @output/plan.json
```
API docs available at `http://localhost:8000/docs`

#### Human Review UI
```bash
# Enable review in settings.yaml, then run pipeline
# Bundles go to output/pending/

# Launch review UI
streamlit run reviewer/review_ui.py
```

#### Run Tests
```bash
python -m pytest tests/ -v
```

---

## Project Structure

```
NHCX/
├── main.py                  # CLI pipeline entry point
├── requirements.txt
├── .env                     # OpenAI API key (not committed)
├── .gitignore
├── api/
│   └── server.py            # FastAPI REST API
├── config/
│   ├── settings.yaml        # Pipeline settings
│   └── mapping.yaml         # Benefit/exclusion terminology mappings
├── extractor/
│   └── pdf.py               # PDF text + table extraction (PyMuPDF)
├── llm/
│   └── openai_llm.py        # LLM-based structured data extraction
├── mapper/
│   └── nhcx_mapper.py       # FHIR InsurancePlan bundle builder
├── validator/
│   └── fhir_validator.py    # FHIR R4 + NHCX profile validation
├── reviewer/
│   └── review_ui.py         # Streamlit human review UI
├── utils/
│   └── logger.py            # Centralized logging
├── tests/
│   └── test_pipeline.py     # 34 automated tests
├── input_pdfs/pdfs/         # Input PDF files
├── output/                  # Generated FHIR bundles
│   └── pending/             # Bundles awaiting human review
└── logs/                    # Pipeline logs
```

## Pipeline Flow

```
┌─────────┐      ┌──────────┐     ┌──────────┐     ┌──────────┐      ┌──────────┐
│  PDF    │────▶│ Extract  │────▶│   LLM    │────▶│  Map to  │────▶│ Validate │
│  Input  │      │  Text    │     │  Parse   │     │  FHIR    │      │  Bundle  │
└─────────┘      └──────────┘     └──────────┘     └──────────┘      └────┬─────┘
                                                                          │
                                                          ┌───────────────┼────────┐
                                                          │               │        │
                                                    ┌─────▼─────┐ ┌────▼────┐      │
                                                    │  Human    │ │  Save   │      │
                                                    │  Review   │ │  JSON   │      │
                                                    │  (opt.)   │ │ Output  │      │
                                                    └───────────┘ └─────────┘      │
                                                                                   │
                                                                         ┌─────────▼──┐
                                                                         │  REST API  │
                                                                         │  (FastAPI) │
                                                                         └────────────┘
```

## Output Format

The output is a FHIR R4 Bundle (type: `collection`) containing:
- **Organization** — insurer details with NHCX profile
- **InsurancePlan** — plan details including:
  - `coverage[].benefit[]` — benefits with coded types and monetary limits
  - `plan[].generalCost[]` — exclusions
  - `plan[].specificCost[]` — co-pay and waiting period details
  - `extension[]` — eligibility rules (age, pre-existing disease waiting)

## Configuration

### mapping.yaml

Normalize insurer-specific terms to standard NHCX terminology:

```yaml
benefit_mapping:
  opd: OPD Expenses
  daycare: Day Care Treatment
  maternity: Maternity Cover
  ambulance: Ambulance Cover
  ayush: AYUSH Treatment
  # ... 60+ mappings
```

### Adding New Insurers

1. Place PDF(s) in `input_pdfs/pdfs/`
2. If the insurer uses unique terminology, add mappings to `config/mapping.yaml`
3. Run `python main.py`

---

## License

Open source — designed to be used by any insurance company, TPA, or integrator for NHCX onboarding.
