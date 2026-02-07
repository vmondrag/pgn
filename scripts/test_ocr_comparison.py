"""
Prueba de extracción SOLO con OCR (forzando OCR incluso en PDFs con texto nativo)
Para comparar calidad OCR vs extracción nativa
"""
import os
import json
import base64
import sqlite3
import requests
from datetime import datetime
from typing import Dict, Optional

# Configuración
DB_PATH = r"C:\temp\PNG_CERTIFICADO_V3\novedades_pgn.db"
DEFAULT_DIR = r"C:\temp\PNG_CERTIFICADO_V3\Decretos\2009"
OUTPUT_DIR = r"C:\temp\PNG_CERTIFICADO_V3\output_2009_ocr"
OCR_HOST = "localhost"
OCR_PORT = 8000
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gpt-oss:20b-cloud"

try:
    import fitz
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False
    print("ERROR: PyMuPDF no instalado")


def ensure_dir(path: str):
    if not os.path.exists(path):
        os.makedirs(path)


def render_page_to_base64(pdf_path: str, page_index: int = 0, dpi: int = 300) -> Optional[str]:
    """Renderiza página PDF a imagen base64 para OCR"""
    try:
        doc = fitz.open(pdf_path)
        page = doc[page_index]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        doc.close()
        
        b64 = base64.b64encode(img_bytes).decode('utf-8')
        return f"data:image/png;base64,{b64}"
    except Exception as e:
        print(f"Error renderizando: {e}")
        return None


def ocr_with_nim(data_url: str, timeout: int = 120) -> Optional[str]:
    """Realiza OCR usando NIM PaddleOCR"""
    try:
        url = f"http://{OCR_HOST}:{OCR_PORT}/v1/infer"
        payload = {"input": [{"type": "image_url", "url": data_url}]}
        
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        
        result = response.json()
        text_parts = []
        _extract_ocr_text(result, text_parts)
        
        return '\n'.join(text_parts)
    except requests.exceptions.ConnectionError:
        print("Error: No se puede conectar a NIM PaddleOCR")
        return None
    except Exception as e:
        print(f"Error en OCR: {e}")
        return None


def _extract_ocr_text(obj, texts: list):
    """Extrae texto recursivamente de respuesta OCR"""
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
                            _extract_ocr_text(item, texts)
        for v in obj.values():
            if isinstance(v, (dict, list)):
                _extract_ocr_text(v, texts)
    elif isinstance(obj, list):
        for item in obj:
            _extract_ocr_text(item, texts)


def extract_text_native(pdf_path: str) -> Optional[str]:
    """Extrae texto nativo del PDF"""
    try:
        doc = fitz.open(pdf_path)
        full_text = []
        for page in doc:
            text = page.get_text()
            full_text.append(text)
        doc.close()
        return '\n'.join(full_text)
    except:
        return None


def extract_text_ocr_only(pdf_path: str, max_pages: int = 5) -> Optional[str]:
    """Extrae texto SOLO con OCR (ignora texto nativo)"""
    try:
        doc = fitz.open(pdf_path)
        num_pages = min(len(doc), max_pages)
        doc.close()
        
        all_text = []
        for i in range(num_pages):
            data_url = render_page_to_base64(pdf_path, i)
            if data_url:
                page_text = ocr_with_nim(data_url)
                if page_text:
                    all_text.append(f"--- Página {i+1} ---\n{page_text}")
        
        if all_text:
            return '\n'.join(all_text)
        return None
    except Exception as e:
        print(f"Error OCR: {e}")
        return None


def query_ollama(prompt: str, system_prompt: str = None) -> Optional[str]:
    """Consulta al modelo LLM via Ollama"""
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 2000}
        }
        if system_prompt:
            payload["system"] = system_prompt
        
        response = requests.post(OLLAMA_URL, json=payload, timeout=90)
        if response.status_code == 200:
            return response.json().get('response', '')
        return None
    except:
        return None


def compare_extraction(filepath: str) -> Dict:
    """Compara extracción nativa vs OCR para un archivo"""
    filename = os.path.basename(filepath)
    result = {
        'filename': filename,
        'native': {'text': '', 'chars': 0, 'success': False},
        'ocr': {'text': '', 'chars': 0, 'success': False},
        'comparison': {}
    }
    
    # 1. Extracción Nativa
    native_text = extract_text_native(filepath)
    if native_text:
        result['native']['text'] = native_text
        result['native']['chars'] = len(native_text)
        result['native']['success'] = True
    
    # 2. Extracción OCR
    ocr_text = extract_text_ocr_only(filepath)
    if ocr_text:
        result['ocr']['text'] = ocr_text
        result['ocr']['chars'] = len(ocr_text)
        result['ocr']['success'] = True
    
    # 3. Comparación
    result['comparison']['native_chars'] = result['native']['chars']
    result['comparison']['ocr_chars'] = result['ocr']['chars']
    result['comparison']['ratio'] = (
        result['ocr']['chars'] / result['native']['chars'] 
        if result['native']['chars'] > 0 else 0
    )
    
    return result


def generate_comparison_report(results: list, output_path: str):
    """Genera reporte de comparación"""
    md = []
    md.append("# Comparación Extracción NATIVA vs OCR - Decretos 2009\n")
    md.append(f"**Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    md.append(f"**Total archivos:** {len(results)}\n")
    
    md.append("\n## Resumen\n")
    native_ok = sum(1 for r in results if r['native']['success'])
    ocr_ok = sum(1 for r in results if r['ocr']['success'])
    avg_ratio = sum(r['comparison']['ratio'] for r in results) / len(results) if results else 0
    
    md.append(f"| Métrica | Valor |")
    md.append(f"|---------|-------|")
    md.append(f"| Extracción Nativa OK | {native_ok} |")
    md.append(f"| Extracción OCR OK | {ocr_ok} |")
    md.append(f"| Ratio promedio OCR/Nativo | {avg_ratio:.2f} |")
    
    md.append("\n## Detalle por Archivo\n")
    md.append("| # | Archivo | Nativo (chars) | OCR (chars) | Ratio | Mejor |")
    md.append("|---|---------|----------------|-------------|-------|-------|")
    
    for i, r in enumerate(results, 1):
        filename = r['filename'][:25]
        native = r['native']['chars']
        ocr = r['ocr']['chars']
        ratio = r['comparison']['ratio']
        mejor = "OCR" if ocr > native * 1.1 else "NATIVO" if native > ocr * 1.1 else "≈"
        md.append(f"| {i} | {filename} | {native:,} | {ocr:,} | {ratio:.2f} | {mejor} |")
    
    md.append("\n## Textos de Muestra (Primer Archivo)\n")
    if results:
        r = results[0]
        md.append(f"### Texto NATIVO ({r['native']['chars']} chars)\n```text")
        md.append(r['native']['text'][:1500])
        md.append("```\n")
        md.append(f"### Texto OCR ({r['ocr']['chars']} chars)\n```text")
        md.append(r['ocr']['text'][:1500])
        md.append("```\n")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md))
    
    print(f"\nReporte generado: {output_path}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Comparar extracción Nativa vs OCR')
    parser.add_argument('--dir-in', type=str, default=DEFAULT_DIR)
    parser.add_argument('--output-dir', type=str, default=OUTPUT_DIR)
    parser.add_argument('--limit', type=int, default=5, help='Número de archivos a comparar')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("COMPARACIÓN EXTRACCIÓN NATIVA VS OCR")
    print("=" * 60)
    print(f"Directorio: {args.dir_in}")
    print(f"Límite: {args.limit} archivos")
    print()
    
    # Verificar OCR
    print("Verificando servicio OCR...")
    try:
        resp = requests.get(f"http://{OCR_HOST}:{OCR_PORT}/v1/health/ready", timeout=5)
        if resp.status_code == 200:
            print("  OCR: OK")
        else:
            print("  OCR: NO DISPONIBLE")
            return
    except:
        print("  OCR: NO DISPONIBLE - Asegúrese de que NIM PaddleOCR esté corriendo")
        return
    
    ensure_dir(args.output_dir)
    
    # Buscar PDFs
    pdf_files = []
    for f in sorted(os.listdir(args.dir_in)):
        if f.lower().endswith('.pdf'):
            pdf_files.append(os.path.join(args.dir_in, f))
    
    pdf_files = pdf_files[:args.limit]
    print(f"\nProcesando {len(pdf_files)} archivos...\n")
    
    results = []
    for i, filepath in enumerate(pdf_files):
        filename = os.path.basename(filepath)
        print(f"[{i+1}/{len(pdf_files)}] {filename[:40]}...", end=" ", flush=True)
        
        result = compare_extraction(filepath)
        results.append(result)
        
        print(f"NATIVO:{result['native']['chars']:,} | OCR:{result['ocr']['chars']:,}")
    
    # Guardar resultados JSON
    json_path = os.path.join(args.output_dir, 'comparison_results.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        # No guardar textos completos para reducir tamaño
        results_summary = [
            {
                'filename': r['filename'],
                'native_chars': r['native']['chars'],
                'ocr_chars': r['ocr']['chars'],
                'ratio': r['comparison']['ratio']
            }
            for r in results
        ]
        json.dump(results_summary, f, indent=2, ensure_ascii=False)
    
    # Guardar textos individuales
    for r in results:
        base = r['filename'].replace('.pdf', '').replace('.PDF', '')
        
        # Texto nativo
        native_path = os.path.join(args.output_dir, f"{base}_NATIVO.txt")
        with open(native_path, 'w', encoding='utf-8') as f:
            f.write(r['native']['text'])
        
        # Texto OCR
        ocr_path = os.path.join(args.output_dir, f"{base}_OCR.txt")
        with open(ocr_path, 'w', encoding='utf-8') as f:
            f.write(r['ocr']['text'])
    
    # Generar reporte comparativo
    report_path = os.path.join(args.output_dir, 'comparison_report.md')
    generate_comparison_report(results, report_path)
    
    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"Archivos procesados: {len(results)}")
    print(f"Directorio salida: {args.output_dir}")


if __name__ == "__main__":
    main()
