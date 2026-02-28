import sys
sys.path.insert(0, r"d:\Downloads Amit\Programming\NHCX(updated)\NHCX(updated)\NHCX")
from extractor.pdf import extract_text

t = extract_text(r"d:\Downloads Amit\Programming\NHCX(updated)\NHCX(updated)\NHCX\input_pdfs\pdfs\ICICI Lombard_02.pdf")
lines = t.split("\n")

with open("pdf_analysis.txt", "w", encoding="utf-8") as f:
    f.write("=== FIRST 60 LINES ===\n")
    for i, line in enumerate(lines[:60]):
        f.write(f"{i+1}: {line}\n")

    f.write("\n=== SEARCHING FOR 'family shield' ===\n")
    for i, line in enumerate(lines):
        if "family shield" in line.lower():
            f.write(f"  Line {i+1}: {line}\n")

    f.write("\n=== SEARCHING FOR 'shield' ===\n")
    for i, line in enumerate(lines):
        if "shield" in line.lower():
            f.write(f"  Line {i+1}: {line}\n")

    f.write("\n=== SEARCHING FOR 'product name' or 'plan name' ===\n")
    for i, line in enumerate(lines):
        if "product name" in line.lower() or "plan name" in line.lower():
            f.write(f"  Line {i+1}: {line}\n")

    f.write("\n=== SEARCHING FOR UIN ===\n")
    for i, line in enumerate(lines):
        if "uin" in line.lower() or "icihlip" in line.lower():
            f.write(f"  Line {i+1}: {line}\n")

print("Done! Check pdf_analysis.txt")
