"""
Script de prueba para verificar servicios OCR y LLM
NO modifica la base de datos - solo verifica conectividad
"""
import requests
import json
import os
import base64
import sys

# Forzar UTF-8 para Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Configuración
OLLAMA_URL = "http://localhost:11434/api/generate"
OCR_HOST = "localhost"
OCR_PORT = 8000
TEST_MODEL = "gpt-oss:20b-cloud"

def test_ollama():
    """Prueba el servicio Ollama con el modelo especificado"""
    print("\n" + "="*50)
    print("TEST 1: Ollama LLM")
    print("="*50)

    try:
        # Primero verificar que Ollama está corriendo
        print(f"Conectando a: {OLLAMA_URL}")
        print(f"Modelo: {TEST_MODEL}")

        payload = {
            "model": TEST_MODEL,
            "prompt": "Responde solo con la palabra 'FUNCIONANDO' si puedes leer este mensaje.",
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 50,
            }
        }

        response = requests.post(OLLAMA_URL, json=payload, timeout=30)

        if response.status_code == 200:
            result = response.json()
            respuesta = result.get('response', '')
            print(f"✓ OLLAMA OK - Respuesta: {respuesta[:100]}")
            return True
        else:
            print(f"✗ OLLAMA ERROR - Status: {response.status_code}")
            print(f"  Respuesta: {response.text[:200]}")
            return False

    except requests.exceptions.ConnectionError:
        print("✗ OLLAMA NO DISPONIBLE - No se puede conectar a localhost:11434")
        print("  Verifique que Ollama esté ejecutándose")
        return False
    except Exception as e:
        print(f"✗ OLLAMA ERROR: {e}")
        return False


def test_ocr():
    """Prueba el servicio OCR NIM PaddleOCR"""
    print("\n" + "="*50)
    print("TEST 2: OCR (NIM PaddleOCR)")
    print("="*50)

    try:
        # Verificar health endpoint
        url_health = f"http://{OCR_HOST}:{OCR_PORT}/v1/health/ready"
        print(f"Verificando: {url_health}")

        resp = requests.get(url_health, timeout=10)

        if resp.status_code == 200:
            print(f"✓ OCR HEALTH OK - Status: {resp.status_code}")
            return True
        else:
            print(f"✗ OCR HEALTH ERROR - Status: {resp.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        print("✗ OCR NO DISPONIBLE - No se puede conectar a localhost:8000")
        print("  Verifique que el contenedor Docker de OCR esté ejecutándose")
        return False
    except Exception as e:
        print(f"✗ OCR ERROR: {e}")
        return False


def test_pdf_extraction(pdf_path):
    """Prueba extracción de texto de un PDF específico"""
    print("\n" + "="*50)
    print("TEST 3: Extracción de PDF")
    print("="*50)

    try:
        import fitz  # PyMuPDF
        print(f"PyMuPDF instalado: ✓")
    except ImportError:
        print("✗ PyMuPDF NO instalado. Ejecute: pip install pymupdf")
        return False

    if not os.path.exists(pdf_path):
        print(f"✗ Archivo no encontrado: {pdf_path}")
        return False

    print(f"Archivo: {pdf_path}")

    try:
        doc = fitz.open(pdf_path)
        num_pages = len(doc)
        print(f"Páginas: {num_pages}")

        # Extraer texto nativo
        full_text = []
        for page in doc:
            text = page.get_text()
            full_text.append(text)
        doc.close()

        combined = '\n'.join(full_text)
        clean_text = ''.join(combined.split())

        if len(clean_text) > 100:
            print(f"✓ Texto nativo extraído: {len(clean_text)} caracteres")
            print(f"  Primeros 200 chars: {combined[:200]}...")
            return True, combined
        else:
            print(f"  Texto nativo insuficiente ({len(clean_text)} chars)")
            print("  Intentando OCR...")
            return False, None

    except Exception as e:
        print(f"✗ Error extrayendo PDF: {e}")
        return False, None


def test_llm_analysis(text, filename):
    """Prueba análisis LLM con texto extraído"""
    print("\n" + "="*50)
    print("TEST 4: Análisis LLM del decreto")
    print("="*50)

    if not text:
        print("✗ No hay texto para analizar")
        return False

    # Prompt simplificado para prueba
    prompt = f"""Analiza este decreto y extrae la información básica en JSON:

ARCHIVO: {filename}

TEXTO (primeros 2000 chars):
{text[:2000]}

Responde SOLO con JSON:
{{
    "numero_decreto": "número del decreto",
    "tipo_documento": "DECRETO o RESOLUCION",
    "resumen": "breve descripción de qué trata"
}}"""

    try:
        payload = {
            "model": TEST_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 500,
            }
        }

        print(f"Enviando a LLM ({TEST_MODEL})...")
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)

        if response.status_code == 200:
            result = response.json()
            respuesta = result.get('response', '')
            print(f"✓ LLM respondió correctamente")
            print(f"\nRespuesta del LLM:")
            print("-"*40)
            print(respuesta)
            print("-"*40)
            return True
        else:
            print(f"✗ LLM ERROR - Status: {response.status_code}")
            return False

    except Exception as e:
        print(f"✗ Error en análisis LLM: {e}")
        return False


def find_test_pdf(directory):
    """Busca un PDF de prueba en el directorio"""
    if not os.path.isdir(directory):
        return None

    for root, dirs, files in os.walk(directory):
        for f in files:
            if f.lower().endswith('.pdf'):
                return os.path.join(root, f)
    return None


if __name__ == "__main__":
    print("="*50)
    print("VERIFICACIÓN DE SERVICIOS - TEST MODE")
    print("="*50)
    print("Este script NO modifica la base de datos")
    print()

    # Test 1: Ollama
    ollama_ok = test_ollama()

    # Test 2: OCR
    ocr_ok = test_ocr()

    # Test 3 y 4: PDF y análisis
    test_dir = r"C:\temp\PNG_CERTIFICADO_V3\Decretos\2009"
    pdf_path = find_test_pdf(test_dir)

    if pdf_path:
        result = test_pdf_extraction(pdf_path)
        if isinstance(result, tuple):
            pdf_ok, text = result
        else:
            pdf_ok, text = result, None

        # Test 4: Análisis LLM
        if pdf_ok and text and ollama_ok:
            test_llm_analysis(text, os.path.basename(pdf_path))
    else:
        print(f"\n✗ No se encontraron PDFs en: {test_dir}")
        pdf_ok = False

    # Resumen
    print("\n" + "="*50)
    print("RESUMEN DE VERIFICACIÓN")
    print("="*50)
    print(f"Ollama LLM ({TEST_MODEL}): {'✓ OK' if ollama_ok else '✗ FALLO'}")
    print(f"OCR Docker (localhost:8000): {'✓ OK' if ocr_ok else '✗ FALLO'}")
    print(f"Extracción PDF: {'✓ OK' if pdf_ok else '✗ FALLO'}")

    if ollama_ok and (ocr_ok or pdf_ok):
        print("\n✓ SERVICIOS LISTOS - Puede ejecutar extract_decretos.py")
    else:
        print("\n✗ ALGUNOS SERVICIOS NO DISPONIBLES")
        if not ollama_ok:
            print("  - Verifique que Ollama esté corriendo: ollama serve")
            print(f"  - Verifique que el modelo esté disponible: ollama list")
        if not ocr_ok:
            print("  - Verifique el contenedor Docker de OCR")
