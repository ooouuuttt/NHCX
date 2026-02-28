
import os
import json
import logging
from extractor.pdf import extract_text
from llm.openai_llm import extract_insurance_data
from mapper.nhcx_mapper import map_to_fhir
from utils.logger import setup_logging

# Setup logging to console
setup_logging()
logger = logging.getLogger(__name__)

def test_single_pdf(file_path):
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        return

    print(f"--- Testing Single PDF: {os.path.basename(file_path)} ---")
    
    # 1. Extract Text
    print("1. Extracting text from PDF...")
    text = extract_text(file_path)
    
    # 2. LLM Extraction
    print("2. Extracting structured JSON using LLM...")
    data = extract_insurance_data(text)
    
    # 3. NHCX Mapping
    print("3. Mapping to NHCX FHIR Bundle...")
    bundle = map_to_fhir(data)
    
    # 4. Success Output
    print("\n" + "="*50)
    print("FINAL NHCX FHIR BUNDLE JSON:")
    print("="*50)
    json_result = json.dumps(bundle, indent=2, ensure_ascii=False)
    print(json_result)
    print("="*50)

    output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_result.json")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(json_result)
    print(f"Result saved to {output_file}")
    print(f"Result saved to test_result.json")

if __name__ == "__main__":
    # Selected ICICI Lombard_02.pdf for testing PA rules
    target_pdf = r"d:\Downloads Amit\Programming\NHCX(updated)\NHCX(updated)\NHCX\input_pdfs\pdfs\Aditya Birla(G)_03.pdf"
    test_single_pdf(target_pdf)
