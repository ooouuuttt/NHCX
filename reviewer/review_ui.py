"""
Streamlit-based Human Review UI for NHCX InsurancePlan Bundles.

Launch with:  streamlit run reviewer/review_ui.py

Shows pending bundles from output/pending/, allows editing,
validates, and saves approved bundles to output/.
"""

import streamlit as st
import json
import os
import sys
import glob

# Add project root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validator.fhir_validator import validate, format_validation_report

PENDING_DIR = "output/pending"
APPROVED_DIR = "output"


def load_pending_files():
    """List all JSON files awaiting review."""
    if not os.path.exists(PENDING_DIR):
        return []
    return sorted(glob.glob(os.path.join(PENDING_DIR, "*.json")))


def load_bundle(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_bundle(bundle, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2, ensure_ascii=False)


def get_plan_resource(bundle):
    """Extract the InsurancePlan resource from the bundle."""
    for entry in bundle.get("entry", []):
        if entry.get("resource", {}).get("resourceType") == "InsurancePlan":
            return entry["resource"]
    return None


def get_org_resource(bundle):
    """Extract the Organization resource from the bundle."""
    for entry in bundle.get("entry", []):
        if entry.get("resource", {}).get("resourceType") == "Organization":
            return entry["resource"]
    return None


def main():
    st.set_page_config(page_title="NHCX InsurancePlan Reviewer", layout="wide")
    st.title("NHCX InsurancePlan — Human Review")

    pending_files = load_pending_files()

    if not pending_files:
        st.info("No bundles pending review. Run the pipeline first with `enable_human_review: true`.")
        return

    # ── File selector ──
    st.sidebar.header("Pending Reviews")
    selected_file = st.sidebar.selectbox(
        "Select a bundle to review:",
        pending_files,
        format_func=lambda x: os.path.basename(x)
    )

    if not selected_file:
        return

    bundle = load_bundle(selected_file)
    plan = get_plan_resource(bundle)
    org = get_org_resource(bundle)

    if not plan:
        st.error("No InsurancePlan resource found in this bundle.")
        return

    st.subheader(f"Reviewing: {os.path.basename(selected_file)}")

    # ── Organization Info ──
    st.header("1. Organization")
    col1, col2 = st.columns(2)
    with col1:
        org_name = st.text_input("Organization Name", value=org.get("name", "") if org else "")
    with col2:
        plan_status = st.selectbox("Plan Status", ["active", "draft", "retired"],
                                    index=["active", "draft", "retired"].index(plan.get("status", "active")))

    # ── Plan Info ──
    st.header("2. Plan Details")
    col1, col2 = st.columns(2)
    with col1:
        plan_name = st.text_input("Plan Name", value=plan.get("name", ""))
    with col2:
        plan_type_text = ""
        if plan.get("type") and len(plan["type"]) > 0:
            plan_type_text = plan["type"][0].get("text", "")
        plan_type = st.text_input("Plan Type", value=plan_type_text)

    # ── Benefits ──
    st.header("3. Benefits")
    coverages = plan.get("coverage", [])
    if coverages:
        benefits = coverages[0].get("benefit", [])
        st.write(f"**{len(benefits)} benefits found**")

        for i, ben in enumerate(benefits):
            with st.expander(f"Benefit {i+1}: {ben.get('type', {}).get('text', 'Unknown')}"):
                ben_text = st.text_input(f"Name##b{i}", value=ben.get("type", {}).get("text", ""), key=f"ben_{i}")
                if ben_text:
                    ben["type"]["text"] = ben_text

                # Show limits
                limits = ben.get("limit", [])
                if limits:
                    for li, lim in enumerate(limits):
                        val = lim.get("value", {})
                        st.text(f"  Limit: {val.get('value', '')} {val.get('unit', '')}")

                # Show requirement/description
                if ben.get("requirement"):
                    new_req = st.text_area(f"Description##b{i}", value=ben["requirement"], key=f"req_{i}")
                    ben["requirement"] = new_req
    else:
        st.warning("No coverage/benefits found.")

    # ── Exclusions ──
    st.header("4. Exclusions")
    plans_section = plan.get("plan", [])
    if plans_section:
        general_costs = plans_section[0].get("generalCost", [])
        st.write(f"**{len(general_costs)} exclusions found**")
        for i, gc in enumerate(general_costs):
            exc_name = gc.get("type", {}).get("text", "")
            exc_comment = gc.get("comment", "")
            with st.expander(f"Exclusion {i+1}: {exc_name}"):
                new_name = st.text_input(f"Name##e{i}", value=exc_name, key=f"exc_{i}")
                new_comment = st.text_area(f"Description##e{i}", value=exc_comment, key=f"exc_c_{i}")
                gc["type"]["text"] = new_name
                gc["comment"] = new_comment
    else:
        st.info("No exclusions found in the plan section.")

    # ── Apply edits to bundle (BEFORE raw JSON, so they are reflected) ──
    if org:
        org["name"] = org_name
    plan["status"] = plan_status
    plan["name"] = plan_name

    # ── Raw JSON Editor ──
    st.header("5. Raw JSON (Advanced)")
    with st.expander("Edit Raw Bundle JSON"):
        raw_json = st.text_area(
            "Bundle JSON",
            json.dumps(bundle, indent=2, ensure_ascii=False),
            height=400
        )
        try:
            bundle = json.loads(raw_json)
        except json.JSONDecodeError:
            st.error("Invalid JSON — fix before saving.")

    # ── Validation ──
    st.header("6. Validation")
    if st.button("Validate Bundle"):
        errors = validate(bundle)
        report = format_validation_report(errors)
        if errors:
            st.error(report)
        else:
            st.success(report)

    # ── Approve & Save ──
    st.header("7. Approve")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Approve & Save", type="primary"):
            errors = validate(bundle)
            if errors:
                st.warning(f"Bundle has {len(errors)} validation error(s). Saving anyway with warnings.")

            # Save to approved output directory
            approved_path = os.path.join(APPROVED_DIR, os.path.basename(selected_file))
            save_bundle(bundle, approved_path)

            # Remove from pending
            os.remove(selected_file)

            st.success(f"Saved to {approved_path} and removed from pending queue.")
            st.rerun()

    with col2:
        if st.button("Reject & Skip"):
            # Move to rejected folder
            rejected_dir = "output/rejected"
            os.makedirs(rejected_dir, exist_ok=True)
            rejected_path = os.path.join(rejected_dir, os.path.basename(selected_file))
            os.rename(selected_file, rejected_path)
            st.warning(f"Moved to {rejected_path}")
            st.rerun()


if __name__ == "__main__":
    main()