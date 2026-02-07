"""
Script para analizar patrones de certificaciones por año.
Extrae muestras de 10 archivos por año y analiza el contenido.
"""
import os
import sys
from pathlib import Path
import random

# Agregar directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Intentar importar funciones de extracción
try:
    from extract_decretos import extract_pdf_text, extract_text_native
    HAS_EXTRACT = True
except ImportError:
    HAS_EXTRACT = False

BASE_DIR = Path(r"C:\temp\PNG_CERTIFICADO_V3\Certificaciones")
SAMPLES_PER_YEAR = 10

def count_files_by_year():
    """Cuenta archivos PDF por año"""
    years = sorted([d for d in os.listdir(BASE_DIR) if d.isdigit()])
    counts = {}
    for year in years:
        year_dir = BASE_DIR / year
        pdfs = list(year_dir.glob("*.pdf"))
        counts[year] = len(pdfs)
    return counts

def get_sample_files(year, n=10):
    """Obtiene n archivos de muestra de un año"""
    year_dir = BASE_DIR / year
    pdfs = list(year_dir.glob("*.pdf"))
    if len(pdfs) <= n:
        return pdfs
    return random.sample(pdfs, n)

def analyze_filename(filename):
    """Analiza patrones en el nombre del archivo"""
    name = filename.replace(".pdf", "")
    patterns = {
        "tiene_cedula": any(c.isdigit() for c in name),
        "tiene_nombre": any(c.isalpha() for c in name),
        "longitud": len(name),
        "palabras": len(name.split()),
    }
    return patterns

def extract_sample_text(pdf_path, max_chars=500):
    """Extrae texto de muestra del PDF"""
    if not HAS_EXTRACT:
        return None, "NO_EXTRACT_MODULE"
    
    try:
        text, method = extract_pdf_text(str(pdf_path))
        if text:
            return text[:max_chars], method
        return None, method
    except Exception as e:
        return None, str(e)

def main():
    print("=" * 70)
    print("ANÁLISIS DE CERTIFICACIONES POR AÑO")
    print("=" * 70)
    
    # Contar archivos por año
    counts = count_files_by_year()
    
    print("\n1. CONTEO DE ARCHIVOS POR AÑO")
    print("-" * 40)
    total = 0
    for year, count in sorted(counts.items()):
        total += count
        print(f"  {year}: {count:>6} PDFs")
    print("-" * 40)
    print(f"  TOTAL: {total:>6} PDFs")
    
    # Analizar nombres de archivos por año
    print("\n2. ANÁLISIS DE NOMBRES DE ARCHIVOS (10 muestras/año)")
    print("-" * 70)
    
    filename_patterns = {}
    for year in sorted(counts.keys()):
        samples = get_sample_files(year, SAMPLES_PER_YEAR)
        year_patterns = []
        for pdf in samples:
            pattern = analyze_filename(pdf.name)
            year_patterns.append(pattern)
        
        if year_patterns:
            avg_length = sum(p["longitud"] for p in year_patterns) / len(year_patterns)
            avg_words = sum(p["palabras"] for p in year_patterns) / len(year_patterns)
            has_cedula_pct = sum(1 for p in year_patterns if p["tiene_cedula"]) / len(year_patterns) * 100
            
            filename_patterns[year] = {
                "avg_length": avg_length,
                "avg_words": avg_words,
                "has_cedula_pct": has_cedula_pct,
            }
            
            print(f"  {year}: Long.prom={avg_length:.0f}, Palabras.prom={avg_words:.1f}, Con cédula={has_cedula_pct:.0f}%")
    
    # Mostrar ejemplos de nombres por año
    print("\n3. EJEMPLOS DE NOMBRES POR AÑO")
    print("-" * 70)
    for year in sorted(counts.keys()):
        samples = get_sample_files(year, 3)
        print(f"\n  {year}:")
        for pdf in samples:
            print(f"    - {pdf.name[:60]}")
    
    # Analizar contenido de muestras (si hay módulo de extracción)
    if HAS_EXTRACT:
        print("\n4. ANÁLISIS DE CONTENIDO (2 muestras/año)")
        print("-" * 70)
        
        for year in sorted(counts.keys()):
            samples = get_sample_files(year, 2)
            print(f"\n  {year}:")
            for pdf in samples:
                text, method = extract_sample_text(pdf, 300)
                if text:
                    # Buscar patrones en el texto
                    text_lower = text.lower()
                    has_certifica = "certifica" in text_lower
                    has_funcionario = "funcionario" in text_lower or "servidor" in text_lower
                    has_fecha = any(m in text_lower for m in ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"])
                    
                    print(f"    [{method}] {pdf.name[:40]}...")
                    print(f"      Contiene: CERTIFICA={has_certifica}, FUNCIONARIO={has_funcionario}, FECHA={has_fecha}")
                else:
                    print(f"    [ERROR] {pdf.name[:40]}: {method}")
    
    print("\n" + "=" * 70)
    print("ANÁLISIS COMPLETADO")
    print("=" * 70)

if __name__ == "__main__":
    main()
