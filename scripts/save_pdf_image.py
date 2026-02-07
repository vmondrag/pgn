"""
Guardar imagen renderizada del PDF para análisis visual
"""
import fitz
import os

pdf_path = r"C:\temp\PNG_CERTIFICADO_V3\Decretos\2009\DECRETO 001-2009.pdf"
output_dir = r"C:\temp\PNG_CERTIFICADO_V3\output_2009_ocr"

doc = fitz.open(pdf_path)
page = doc[0]

# Guardar a diferentes DPIs
for dpi in [150, 300]:
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    output_path = os.path.join(output_dir, f"DECRETO_001_2009_DPI{dpi}.png")
    pix.save(output_path)
    print(f"Guardado: {output_path} ({pix.width}x{pix.height})")

# Extraer texto nativo para comparar
text = page.get_text()
print(f"\nTexto nativo del PDF ({len(text)} chars):")
print("="*50)
print(text[:800])

doc.close()
