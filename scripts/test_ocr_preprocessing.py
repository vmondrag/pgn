"""
Script de prueba para comparar modos de preprocesamiento OCR
Prueba diferentes técnicas en la Resolución 751 de 2023
"""
import os
import sys
import base64
import requests
import time

# Forzar UTF-8
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Importar funciones del script principal
sys.path.insert(0, r'c:\temp\PNG_CERTIFICADO_V3')
from extract_resoluciones import preprocess_image_for_ocr, HAS_FITZ

if HAS_FITZ:
    import fitz

# Configuración OCR Docker
OCR_HOST = "localhost"
OCR_PORT = 8000

# PDF de prueba - usar resolución con múltiples funcionarios (tiene tablas)
PDF_PATH = r"C:\temp\PNG_CERTIFICADO_V3\Decretos\RESOLUCIONES 2024\RESOLUCION 085 DE 01 DE MARZO DE  2024 WILLIAM SAMUEL WILCHES VILLAMARIN Y OTROS.pdf"


def render_page_raw(pdf_path: str, page_index: int, dpi: int = 300) -> bytes:
    """Renderiza página a bytes PNG sin procesar"""
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img_bytes = pix.tobytes("png")
    doc.close()
    return img_bytes


def ocr_with_docker(img_base64: str) -> dict:
    """Envía imagen a Docker PaddleOCR (NIM format)"""
    url = f"http://{OCR_HOST}:{OCR_PORT}/v1/infer"
    # Formato NIM PaddleOCR: data URL con prefijo
    data_url = f"data:image/png;base64,{img_base64}"
    payload = {"input": [{"type": "image_url", "url": data_url}]}

    try:
        response = requests.post(url, json=payload, timeout=60)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Status {response.status_code}: {response.text[:200]}"}
    except Exception as e:
        return {"error": str(e)}


def extract_text_from_ocr_result(result: dict) -> str:
    """Extrae texto del resultado OCR (formato NIM PaddleOCR)"""
    if "error" in result:
        return f"ERROR: {result['error']}"

    text_parts = []

    def _extract_recursive(obj):
        if isinstance(obj, dict):
            # Buscar campos de texto
            for key in ['text', 'transcription', 'rec_texts', 'content']:
                if key in obj:
                    val = obj[key]
                    if isinstance(val, str) and val.strip():
                        text_parts.append(val.strip())
                    elif isinstance(val, list):
                        for item in val:
                            if isinstance(item, str) and item.strip():
                                text_parts.append(item.strip())
                            else:
                                _extract_recursive(item)
            # Buscar text_prediction
            if 'text_prediction' in obj:
                pred = obj['text_prediction']
                if isinstance(pred, dict) and 'text' in pred:
                    text_parts.append(pred['text'])
            # Recurrir en valores
            for v in obj.values():
                if isinstance(v, (dict, list)):
                    _extract_recursive(v)
        elif isinstance(obj, list):
            for item in obj:
                _extract_recursive(item)

    _extract_recursive(result)
    return "\n".join(text_parts) if text_parts else ""


def test_preprocessing_modes(pdf_path: str, pages: list, modes: list):
    """
    Prueba diferentes modos de preprocesamiento en varias páginas
    """
    print("=" * 80)
    print(f"PRUEBA DE MODOS DE PREPROCESAMIENTO OCR")
    print(f"PDF: {os.path.basename(pdf_path)}")
    print("=" * 80)

    results = {}

    for page_idx in pages:
        print(f"\n{'='*60}")
        print(f"PÁGINA {page_idx + 1}")
        print("=" * 60)

        # Renderizar página original
        print(f"Renderizando página {page_idx + 1} a 300 DPI...")
        raw_bytes = render_page_raw(pdf_path, page_idx, dpi=300)
        raw_size = len(raw_bytes)
        print(f"  Tamaño imagen original: {raw_size:,} bytes")

        page_results = {}

        for mode in modes:
            print(f"\n  Modo: {mode.upper()}")
            print("  " + "-" * 40)

            # Preprocesar
            start_time = time.time()
            if mode == "none":
                processed_bytes = raw_bytes
            else:
                processed_bytes = preprocess_image_for_ocr(raw_bytes, mode=mode)
            preprocess_time = time.time() - start_time

            processed_size = len(processed_bytes)
            print(f"    Tamaño procesado: {processed_size:,} bytes")
            print(f"    Tiempo preprocesamiento: {preprocess_time:.2f}s")

            # Enviar a OCR
            img_base64 = base64.b64encode(processed_bytes).decode('utf-8')

            start_time = time.time()
            ocr_result = ocr_with_docker(img_base64)
            ocr_time = time.time() - start_time

            # Extraer texto
            text = extract_text_from_ocr_result(ocr_result)
            char_count = len(text)
            word_count = len(text.split())
            line_count = len(text.strip().split('\n'))

            print(f"    Tiempo OCR: {ocr_time:.2f}s")
            print(f"    Caracteres extraídos: {char_count:,}")
            print(f"    Palabras: {word_count:,}")
            print(f"    Líneas: {line_count}")

            # Mostrar muestra del texto
            sample = text[:500] if len(text) > 500 else text
            print(f"\n    Muestra de texto:")
            for line in sample.split('\n')[:10]:
                print(f"      {line[:80]}")

            page_results[mode] = {
                "chars": char_count,
                "words": word_count,
                "lines": line_count,
                "preprocess_time": preprocess_time,
                "ocr_time": ocr_time,
                "text": text
            }

        results[page_idx] = page_results

    # Resumen comparativo
    print("\n" + "=" * 80)
    print("RESUMEN COMPARATIVO")
    print("=" * 80)

    for page_idx in pages:
        print(f"\nPágina {page_idx + 1}:")
        print(f"  {'Modo':<12} {'Chars':>8} {'Words':>8} {'Lines':>6} {'Time':>8}")
        print("  " + "-" * 50)

        page_data = results[page_idx]
        best_chars = max(page_data.values(), key=lambda x: x["chars"])["chars"]

        for mode in modes:
            data = page_data[mode]
            total_time = data["preprocess_time"] + data["ocr_time"]
            marker = " *" if data["chars"] == best_chars else ""
            print(f"  {mode:<12} {data['chars']:>8,} {data['words']:>8,} {data['lines']:>6} {total_time:>7.2f}s{marker}")

    print("\n* = Mayor cantidad de caracteres extraídos")

    return results


def test_dpi_variations(pdf_path: str, page_idx: int, dpis: list, mode: str = "none"):
    """
    Prueba diferentes valores de DPI
    """
    print("\n" + "=" * 80)
    print(f"PRUEBA DE VARIACIONES DE DPI")
    print(f"PDF: {os.path.basename(pdf_path)}, Página {page_idx + 1}")
    print(f"Modo de preprocesamiento: {mode}")
    print("=" * 80)

    results = {}

    for dpi in dpis:
        print(f"\n  DPI: {dpi}")
        print("  " + "-" * 40)

        # Renderizar
        raw_bytes = render_page_raw(pdf_path, page_idx, dpi=dpi)

        # Preprocesar si es necesario
        if mode != "none":
            processed_bytes = preprocess_image_for_ocr(raw_bytes, mode=mode)
        else:
            processed_bytes = raw_bytes

        print(f"    Tamaño imagen: {len(processed_bytes):,} bytes")

        # OCR
        img_base64 = base64.b64encode(processed_bytes).decode('utf-8')
        start_time = time.time()
        ocr_result = ocr_with_docker(img_base64)
        ocr_time = time.time() - start_time

        text = extract_text_from_ocr_result(ocr_result)

        print(f"    Tiempo OCR: {ocr_time:.2f}s")
        print(f"    Caracteres: {len(text):,}")
        print(f"    Palabras: {len(text.split()):,}")

        results[dpi] = {
            "chars": len(text),
            "words": len(text.split()),
            "time": ocr_time,
            "text": text
        }

    # Resumen
    print("\n  Resumen DPI:")
    print(f"  {'DPI':>6} {'Chars':>10} {'Words':>8} {'Time':>8}")
    print("  " + "-" * 40)
    for dpi in dpis:
        data = results[dpi]
        print(f"  {dpi:>6} {data['chars']:>10,} {data['words']:>8,} {data['time']:>7.2f}s")

    return results


if __name__ == "__main__":
    if not HAS_FITZ:
        print("ERROR: PyMuPDF no está instalado")
        sys.exit(1)

    if not os.path.exists(PDF_PATH):
        print(f"ERROR: No se encuentra el archivo: {PDF_PATH}")
        sys.exit(1)

    # Verificar conexión OCR Docker
    print("Verificando conexión con Docker PaddleOCR...")
    try:
        response = requests.get(f"http://{OCR_HOST}:{OCR_PORT}/v1/health", timeout=5)
        print(f"  Estado: OK (código {response.status_code})")
    except Exception as e:
        print(f"  ERROR: No se puede conectar al OCR Docker: {e}")
        print("  Asegúrese de que el contenedor esté corriendo:")
        print("  docker run -it --rm --gpus all -p 8000:8000 nvcr.io/nim/baai/paddleocr:latest")
        sys.exit(1)

    # Probar modos de preprocesamiento en páginas con tablas (2-5)
    # Página 1 es la primera página con texto normal
    # Páginas 2-5 contienen las tablas con los datos

    print("\n" + "=" * 80)
    print("INICIANDO PRUEBAS")
    print("=" * 80)

    # Test 1: Comparar modos de preprocesamiento
    modes = ["none", "grayscale", "contrast", "enhanced"]
    pages_to_test = [1, 2, 3]  # Páginas 2, 3, 4 (índice 0-based)

    results = test_preprocessing_modes(PDF_PATH, pages_to_test, modes)

    # Test 2: Variación de DPI en página con tabla
    print("\n\n")
    dpi_results = test_dpi_variations(PDF_PATH, page_idx=2, dpis=[150, 200, 300, 400], mode="none")

    print("\n" + "=" * 80)
    print("PRUEBAS COMPLETADAS")
    print("=" * 80)
