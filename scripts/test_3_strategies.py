"""
Prueba de 3 estrategias de extracción de decretos:
1. OCR DPI 150 + LLM para fechas
2. OCR con preprocesamiento de imagen (contraste, binarización)
3. Híbrido: OCR + extracción de metadata del filename
"""
import os
import re
import json
import base64
import requests
import fitz  # PyMuPDF
from datetime import datetime
from typing import Dict, Optional, Tuple

# Intentar importar PIL para preprocesamiento
try:
    from PIL import Image, ImageEnhance, ImageFilter
    import io
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("ADVERTENCIA: PIL no disponible. Instalando...")
    os.system("pip install pillow")
    from PIL import Image, ImageEnhance, ImageFilter
    import io
    HAS_PIL = True

# Configuración
OCR_HOST = "localhost"
OCR_PORT = 8000
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gpt-oss:20b-cloud"
OUTPUT_DIR = r"C:\temp\PNG_CERTIFICADO_V3\output_2009_test_strategies"


def ensure_dir(path: str):
    if not os.path.exists(path):
        os.makedirs(path)


# =============================================================================
# ESTRATEGIA 1: OCR DPI 150 + LLM
# =============================================================================

def render_page_to_bytes(pdf_path: str, page_index: int = 0, dpi: int = 150) -> bytes:
    """Renderiza página PDF a bytes PNG"""
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    doc.close()
    return img_bytes


def ocr_from_bytes(img_bytes: bytes, timeout: int = 120) -> Optional[str]:
    """OCR desde bytes de imagen"""
    b64 = base64.b64encode(img_bytes).decode('utf-8')
    data_url = f"data:image/png;base64,{b64}"
    
    try:
        url = f"http://{OCR_HOST}:{OCR_PORT}/v1/infer"
        payload = {"input": [{"type": "image_url", "url": data_url}]}
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        
        result = response.json()
        texts = []
        _extract_texts(result, texts)
        return '\n'.join(texts)
    except Exception as e:
        print(f"Error OCR: {e}")
        return None


def _extract_texts(obj, texts: list):
    if isinstance(obj, dict):
        for key in ['text', 'transcription', 'rec_texts', 'content']:
            if key in obj:
                val = obj[key]
                if isinstance(val, str) and val.strip():
                    texts.append(val.strip())
                elif isinstance(val, list):
                    for item in val:
                        if isinstance(item, str) and item.strip():
                            texts.append(item.strip())
                        else:
                            _extract_texts(item, texts)
        for v in obj.values():
            if isinstance(v, (dict, list)):
                _extract_texts(v, texts)
    elif isinstance(obj, list):
        for item in obj:
            _extract_texts(item, texts)


def strategy_1_ocr_dpi150(pdf_path: str) -> Dict:
    """Estrategia 1: OCR simple DPI 150"""
    img_bytes = render_page_to_bytes(pdf_path, dpi=150)
    text = ocr_from_bytes(img_bytes)
    return {
        'strategy': 'OCR_DPI150',
        'text': text or '',
        'chars': len(text) if text else 0,
        'success': text is not None and len(text) > 100
    }


# =============================================================================
# ESTRATEGIA 2: OCR con preprocesamiento de imagen
# =============================================================================

def preprocess_image(img_bytes: bytes) -> bytes:
    """Preprocesa imagen para mejorar OCR: contraste, nitidez, binarización"""
    # Cargar imagen
    img = Image.open(io.BytesIO(img_bytes))
    
    # Convertir a escala de grises
    if img.mode != 'L':
        img = img.convert('L')
    
    # Aumentar contraste
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.5)
    
    # Aumentar nitidez
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(2.0)
    
    # Aplicar umbral (binarización simple)
    # Convertir a blanco y negro puro
    threshold = 128
    img = img.point(lambda p: 255 if p > threshold else 0)
    
    # Convertir de vuelta a RGB para el OCR
    img = img.convert('RGB')
    
    # Guardar a bytes
    output = io.BytesIO()
    img.save(output, format='PNG')
    return output.getvalue()


def strategy_2_ocr_preprocessed(pdf_path: str) -> Dict:
    """Estrategia 2: OCR con preprocesamiento de imagen"""
    img_bytes = render_page_to_bytes(pdf_path, dpi=200)  # DPI un poco mayor
    
    # Preprocesar
    processed_bytes = preprocess_image(img_bytes)
    
    # OCR
    text = ocr_from_bytes(processed_bytes)
    
    return {
        'strategy': 'OCR_PREPROCESSED',
        'text': text or '',
        'chars': len(text) if text else 0,
        'success': text is not None and len(text) > 100
    }


# =============================================================================
# ESTRATEGIA 3: Híbrido OCR + Filename extraction
# =============================================================================

def extract_from_filename(filename: str) -> Dict:
    """Extrae número de decreto y año del nombre del archivo"""
    result = {'numero_decreto': None, 'anio': None}
    
    # Patrón: DECRETO 001-2009.pdf o similar
    match = re.search(r'(\d{1,5})[\s_-]+(\d{4})', filename)
    if match:
        result['numero_decreto'] = match.group(1)
        result['anio'] = int(match.group(2))
    
    return result


def extract_with_llm_simple(text: str, filename_info: Dict) -> Dict:
    """Usa LLM para extraer datos estructurados del texto OCR"""
    
    prompt = f"""Analiza el siguiente texto de un decreto y extrae la información.
El archivo se llama: contiene decreto #{filename_info.get('numero_decreto')} del año {filename_info.get('anio')}.

TEXTO DEL DOCUMENTO:
{text[:4000]}

Extrae en formato JSON:
{{
    "numero_decreto": "número del decreto (usa {filename_info.get('numero_decreto')} si no es claro)",
    "anio": {filename_info.get('anio') or 2009},
    "fecha_texto": "fecha completa si aparece",
    "dia": null,
    "mes": null,
    "tipo_novedad": "N=Nombramiento, R=Renuncia, E=Encargo, etc",
    "funcionario": {{
        "cedula": "número de cédula",
        "nombre": "nombre completo",
        "cargo": "cargo del funcionario"
    }},
    "resumen": "resumen breve del decreto"
}}

Responde SOLO con JSON válido:"""

    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 1500}
        }
        
        response = requests.post(OLLAMA_URL, json=payload, timeout=90)
        if response.status_code == 200:
            resp_text = response.json().get('response', '')
            # Extraer JSON
            match = re.search(r'\{[\s\S]*\}', resp_text)
            if match:
                return json.loads(match.group())
    except Exception as e:
        print(f"Error LLM: {e}")
    
    return {}


def strategy_3_hybrid(pdf_path: str) -> Dict:
    """Estrategia 3: Híbrido OCR + filename + LLM"""
    filename = os.path.basename(pdf_path)
    
    # Extraer metadata del filename
    filename_info = extract_from_filename(filename)
    
    # OCR
    img_bytes = render_page_to_bytes(pdf_path, dpi=150)
    text = ocr_from_bytes(img_bytes)
    
    # LLM para estructurar
    structured = extract_with_llm_simple(text or '', filename_info)
    
    return {
        'strategy': 'HYBRID',
        'text': text or '',
        'chars': len(text) if text else 0,
        'filename_info': filename_info,
        'llm_structured': structured,
        'success': bool(structured)
    }


# =============================================================================
# COMPARACIÓN
# =============================================================================

def compare_strategies(pdf_path: str) -> Dict:
    """Compara las 3 estrategias para un archivo"""
    filename = os.path.basename(pdf_path)
    print(f"\nProcesando: {filename}")
    print("-" * 50)
    
    results = {'filename': filename}
    
    # Estrategia 1
    print("  [1] OCR DPI 150...", end=" ", flush=True)
    r1 = strategy_1_ocr_dpi150(pdf_path)
    results['strategy_1'] = r1
    print(f"{r1['chars']} chars")
    
    # Estrategia 2
    print("  [2] OCR Preprocesado...", end=" ", flush=True)
    r2 = strategy_2_ocr_preprocessed(pdf_path)
    results['strategy_2'] = r2
    print(f"{r2['chars']} chars")
    
    # Estrategia 3
    print("  [3] Híbrido + LLM...", end=" ", flush=True)
    r3 = strategy_3_hybrid(pdf_path)
    results['strategy_3'] = r3
    llm_ok = "✓" if r3['llm_structured'] else "✗"
    print(f"{r3['chars']} chars, LLM: {llm_ok}")
    
    return results


def generate_comparison_report(all_results: list, output_path: str):
    """Genera reporte comparativo"""
    md = []
    md.append("# Comparación de 3 Estrategias de Extracción\n")
    md.append(f"**Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    md.append("\n## Resumen de Estrategias\n")
    md.append("| Estrategia | Descripción |")
    md.append("|------------|-------------|")
    md.append("| **1. OCR DPI 150** | OCR directo con resolución baja |")
    md.append("| **2. OCR Preprocesado** | OCR con mejora de contraste y binarización |")
    md.append("| **3. Híbrido + LLM** | OCR + metadata filename + estructuración con LLM |")
    
    md.append("\n## Resultados por Archivo\n")
    md.append("| Archivo | E1 chars | E2 chars | E3 chars | E3 LLM OK |")
    md.append("|---------|----------|----------|----------|-----------|")
    
    for r in all_results:
        fn = r['filename'][:25]
        c1 = r['strategy_1']['chars']
        c2 = r['strategy_2']['chars']
        c3 = r['strategy_3']['chars']
        llm = "✓" if r['strategy_3'].get('llm_structured') else "✗"
        md.append(f"| {fn} | {c1} | {c2} | {c3} | {llm} |")
    
    # Detalle de estrategia 3 (híbrido)
    md.append("\n## Detalle Estrategia Híbrida (E3)\n")
    for r in all_results:
        fn = r['filename']
        llm = r['strategy_3'].get('llm_structured', {})
        if llm:
            md.append(f"\n### {fn}\n")
            md.append("```json")
            md.append(json.dumps(llm, indent=2, ensure_ascii=False, default=str)[:1000])
            md.append("```")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md))
    
    print(f"\nReporte: {output_path}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir-in', default=r"C:\temp\PNG_CERTIFICADO_V3\Decretos\2009")
    parser.add_argument('--limit', type=int, default=5)
    args = parser.parse_args()
    
    print("=" * 60)
    print("COMPARACIÓN DE 3 ESTRATEGIAS DE EXTRACCIÓN")
    print("=" * 60)
    
    ensure_dir(OUTPUT_DIR)
    
    # Buscar PDFs
    pdf_files = sorted([
        os.path.join(args.dir_in, f) 
        for f in os.listdir(args.dir_in) 
        if f.lower().endswith('.pdf')
    ])[:args.limit]
    
    print(f"\nArchivos a procesar: {len(pdf_files)}")
    
    all_results = []
    for pdf_path in pdf_files:
        result = compare_strategies(pdf_path)
        all_results.append(result)
    
    # Guardar resultados
    json_path = os.path.join(OUTPUT_DIR, 'comparison_all_strategies.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
    
    # Generar reporte
    report_path = os.path.join(OUTPUT_DIR, 'comparison_strategies_report.md')
    generate_comparison_report(all_results, report_path)
    
    print("\n" + "=" * 60)
    print("COMPLETADO")
    print(f"Resultados en: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
