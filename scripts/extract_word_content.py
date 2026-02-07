"""
Script para extraer contenido de documentos Word (.doc y .docx)
para análisis de patrones en certificaciones PGN
"""
import os
import sys
import json

# Intentar usar python-docx para archivos .docx
try:
    from docx import Document
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False
    print("NOTA: python-docx no está instalado. Instalar con: pip install python-docx")

# Para archivos .doc usaremos win32com en Windows
try:
    import win32com.client
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False
    print("NOTA: pywin32 no está instalado. Instalar con: pip install pywin32")


def extract_docx(filepath):
    """Extrae texto de archivo .docx"""
    if not HAS_DOCX:
        return None
    try:
        doc = Document(filepath)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return '\n'.join(full_text)
    except Exception as e:
        return f"ERROR: {str(e)}"


def extract_doc(filepath):
    """Extrae texto de archivo .doc usando COM"""
    if not HAS_WIN32:
        return None
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(filepath)
        text = doc.Content.Text
        doc.Close(False)
        word.Quit()
        return text
    except Exception as e:
        return f"ERROR: {str(e)}"


def extract_word_content(filepath):
    """Extrae contenido de archivo Word (.doc o .docx)"""
    filepath = os.path.abspath(filepath)
    if not os.path.exists(filepath):
        return f"Archivo no encontrado: {filepath}"
    
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext == '.docx':
        return extract_docx(filepath)
    elif ext == '.doc':
        return extract_doc(filepath)
    else:
        return f"Extensión no soportada: {ext}"


def analyze_samples(base_dir, samples_per_year=5):
    """Analiza muestras de certificaciones por año"""
    years = ['2007', '2010', '2011', '2012', '2013', '2014', '2015']
    
    results = {}
    
    for year in years:
        year_dir = os.path.join(base_dir, year)
        if not os.path.exists(year_dir):
            print(f"Directorio no encontrado: {year_dir}")
            continue
        
        # Obtener archivos Word (excluyendo ~ y copias)
        files = [f for f in os.listdir(year_dir) 
                 if (f.endswith('.doc') or f.endswith('.docx'))
                 and not f.startswith('~')
                 and 'copia' not in f.lower()]
        
        # Tomar muestra
        sample_files = files[:samples_per_year]
        
        results[year] = []
        
        for filename in sample_files:
            filepath = os.path.join(year_dir, filename)
            content = extract_word_content(filepath)
            if content:
                results[year].append({
                    'filename': filename,
                    'content': content
                })
    
    return results


if __name__ == "__main__":
    base_dir = r"C:\temp\PNG_CERTIFICADO_V3\Certificaciones"
    results = analyze_samples(base_dir, samples_per_year=5)
    
    # Guardar resultados como JSON
    output_file = r"C:\temp\PNG_CERTIFICADO_V3\extraction_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"Resultados guardados en: {output_file}")
    print(f"Total de años procesados: {len(results)}")
    for year, docs in results.items():
        print(f"  {year}: {len(docs)} documentos")
