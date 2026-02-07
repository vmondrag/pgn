"""
Diagnóstico de calidad OCR - Prueba con diferentes configuraciones
"""
import os
import base64
import requests
import fitz  # PyMuPDF

OCR_HOST = "localhost"
OCR_PORT = 8000

def render_page_to_base64(pdf_path: str, page_index: int = 0, dpi: int = 300):
    """Renderiza página PDF a imagen base64"""
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    doc.close()
    
    b64 = base64.b64encode(img_bytes).decode('utf-8')
    return f"data:image/png;base64,{b64}", len(img_bytes)


def ocr_with_nim(data_url: str, timeout: int = 180):
    """Realiza OCR usando NIM PaddleOCR"""
    url = f"http://{OCR_HOST}:{OCR_PORT}/v1/infer"
    payload = {"input": [{"type": "image_url", "url": data_url}]}
    
    response = requests.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    
    result = response.json()
    text_parts = []
    _extract_ocr_text(result, text_parts)
    
    return '\n'.join(text_parts), result


def _extract_ocr_text(obj, texts: list):
    """Extrae texto recursivamente"""
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


def test_ocr_quality(pdf_path: str):
    """Prueba OCR con diferentes configuraciones de DPI"""
    
    print(f"\n{'='*60}")
    print(f"DIAGNÓSTICO OCR: {os.path.basename(pdf_path)}")
    print(f"{'='*60}\n")
    
    # Texto esperado (referencia)
    expected_text = """PROCURADURÍA GENERAL DE LA NACIÓN
DECRETO No. 001 de 2009
(17 de enero de 2009)
GONZALO ENRIQUE SIERRA VASCO
70.039.458
Bogotá, D.C., a los 17 de enero de 2009
EDGARDO JOSÉ MAYA VILLAZÓN"""
    
    print("TEXTO ESPERADO (referencia):")
    print("-" * 40)
    print(expected_text)
    print()
    
    # Probar diferentes DPIs
    for dpi in [150, 300, 400]:
        print(f"\n{'='*40}")
        print(f"DPI: {dpi}")
        print(f"{'='*40}")
        
        try:
            data_url, img_size = render_page_to_base64(pdf_path, 0, dpi)
            print(f"Tamaño imagen: {img_size:,} bytes")
            
            text, raw_response = ocr_with_nim(data_url)
            print(f"Caracteres extraídos: {len(text)}")
            print("\nTexto OCR:")
            print("-" * 40)
            print(text[:1500])
            
            # Análisis de errores
            print("\n\nANÁLISIS DE ERRORES:")
            print("-" * 40)
            
            checks = [
                ("PROCURADURÍA", "PROCURADURIA" in text.upper() or "PROCURADURÍA" in text),
                ("GENERAL DE LA", "GENERAL DE LA" in text.upper()),
                ("DECRETO No. 001", "001" in text or "001" in text),
                ("17 de enero", "17" in text and "enero" in text.lower()),
                ("GONZALO ENRIQUE", "GONZALO" in text.upper()),
                ("SIERRA VASCO", "SIERRA" in text.upper() and "VASCO" in text.upper()),
                ("70.039.458", "70.039.458" in text or "70039458" in text),
                ("Bogotá", "BOGOTA" in text.upper() or "Bogotá" in text),
                ("MAYA VILLAZÓN", "MAYA" in text.upper()),
            ]
            
            for check_name, passed in checks:
                status = "✓" if passed else "✗"
                print(f"  {status} {check_name}")
            
            passed_count = sum(1 for _, p in checks if p)
            print(f"\nPrecisión: {passed_count}/{len(checks)} ({passed_count/len(checks)*100:.0f}%)")
            
        except Exception as e:
            print(f"ERROR: {e}")


if __name__ == "__main__":
    pdf_path = r"C:\temp\PNG_CERTIFICADO_V3\Decretos\2009\DECRETO 001-2009.pdf"
    
    # Verificar servicio OCR
    print("Verificando servicio OCR...")
    try:
        resp = requests.get(f"http://{OCR_HOST}:{OCR_PORT}/v1/health/ready", timeout=5)
        if resp.status_code == 200:
            print("OCR: OK\n")
        else:
            print("OCR: ERROR")
            exit(1)
    except Exception as e:
        print(f"OCR: NO DISPONIBLE - {e}")
        exit(1)
    
    test_ocr_quality(pdf_path)
