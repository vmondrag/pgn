"""
Script de extracción de novedades de RESOLUCIONES PGN
Basado en el Decreto Ley 262 de 2000 y Decreto 1851 de 2021

Las resoluciones gestionan situaciones administrativas temporales:
- Licencias (ordinarias, no remuneradas, por luto, maternidad, estudios)
- Comisiones especiales (asesoría, otras entidades)
- Prórrogas (posesión, comisiones, licencias)
- Vacaciones e interrupciones
- Cumplimiento de órdenes judiciales

Uso:
    python extract_resoluciones.py --dir-in "C:\temp\Decretos\RESOLUCIONES 2024" --llm gpt-oss:120b-cloud
    python extract_resoluciones.py --dir-in "C:\temp\Decretos\RESOLUCIONES -2023" --llm gpt-oss:20b-cloud --limit 50
"""
import os
import re
import json
import sqlite3
import base64
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import requests
import sys

# Forzar UTF-8 para Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Configuración por defecto
DB_PATH = r"C:\temp\PNG_CERTIFICADO_V3\novedades_pgn.db"
DEFAULT_DIR = r"C:\temp\PNG_CERTIFICADO_V3\Decretos\RESOLUCIONES 2024"
OLLAMA_HOST = "localhost"
OLLAMA_PORT = 11434
OLLAMA_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/generate"
DEFAULT_MODEL = "gpt-oss:120b-cloud"
OCR_HOST = "localhost"
OCR_PORT = 8000

# Directorios de salida para metadatos
OUTPUT_BASE = r"C:\temp\PNG_CERTIFICADO_V3\output_resoluciones"

# Variable global para modelo
OLLAMA_MODEL = DEFAULT_MODEL

# Intentar importar PyMuPDF
try:
    import fitz
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False
    print("ADVERTENCIA: PyMuPDF no instalado. Ejecute: pip install pymupdf")


# =============================================================================
# CÓDIGOS DE NOVEDAD PARA RESOLUCIONES (Decreto 262/2000)
# =============================================================================

CODIGOS_RESOLUCION = {
    # Licencias (Arts. 110-131)
    "LNR": {"descripcion": "Licencia No Remunerada Ordinaria", "tipo": "LICENCIA", "articulo": "111-112"},
    "LNRE": {"descripcion": "Licencia No Remunerada para Estudios", "tipo": "LICENCIA", "articulo": "119"},
    "LR": {"descripcion": "Licencia Remunerada", "tipo": "LICENCIA", "articulo": "120"},
    "LLUT": {"descripcion": "Licencia por Luto", "tipo": "LICENCIA", "articulo": "Ley 1635/2013"},
    "LMAT": {"descripcion": "Licencia por Maternidad", "tipo": "LICENCIA", "articulo": "120-125"},
    "LPAT": {"descripcion": "Licencia por Paternidad", "tipo": "LICENCIA", "articulo": "120"},
    "LENF": {"descripcion": "Licencia por Enfermedad", "tipo": "LICENCIA", "articulo": "120"},
    "LDEP": {"descripcion": "Licencia Deportiva", "tipo": "LICENCIA", "articulo": "129"},

    # Comisiones (Arts. 94-109)
    "CESP": {"descripcion": "Comisión Especial", "tipo": "COMISION", "articulo": "105"},
    "CEST": {"descripcion": "Comisión de Estudios", "tipo": "COMISION", "articulo": "98"},
    "CSER": {"descripcion": "Comisión de Servicio", "tipo": "COMISION", "articulo": "94"},
    "RCESP": {"descripcion": "Renuncia a Comisión Especial", "tipo": "COMISION", "articulo": "105-108"},
    "TCOM": {"descripcion": "Terminación de Comisión", "tipo": "COMISION", "articulo": "108"},
    "TENC": {"descripcion": "Terminación de Encargo", "tipo": "COMISION", "articulo": "187"},
    "TPROV": {"descripcion": "Terminación de Provisionalidad", "tipo": "COMISION", "articulo": "81"},
    "REINC": {"descripcion": "Reincorporación al Cargo", "tipo": "COMISION", "articulo": "108"},

    # Prórrogas
    "PPOS": {"descripcion": "Prórroga para Posesión", "tipo": "PRORROGA", "articulo": "84"},
    "PCOM": {"descripcion": "Prórroga de Comisión", "tipo": "PRORROGA", "articulo": "105"},
    "PLIC": {"descripcion": "Prórroga de Licencia", "tipo": "PRORROGA", "articulo": "119"},

    # Vacaciones (Arts. 139-149)
    "VAC": {"descripcion": "Vacaciones", "tipo": "VACACIONES", "articulo": "139"},
    "IVAC": {"descripcion": "Interrupción de Vacaciones", "tipo": "VACACIONES", "articulo": "145"},

    # Permisos (Art. 132)
    "PERM": {"descripcion": "Permiso Remunerado", "tipo": "PERMISO", "articulo": "132"},

    # Especiales
    "COJ": {"descripcion": "Cumplimiento Orden Judicial", "tipo": "ESPECIAL", "articulo": "N/A"},
    "NEG": {"descripcion": "Negación de Solicitud", "tipo": "ESPECIAL", "articulo": "N/A"},
    "REV": {"descripcion": "Revocatoria/Modificación", "tipo": "ESPECIAL", "articulo": "N/A"},

    # Suspensiones Preventivas (Art. 157-160)
    "SUSP": {"descripcion": "Suspensión del cargo", "tipo": "SUSPENSION", "articulo": "157-160"},
    "SUSPI": {"descripcion": "Suspensión por Inhabilidad Sobreviniente", "tipo": "SUSPENSION", "articulo": "160"},

    # === SANCIONES DISCIPLINARIAS (Ley 734/2002, Ley 1952/2019) ===
    # Según el Código Disciplinario Único y Código General Disciplinario
    "D": {"descripcion": "Destitución", "tipo": "SANCION_DISCIPLINARIA", "articulo": "Ley 734/2002 Art. 44"},
    "DESINH": {"descripcion": "Destitución e Inhabilidad General", "tipo": "SANCION_DISCIPLINARIA", "articulo": "Ley 734/2002 Art. 44-45"},
    "SUSPD": {"descripcion": "Suspensión Disciplinaria", "tipo": "SANCION_DISCIPLINARIA", "articulo": "Ley 734/2002 Art. 44"},
    "SUSPINH": {"descripcion": "Suspensión e Inhabilidad Especial", "tipo": "SANCION_DISCIPLINARIA", "articulo": "Ley 734/2002 Art. 44-46"},
    "MULTA": {"descripcion": "Multa Disciplinaria", "tipo": "SANCION_DISCIPLINARIA", "articulo": "Ley 734/2002 Art. 44"},
    "AMONES": {"descripcion": "Amonestación Escrita", "tipo": "SANCION_DISCIPLINARIA", "articulo": "Ley 734/2002 Art. 44"},

    # Pendiente revisión
    "PENDIENTE_REVISION": {"descripcion": "Requiere revisión manual", "tipo": "PENDIENTE", "articulo": "N/A"},

    # === ENCARGOS (Art. 91-93, 187) ===
    # Los encargos pueden venir en Resoluciones o Decretos
    "E": {"descripcion": "Encargo", "tipo": "ENCARGO", "articulo": "91-93"},
    "ETEMP": {"descripcion": "Encargo Temporal", "tipo": "ENCARGO", "articulo": "91"},
    "EVAC": {"descripcion": "Encargo por Vacancia", "tipo": "ENCARGO", "articulo": "91"},
    "ELIC": {"descripcion": "Encargo por Licencia del Titular", "tipo": "ENCARGO", "articulo": "91"},
    "ECOM": {"descripcion": "Encargo por Comisión del Titular", "tipo": "ENCARGO", "articulo": "91"},

    # === RENUNCIAS (Art. 155) ===
    "R": {"descripcion": "Renuncia Aceptada", "tipo": "RENUNCIA", "articulo": "155"},
    "RCAR": {"descripcion": "Renuncia al Cargo", "tipo": "RENUNCIA", "articulo": "155"},

    # === NOMBRAMIENTOS (Art. 77-80) ===
    "N": {"descripcion": "Nombramiento", "tipo": "NOMBRAMIENTO", "articulo": "77-80"},
    "NORD": {"descripcion": "Nombramiento Ordinario", "tipo": "NOMBRAMIENTO", "articulo": "77"},
    "NPROV": {"descripcion": "Nombramiento Provisional", "tipo": "NOMBRAMIENTO", "articulo": "81"},

    # === OTROS MOVIMIENTOS DE PERSONAL ===
    "T": {"descripcion": "Traslado", "tipo": "TRASLADO", "articulo": "89"},
    "RET": {"descripcion": "Retiro/Jubilación", "tipo": "RETIRO", "articulo": "155-157"},
    "RECL": {"descripcion": "Reclasificación de Cargo", "tipo": "ADMINISTRATIVO", "articulo": "N/A"},
}


# =============================================================================
# FUNCIONES DE EXTRACCIÓN DE PDF
# =============================================================================

def extract_text_native(pdf_path: str) -> Tuple[Optional[str], bool]:
    """Extrae texto de PDF usando PyMuPDF"""
    if not HAS_FITZ:
        return None, False

    try:
        doc = fitz.open(pdf_path)
        full_text = []
        for page in doc:
            text = page.get_text()
            full_text.append(text)
        doc.close()

        combined = '\n'.join(full_text)
        clean_text = re.sub(r'\s+', '', combined)
        is_native = len(clean_text) > 100

        return combined if is_native else None, is_native

    except Exception as e:
        print(f"Error extrayendo PDF nativo: {e}")
        return None, False


def preprocess_image_for_ocr(img_bytes: bytes, mode: str = "grayscale") -> bytes:
    """
    Preprocesa imagen para mejorar la calidad del OCR.

    Args:
        img_bytes: Imagen en bytes (PNG)
        mode: Modo de preprocesamiento
            - "grayscale": Solo escala de grises + denoise (RECOMENDADO - mejor extracción)
            - "contrast": Escala de grises + CLAHE (sin binarización)
            - "enhanced": Preprocesamiento completo (grayscale + denoise + CLAHE + binarization)
            - "none": Sin preprocesamiento

    Resultados de pruebas (Resolución 085/2024):
    - grayscale: +1-2% más caracteres extraídos vs sin preprocesamiento
    - enhanced: -3-5% MENOS caracteres (binarización pierde información)
    - DPI óptimo: 150 (mejor que 300 para NIM PaddleOCR)

    Referencias:
    - https://nextgeninvent.com/blogs/7-steps-of-image-pre-processing-to-improve-ocr-using-python-2/
    - https://docs.nvidia.com/nim/ingestion/table-extraction/latest/optimization.html
    """
    if mode == "none":
        return img_bytes

    try:
        import cv2
        import numpy as np

        # Convertir bytes a imagen numpy
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return img_bytes

        # 1. Convertir a escala de grises
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 2. Normalización de intensidad
        normalized = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)

        # 3. Reducción de ruido (Non-local Means Denoising)
        denoised = cv2.fastNlMeansDenoising(normalized, None, h=10, templateWindowSize=7, searchWindowSize=21)

        if mode == "grayscale":
            # Solo escala de grises con denoising
            final_img = cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)
        elif mode == "contrast":
            # 4. Mejora de contraste con CLAHE (sin binarización)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(denoised)
            final_img = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
        else:  # mode == "enhanced" (default)
            # 4. Mejora de contraste con CLAHE
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(denoised)

            # 5. Binarización adaptativa (Otsu)
            _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            final_img = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

        # Codificar como PNG
        _, processed_bytes = cv2.imencode('.png', final_img)
        return processed_bytes.tobytes()

    except ImportError:
        print("Advertencia: OpenCV no disponible, usando imagen sin preprocesar")
        return img_bytes
    except Exception as e:
        print(f"Error en preprocesamiento: {e}, usando imagen original")
        return img_bytes


def render_page_to_base64(pdf_path: str, page_index: int = 0, dpi: int = 150,
                          preprocess: bool = True) -> Optional[str]:
    """
    Renderiza página PDF a imagen base64 para OCR.

    Args:
        pdf_path: Ruta al archivo PDF
        page_index: Índice de la página (0-based)
        dpi: Resolución de renderizado (óptimo: 150 para NIM PaddleOCR)
        preprocess: Si True, aplica preprocesamiento grayscale para mejorar OCR

    Nota: Pruebas empíricas (Resolución 085/2024) muestran que 150 DPI
    produce MEJOR extracción que 300 DPI con NIM PaddleOCR:
    - 150 DPI: 3,777 chars, 1.35s
    - 300 DPI: 3,711 chars, 1.56s
    """
    if not HAS_FITZ:
        return None

    try:
        doc = fitz.open(pdf_path)
        page = doc[page_index]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        doc.close()

        # Aplicar preprocesamiento si está habilitado
        if preprocess:
            img_bytes = preprocess_image_for_ocr(img_bytes)

        b64 = base64.b64encode(img_bytes).decode('utf-8')
        return f"data:image/png;base64,{b64}"

    except Exception as e:
        print(f"Error renderizando página: {e}")
        return None


def ocr_with_nim(data_url: str, timeout: int = 120) -> Optional[str]:
    """Realiza OCR usando NIM PaddleOCR con post-procesamiento"""
    try:
        url = f"http://{OCR_HOST}:{OCR_PORT}/v1/infer"
        payload = {"input": [{"type": "image_url", "url": data_url}]}

        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()

        result = response.json()
        text_parts = []
        _extract_ocr_text(result, text_parts)

        raw_text = '\n'.join(text_parts)
        # Aplicar post-procesamiento para corregir errores comunes
        return postprocess_ocr_text(raw_text)

    except requests.exceptions.ConnectionError:
        print("Error: No se puede conectar a NIM PaddleOCR en localhost:8000")
        return None
    except Exception as e:
        print(f"Error en OCR: {e}")
        return None


def _extract_ocr_text(obj, texts: List[str]):
    """Extrae texto recursivamente de respuesta OCR"""
    if isinstance(obj, dict):
        # Buscar text_prediction primero (formato NIM PaddleOCR)
        if 'text_prediction' in obj:
            pred = obj['text_prediction']
            if isinstance(pred, dict) and 'text' in pred:
                texts.append(pred['text'].strip())
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


def postprocess_ocr_text(text: str) -> str:
    """
    Post-procesa texto OCR para corregir errores comunes y eliminar duplicados.

    Problemas detectados en NIM PaddleOCR:
    1. Líneas duplicadas consecutivas
    2. Errores en "GENERAL DE LA NACIÓN"
    3. Espacios faltantes en palabras largas
    """
    if not text:
        return text

    lines = text.split('\n')

    # 1. Eliminar líneas duplicadas consecutivas
    cleaned_lines = []
    prev_line = None
    for line in lines:
        line = line.strip()
        if line and line != prev_line:
            cleaned_lines.append(line)
            prev_line = line

    text = '\n'.join(cleaned_lines)

    # 2. Corregir errores comunes de OCR en encabezados PGN
    ocr_corrections = {
        # Variantes de "GENERAL DE LA NACIÓN"
        'GENRALDELA ACH': 'GENERAL DE LA NACIÓN',
        'GENRALDELA NACON': 'GENERAL DE LA NACIÓN',
        'GEHEALDELAMACON': 'GENERAL DE LA NACIÓN',
        'GEHERLDELAMACON': 'GENERAL DE LA NACIÓN',
        'CEALDELAMCON': 'GENERAL DE LA NACIÓN',
        'SEHBAL DEANON': 'GENERAL DE LA NACIÓN',
        'GENERAL DELA NACIOH': 'GENERAL DE LA NACIÓN',
        'GENERALDELANACION': 'GENERAL DE LA NACIÓN',
        # Variantes de "PROCURADURÍA"
        'PROCURADURA': 'PROCURADURÍA',
        'PROCURADUR': 'PROCURADURÍA',
    }

    for error, correction in ocr_corrections.items():
        text = text.replace(error, correction)

    return text


def extract_pdf_text(pdf_path: str) -> Tuple[str, str]:
    """
    Extrae texto de PDF usando múltiples métodos:
    1. Extracción nativa (si el PDF tiene texto embebido)
    2. OCR con NIM PaddleOCR (si está disponible)

    Args:
        pdf_path: Ruta al archivo PDF
    """
    # Intentar extracción nativa primero
    text, is_native = extract_text_native(pdf_path)
    if is_native and text:
        return text, 'NATIVO'

    if not HAS_FITZ:
        return '', 'ERROR_NO_FITZ'

    try:
        doc = fitz.open(pdf_path)
        num_pages = len(doc)
        doc.close()

        # Intentar OCR con NIM PaddleOCR
        all_text = []
        for i in range(min(num_pages, 10)):
            data_url = render_page_to_base64(pdf_path, i)
            if data_url:
                page_text = ocr_with_nim(data_url)
                if page_text:
                    all_text.append(page_text)

        if all_text:
            return '\n'.join(all_text), 'OCR'

        return '', 'ERROR_OCR'

    except Exception as e:
        return '', f'ERROR: {str(e)}'


# =============================================================================
# FUNCIONES DE ANÁLISIS LLM PARA RESOLUCIONES
# =============================================================================

def query_ollama(prompt: str, system_prompt: str = None, model: str = None) -> Optional[str]:
    """Consulta al modelo LLM via Ollama"""
    global OLLAMA_MODEL
    used_model = model or OLLAMA_MODEL

    try:
        payload = {
            "model": used_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 3000,
            }
        }

        if system_prompt:
            payload["system"] = system_prompt

        response = requests.post(OLLAMA_URL, json=payload, timeout=120)

        if response.status_code == 200:
            result = response.json()
            return result.get('response', '')
        else:
            print(f"Error Ollama: {response.status_code}")
            return None

    except requests.exceptions.ConnectionError:
        print("Error: No se puede conectar a Ollama")
        return None
    except Exception as e:
        print(f"Error consultando Ollama: {e}")
        return None


def get_codigos_resolucion_str() -> str:
    """Genera string con códigos de resolución para el prompt"""
    lines = []
    for codigo, info in CODIGOS_RESOLUCION.items():
        lines.append(f"  - {codigo}: {info['descripcion']} ({info['tipo']}) - Art. {info['articulo']}")
    return "\n".join(lines)


def clean_llm_json(json_str: str) -> str:
    """
    Limpia errores comunes en JSON generado por LLM.
    """
    # Remover caracteres de control no válidos (excepto newlines y tabs)
    json_str = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', json_str)

    # Reemplazar comillas tipográficas por comillas normales
    json_str = json_str.replace('"', '"').replace('"', '"')
    json_str = json_str.replace(''', "'").replace(''', "'")
    json_str = json_str.replace('„', '"').replace('‟', '"')

    # Reemplazar guiones especiales
    json_str = json_str.replace('–', '-').replace('—', '-')

    # Corregir trailing commas antes de ] o }
    json_str = re.sub(r',\s*\]', ']', json_str)
    json_str = re.sub(r',\s*\}', '}', json_str)

    # Corregir valores numéricos con texto (ej: "dias_otorgados": 5 días)
    json_str = re.sub(r':\s*(\d+)\s*[díasabcdefghijklmnopqrstuvwxyz]+\s*([,\}\]])', r': \1\2', json_str, flags=re.IGNORECASE)

    # Corregir comas faltantes entre objetos en array (muy común con múltiples funcionarios)
    # Patrón: } { sin coma
    json_str = re.sub(r'\}\s*\{', '}, {', json_str)

    # Patrón: }\n{ sin coma
    json_str = re.sub(r'\}[\r\n]+\s*\{', '},\n{', json_str)

    # Corregir null/None
    json_str = re.sub(r':\s*None\s*([,\}\]])', r': null\1', json_str)
    json_str = re.sub(r':\s*True\s*([,\}\]])', r': true\1', json_str)
    json_str = re.sub(r':\s*False\s*([,\}\]])', r': false\1', json_str)

    # Eliminar comas dobles que puedan haberse creado
    json_str = re.sub(r',\s*,', ',', json_str)

    return json_str


def repair_json(json_str: str) -> Optional[str]:
    """
    Intenta reparar JSON malformado de forma más agresiva.
    """
    try:
        # Primero limpiar
        json_str = clean_llm_json(json_str)

        # Intentar parsear directamente
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError as e:
        error_pos = e.pos if hasattr(e, 'pos') else 0
        error_msg = str(e)

    # Intentar agregar comas faltantes entre elementos de array
    # Patrón: } { sin coma (común en arrays de funcionarios)
    json_str = re.sub(r'\}\s*\{', '}, {', json_str)

    # Patrón: }\n{ o }\r\n{ sin coma
    json_str = re.sub(r'\}[\r\n]+\s*\{', '},\n{', json_str)

    # Patrón: ] [ sin coma
    json_str = re.sub(r'\]\s*\[', '], [', json_str)

    # Patrón: "valor" "clave": sin coma (error común)
    json_str = re.sub(r'"\s*\n\s*"([a-zA-Z_]+)":', r'",\n"\1":', json_str)

    # Corregir strings no terminados antes de coma o cierre
    # Buscar patrones como: "texto sin cerrar,  o  "texto sin cerrar}
    json_str = re.sub(r'([^\\])"([^"]*?)([,\}\]])', r'\1"\2"\3', json_str)

    # Eliminar comas dobles
    json_str = re.sub(r',\s*,', ',', json_str)

    # Patrón: " " sin coma entre strings
    json_str = re.sub(r'"\s+(?="[a-zA-Z_]+":\s*)', '", ', json_str)

    # Intentar cerrar arrays/objetos no cerrados
    open_braces = json_str.count('{') - json_str.count('}')
    open_brackets = json_str.count('[') - json_str.count(']')

    if open_braces > 0:
        json_str += '}' * open_braces
    if open_brackets > 0:
        json_str += ']' * open_brackets

    try:
        json.loads(json_str)
        return json_str
    except:
        return None


def extract_novedad_resolucion_with_llm(text: str, filename: str, conn: sqlite3.Connection = None) -> Dict:
    """
    Usa LLM para clasificar novedades en RESOLUCIONES.

    A diferencia de los decretos, las resoluciones gestionan:
    - Situaciones administrativas temporales (licencias, comisiones)
    - No afectan titularidad del cargo
    - Pueden afectar a múltiples funcionarios
    """

    codigos_str = get_codigos_resolucion_str()

    system_prompt = f"""Eres un experto en análisis de actos administrativos de la Procuraduría General
de la Nación de Colombia, especializado en el Decreto Ley 262 de 2000 y sus modificaciones.

=== CONTEXTO LEGAL ===
Las RESOLUCIONES gestionan SITUACIONES ADMINISTRATIVAS TEMPORALES, a diferencia de los
DECRETOS que afectan la titularidad del cargo (nombramientos, renuncias).

IMPORTANTE: En las carpetas de RESOLUCIONES pueden aparecer DECRETOS. Debes identificar
correctamente si el documento es un DECRETO o una RESOLUCIÓN.

Marco legal principal:
- Decreto Ley 262 de 2000: Régimen de la Procuraduría General de la Nación
- Decreto 1851 de 2021: Modificaciones al régimen
- Ley 1635 de 2013: Licencia por luto (5 días hábiles)

=== CÓMO DISTINGUIR DECRETO vs RESOLUCIÓN ===
Un DECRETO afecta la TITULARIDAD del cargo:
- Nombramiento (N): Designación de funcionario en un cargo
- Renuncia (R): Aceptación de renuncia
- Encargo (E): Funciones temporales de otro cargo
- Destitución (D): Sanción disciplinaria
- Traslado (T): Cambio de ubicación/dependencia
- Retiro/Jubilación (RET): Retiro del servicio

Una RESOLUCIÓN gestiona situaciones TEMPORALES:
- Licencias (ordinarias, luto, maternidad, estudios)
- Comisiones (especiales, de estudios, de servicio)
- Prórrogas (de posesión, de comisión, de licencia)
- Vacaciones
- Suspensiones (por inhabilidad sobreviniente, disciplinarias)
- Encargos temporales (por vacancia, licencia o comisión del titular)
- Aceptación de renuncias (cuando viene como Resolución)

=== TIPOS DE DOCUMENTOS Y SUS CÓDIGOS ===
{codigos_str}

=== REGLAS DE CLASIFICACIÓN ===

**SI ES UN DECRETO (tipo_documento = "DECRETO"):**
- N: "NOMBRAR", "nombramiento ordinario", "designar" para cargo → NOMBRAMIENTO
- R: "aceptar renuncia", "retiro voluntario" → RENUNCIA
- E: "encargar", "mientras se provee" → ENCARGO
- D: "destituir", "sanción disciplinaria" → DESTITUCIÓN
- T: "trasladar", "ubicación" → TRASLADO
- RET: "pensión", "jubilación", "retiro forzoso" → RETIRO

**SI ES UNA RESOLUCIÓN (tipo_documento = "RESOLUCION"):**
1. LICENCIAS (Arts. 110-131):
   - LNR: Licencia ordinaria NO remunerada (hasta 3 meses/año) - Art. 111-112
   - LNRE: Licencia NO remunerada para ESTUDIOS (hasta 3 años) - Art. 119
   - LLUT: Licencia por LUTO (5 días hábiles, remunerada) - Ley 1635/2013
   - LMAT: Licencia por MATERNIDAD - Art. 120-125
   - LPAT: Licencia por PATERNIDAD - Art. 120
   - LENF: Licencia por ENFERMEDAD - Art. 120
   - LDEP: Licencia DEPORTIVA (hasta 90 días) - Art. 129

2. COMISIONES Y SUS TERMINACIONES (Arts. 94-109, 187):
   - CESP: Comisión ESPECIAL (otras entidades, asesoría, hasta 2 años) - Art. 105
   - CEST: Comisión de ESTUDIOS (posgrado, investigación) - Art. 98
   - CSER: Comisión de SERVICIO (funciones en lugar diferente) - Art. 94
   - RCESP: RENUNCIA a comisión especial (aceptar renuncia a comisión) - Art. 105-108
   - TCOM: TERMINACIÓN de comisión (dar por terminada comisión) - Art. 108
   - TENC: TERMINACIÓN de encargo (dar por terminado encargo) - Art. 187
   - TPROV: TERMINACIÓN de provisionalidad (dar por terminado nombramiento provisional) - Art. 81
   - REINC: REINCORPORACIÓN al cargo (volver al cargo de carrera) - Art. 108

3. PRÓRROGAS:
   - PPOS: Prórroga para POSESIÓN (hasta 30 días adicionales) - Art. 84
   - PCOM: Prórroga de COMISIÓN
   - PLIC: Prórroga de LICENCIA

4. VACACIONES (Arts. 139-149):
   - VAC: Concesión de VACACIONES (22 días/año)
   - IVAC: INTERRUPCIÓN de vacaciones

5. ESPECIALES:
   - COJ: Cumplimiento de ORDEN JUDICIAL
   - NEG: NEGACIÓN de solicitud
   - REV: REVOCATORIA o modificación

6. SUSPENSIONES (Arts. 157-160, 170-172):
   - SUSP: Suspensión del cargo (genérica)
   - SUSPI: Suspensión por INHABILIDAD SOBREVINIENTE (proceso penal, medida de aseguramiento) - Art. 160
   - SUSPD: Suspensión DISCIPLINARIA (sanción por falta disciplinaria) - Art. 170-172

7. ENCARGOS (Arts. 91-93):
   - E: Encargo (genérico)
   - ETEMP: Encargo TEMPORAL (funciones de otro cargo temporalmente)
   - EVAC: Encargo por VACANCIA (mientras se provee el cargo)
   - ELIC: Encargo por LICENCIA del titular
   - ECOM: Encargo por COMISIÓN del titular

8. RENUNCIAS Y NOMBRAMIENTOS (cuando vienen en Resolución):
   - R: Renuncia aceptada
   - RCAR: Renuncia al cargo
   - N: Nombramiento
   - NORD: Nombramiento ordinario
   - NPROV: Nombramiento provisional

9. SANCIONES DISCIPLINARIAS (Ley 734/2002, Ley 1952/2019):
   - D: Destitución (retiro definitivo del servicio)
   - DESINH: Destitución e Inhabilidad General (para faltas gravísimas dolosas)
   - SUSPD: Suspensión Disciplinaria (sin goce de sueldo, de 1 a 12 meses)
   - SUSPINH: Suspensión e Inhabilidad Especial (para faltas graves)
   - MULTA: Multa Disciplinaria (para faltas leves dolosas)
   - AMONES: Amonestación Escrita (para faltas leves culposas)

10. OTROS ADMINISTRATIVOS:
   - RECL: Reclasificación de cargo
   - T: Traslado

=== IDENTIFICACIÓN DE PALABRAS CLAVE ===
PARA DECRETOS:
- "DECRETO" + "NOMBRAR" / "nombramiento" → N (Nombramiento)
- "DECRETO" + "aceptar la renuncia" → R (Renuncia)
- "DECRETO" + "encargar" → E (Encargo)
- "DECRETO" + "destituir" → D (Destitución)
- "DECRETO" + "trasladar" → T (Traslado)
- "DECRETO" + "jubilación" / "pensión" → RET (Retiro)

PARA SANCIONES DISCIPLINARIAS (pueden venir en Decreto o Resolución):
- "destituir" / "destitución" (solo) → D
- "destituir" + "inhabilidad general" / "inhabilidad de X años" → DESINH
- "suspender" + "sanción" / "falta disciplinaria" + "inhabilidad" → SUSPINH
- "suspender" + "sanción" / "falta disciplinaria" (sin inhabilidad) → SUSPD
- "multa" + "sanción disciplinaria" / "días de salario" → MULTA
- "amonestación escrita" / "llamado de atención" → AMONES
NOTA: Las sanciones disciplinarias son resultado de un proceso disciplinario y se diferencian de las suspensiones preventivas (SUSP, SUSPI) que son medidas cautelares.

PARA RESOLUCIONES:
- "licencia ordinaria no remunerada" → LNR
- "licencia para adelantar estudios" / "licencia de estudios" → LNRE
- "licencia por luto" / "fallecimiento" → LLUT
- "licencia por maternidad" → LMAT
- "comisión especial" / "comisionar" → CESP
- "prórroga para tomar posesión" → PPOS
- "prórroga de la comisión" → PCOM
- "vacaciones" → VAC
- "interrupción de vacaciones" → IVAC
- "cumplimiento" + "orden judicial" / "sentencia" → COJ
- "negar" / "no conceder" → NEG

PARA SUSPENSIONES PREVENTIVAS (medidas cautelares, NO sanciones):
- "SUSPENDER" + "inhabilidad sobreviniente" / "proceso penal" / "medida de aseguramiento" → SUSPI
- "SUSPENDER" (preventiva, sin sanción disciplinaria) → SUSP

PARA ENCARGOS (pueden venir en Decreto o Resolución):
- "encargar" / "encargo temporal" / "encargo de funciones" → E o ETEMP
- "encargo por vacancia" / "mientras se provee el cargo" → EVAC
- "encargo por licencia del titular" / "durante la licencia de" → ELIC
- "encargo por comisión del titular" / "durante la comisión de" → ECOM
- "dar por terminado el encargo" → TENC

PARA RENUNCIAS (pueden venir en Decreto o Resolución):
- "aceptar la renuncia" / "renuncia presentada" → R o RCAR
- "renuncia irrevocable" / "renuncia voluntaria" → R
- "retiro del servicio por renuncia" → R

PARA NOMBRAMIENTOS (generalmente Decretos):
- "nombrar" / "nombramiento ordinario" / "designar para el cargo" → N o NORD
- "nombramiento provisional" / "proveer provisionalmente" → NPROV

OTROS:
- "reclasificación de cargo" / "reclasificar" → RECL
- "modificar la resolución" / "revocar parcialmente" → REV

=== IMPORTANTE: MÚLTIPLES FUNCIONARIOS ===
Una resolución puede afectar a MÚLTIPLES funcionarios (especialmente licencias por luto).
EXTRAE TODOS los funcionarios mencionados con sus datos completos.

=== IMPORTANTE: IDENTIFICAR TIPO DE DOCUMENTO ===
PRIMERO determina si el documento es un DECRETO o una RESOLUCIÓN.
- Si dice "DECRETO" en el encabezado y habla de nombramientos/renuncias → es DECRETO
- Si dice "RESOLUCIÓN" y habla de licencias/comisiones/vacaciones → es RESOLUCIÓN
- El campo "tipo_documento" DEBE ser "DECRETO" o "RESOLUCION" según corresponda.

Responde SOLO con JSON válido."""

    prompt = f"""Analiza el siguiente documento de la Procuraduría General de la Nación.
NOTA: Este archivo se encuentra en una carpeta de RESOLUCIONES, pero PUEDE SER UN DECRETO.

=== INFORMACIÓN DEL ARCHIVO ===
Nombre: {filename}

=== INSTRUCCIONES DE EXTRACCIÓN ===
**PASO 1: IDENTIFICAR TIPO DE DOCUMENTO**
- Lee el encabezado del documento
- Si dice "DECRETO" y habla de nombramientos, renuncias, encargos → tipo_documento = "DECRETO"
- Si dice "RESOLUCIÓN" y habla de licencias, comisiones, vacaciones → tipo_documento = "RESOLUCION"

**PASO 2: EXTRAER DATOS SEGÚN TIPO**
Para DECRETO:
- Número de decreto
- Tipo de novedad: N (Nombramiento), R (Renuncia), E (Encargo), D (Destitución), T (Traslado), RET (Retiro)
- Datos del funcionario nombrado/retirado/encargado
- Cargo asignado/dejado

Para RESOLUCIÓN:
- Número de resolución
- Tipo de situación administrativa (licencia, comisión, prórroga, etc.)
- Datos de los funcionarios afectados

**PASO 3: PARA TODOS LOS DOCUMENTOS**
1. Extrae TODOS los funcionarios afectados con sus datos:
   - Cédula (sin puntos)
   - Nombre completo
   - Cargo actual
   - Dependencia/Sede
2. Extrae fechas de inicio y fin
3. Identifica el motivo/causa

=== TEXTO DEL DOCUMENTO ===
{text[:7000]}

=== FORMATO JSON DE RESPUESTA ===
{{
    "razonamiento": "Explica: 1) ¿Es DECRETO o RESOLUCION? 2) ¿Qué tipo de novedad es? 3) ¿Por qué elegiste este código?",
    "numero_resolucion": "número del documento (ej: 006, 041, 319, 0441)",
    "fecha_resolucion": "fecha completa del documento",
    "dia_resolucion": 11,
    "mes_resolucion": 1,
    "anio_resolucion": 2023,
    "tipo_documento": "DECRETO o RESOLUCION (¡IMPORTANTE: detectar correctamente!)",
    "codigo_novedad": "Para DECRETO: N, R, E, D, T, RET. Para RESOLUCION: LNR, LLUT, CESP, PPOS, etc.",
    "tipo_novedad": "descripción del tipo (Nombramiento, Renuncia, Licencia No Remunerada, etc.)",
    "es_remunerada": true/false,
    "autoridad_firma": "quien firma (Procurador, Viceprocurador, Secretario General)",
    "funcionarios": [
        {{
            "cedula": "número sin puntos",
            "nombres": "nombres de pila",
            "apellidos": "apellidos",
            "nombre_completo": "nombre completo",
            "cargo": "cargo ASIGNADO (si es nombramiento) o cargo actual (si es resolución)",
            "codigo_cargo": "código si aparece",
            "grado": "grado si aparece",
            "dependencia": "dependencia o área",
            "sede": "ciudad o regional",
            "fecha_inicio": "desde cuándo aplica / fecha de posesión",
            "fecha_fin": "hasta cuándo aplica (si aplica)",
            "dias_otorgados": número de días si aplica,
            "motivo": "razón de la solicitud o nombramiento"
        }}
    ],
    "articulos_aplicables": ["77", "80", "111"],
    "observaciones": "notas adicionales importantes",
    "requiere_revision_humana": false,
    "motivo_revision": "si requiere revisión, explicar por qué"
}}

IMPORTANTE:
- PRIMERO determina si es DECRETO o RESOLUCION antes de asignar el código
- Para DECRETOS de nombramiento: codigo_novedad = "N", tipo_novedad = "Nombramiento"
- Para DECRETOS de renuncia: codigo_novedad = "R", tipo_novedad = "Renuncia"
- Para DECRETOS de encargo: codigo_novedad = "E", tipo_novedad = "Encargo"
- El código DEBE ser uno de los listados arriba
- Si no puedes determinar con certeza, usa "PENDIENTE_REVISION" y explica el motivo
- Extrae TODOS los funcionarios si hay múltiples

=== REGLAS CRÍTICAS DE FORMATO JSON ===
1. USA SOLO comillas dobles (") para strings, NUNCA comillas simples (')
2. NO uses comas al final antes de corchete o llave de cierre
3. Para valores numéricos: usa solo números (ej: "dias_otorgados": 5, NO "dias_otorgados": "5 días")
4. Para valores booleanos: usa true/false en minúsculas (NO True/False)
5. Para valores nulos: usa null (NO None o "")
6. ESCAPA las comillas dentro de strings con barra invertida
7. Cada elemento del array "funcionarios" debe estar separado por coma
8. NO incluyas comentarios dentro del JSON
9. Verifica que cada llave de apertura tenga su llave de cierre correspondiente
10. Verifica que cada corchete de apertura tenga su corchete de cierre correspondiente

Responde ÚNICAMENTE con el JSON válido, sin texto adicional antes o después:"""

    response = query_ollama(prompt, system_prompt)

    if response:
        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                json_str = json_match.group()

                # Limpiar JSON común de errores del LLM
                json_str = clean_llm_json(json_str)

                result = json.loads(json_str)

                # Validar código
                codigo = result.get('codigo_novedad', 'PENDIENTE_REVISION')
                if codigo not in CODIGOS_RESOLUCION:
                    result['codigo_novedad_original'] = codigo
                    result['codigo_novedad'] = 'PENDIENTE_REVISION'
                    result['requiere_revision_humana'] = True
                    result['motivo_revision'] = f"Código '{codigo}' no está en el catálogo"

                return result

        except json.JSONDecodeError as e:
            print(f"Error parseando JSON del LLM: {e}")
            # Intentar reparación más agresiva
            try:
                json_str = repair_json(json_match.group() if json_match else response)
                if json_str:
                    result = json.loads(json_str)
                    result['requiere_revision_humana'] = True
                    result['motivo_revision'] = 'JSON reparado automáticamente - verificar datos'
                    return result
            except:
                pass

    # Si falla, intentar con un prompt simplificado
    simple_prompt = f"""Extrae los datos de esta resolución de la PGN en formato JSON.

Archivo: {filename}
Texto (primeros 5000 caracteres):
{text[:5000]}

Responde SOLO con JSON válido:
{{"razonamiento": "explicación breve", "numero_resolucion": "número", "fecha_resolucion": "fecha", "dia_resolucion": 1, "mes_resolucion": 1, "anio_resolucion": 2024, "tipo_documento": "RESOLUCION", "codigo_novedad": "código (LLUT, LNR, CESP, etc)", "tipo_novedad": "descripción", "es_remunerada": true, "autoridad_firma": "quien firma", "funcionarios": [{{"cedula": "número", "nombre_completo": "nombre", "cargo": "cargo", "dependencia": "área", "sede": "ciudad", "dias_otorgados": 5, "motivo": "razón"}}], "articulos_aplicables": [], "observaciones": "", "requiere_revision_humana": false, "motivo_revision": null}}"""

    simple_system = "Eres un experto en documentos de la PGN Colombia. Responde SOLO con JSON válido, sin texto adicional."

    response2 = query_ollama(simple_prompt, simple_system)
    if response2:
        try:
            json_match2 = re.search(r'\{[\s\S]*\}', response2)
            if json_match2:
                json_str2 = clean_llm_json(json_match2.group())
                result = json.loads(json_str2)
                result['requiere_revision_humana'] = True
                result['motivo_revision'] = 'Procesado con prompt simplificado - verificar datos'
                return result
        except:
            pass

    return {
        'numero_resolucion': None,
        'fecha_resolucion': None,
        'funcionarios': [],
        'codigo_novedad': 'PENDIENTE_REVISION',
        'tipo_novedad': 'Error en extracción',
        'razonamiento': 'No se pudo obtener respuesta válida del LLM',
        'requiere_revision_humana': True,
        'motivo_revision': 'Error en procesamiento LLM'
    }


def extract_year_from_path(filepath: str) -> Optional[int]:
    """Extrae el año del path del directorio"""
    parts = filepath.replace('\\', '/').split('/')

    for p in parts:
        p_upper = p.upper()
        # Buscar año en nombre del directorio
        match = re.search(r'(\d{4})', p)
        if match:
            year = int(match.group(1))
            if 2000 <= year <= 2030:
                return year

    return None


# =============================================================================
# FUNCIONES DE BASE DE DATOS
# =============================================================================

def init_resoluciones_tables(conn: sqlite3.Connection):
    """Inicializa tablas específicas para resoluciones si no existen"""
    cursor = conn.cursor()

    # Tabla de resoluciones (similar a decretos pero para resoluciones)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resoluciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_resolucion VARCHAR(20),
            fecha_resolucion DATE,
            fecha_resolucion_texto VARCHAR(100),
            anio INTEGER,
            dia_resolucion INTEGER,
            mes_resolucion INTEGER,
            anio_resolucion INTEGER,
            archivo_origen VARCHAR(500) NOT NULL,
            ruta_completa VARCHAR(1000),
            tipo_extraccion VARCHAR(20),
            contenido_texto TEXT,
            tiene_multiples_funcionarios BOOLEAN DEFAULT 0,
            es_remunerada BOOLEAN DEFAULT 1,
            autoridad_firma VARCHAR(200),
            articulos_aplicables TEXT,
            estado_procesamiento VARCHAR(20) DEFAULT 'PROCESADO',
            fecha_procesamiento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            razonamiento_llm TEXT,
            requiere_revision_humana BOOLEAN DEFAULT 0,
            motivo_revision TEXT
        )
    ''')

    # Tabla de novedades de resoluciones
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS novedades_resoluciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resolucion_id INTEGER NOT NULL,
            funcionario_id INTEGER,
            codigo_novedad VARCHAR(20),
            tipo_novedad VARCHAR(100),
            descripcion_novedad TEXT,
            cargo_actual VARCHAR(200),
            codigo_cargo VARCHAR(20),
            grado_cargo VARCHAR(20),
            dependencia VARCHAR(300),
            sede VARCHAR(100),
            fecha_inicio DATE,
            fecha_inicio_texto VARCHAR(100),
            fecha_fin DATE,
            fecha_fin_texto VARCHAR(100),
            dias_otorgados INTEGER,
            motivo TEXT,
            es_remunerada BOOLEAN DEFAULT 1,
            observaciones TEXT,
            confianza_extraccion VARCHAR(20) DEFAULT 'LLM',
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (resolucion_id) REFERENCES resoluciones(id),
            FOREIGN KEY (funcionario_id) REFERENCES funcionarios(id)
        )
    ''')

    # Tabla de códigos de novedad para resoluciones
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS codigos_novedad_resolucion (
            codigo VARCHAR(20) PRIMARY KEY,
            descripcion VARCHAR(200),
            tipo_general VARCHAR(50),
            articulo_decreto VARCHAR(50)
        )
    ''')

    # Insertar códigos si no existen
    for codigo, info in CODIGOS_RESOLUCION.items():
        cursor.execute('''
            INSERT OR IGNORE INTO codigos_novedad_resolucion
            (codigo, descripcion, tipo_general, articulo_decreto)
            VALUES (?, ?, ?, ?)
        ''', (codigo, info['descripcion'], info['tipo'], info['articulo']))

    # Índices
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_resoluciones_numero ON resoluciones(numero_resolucion)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_resoluciones_anio ON resoluciones(anio)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_novedades_res_funcionario ON novedades_resoluciones(funcionario_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_novedades_res_resolucion ON novedades_resoluciones(resolucion_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_novedades_res_codigo ON novedades_resoluciones(codigo_novedad)')

    conn.commit()


def get_or_create_funcionario(conn: sqlite3.Connection, data: Dict) -> Optional[int]:
    """Obtiene o crea un funcionario en la BD"""
    cursor = conn.cursor()

    cedula = data.get('cedula')
    if cedula:
        cedula = re.sub(r'[^\d]', '', str(cedula))

    nombres = data.get('nombres', '')
    apellidos = data.get('apellidos', '')
    nombre_completo = data.get('nombre_completo') or f"{nombres} {apellidos}".strip()

    if not nombre_completo and not cedula:
        return None

    if cedula:
        cursor.execute('SELECT id FROM funcionarios WHERE cedula = ?', (cedula,))
        row = cursor.fetchone()
        if row:
            if nombre_completo:
                cursor.execute('''
                    UPDATE funcionarios
                    SET nombre_completo = COALESCE(NULLIF(nombre_completo, ''), ?),
                        nombres = COALESCE(NULLIF(nombres, ''), ?),
                        apellidos = COALESCE(NULLIF(apellidos, ''), ?)
                    WHERE id = ?
                ''', (nombre_completo, nombres, apellidos, row[0]))
                conn.commit()
            return row[0]

    if nombre_completo and not cedula:
        cursor.execute('SELECT id FROM funcionarios WHERE nombre_completo = ? AND cedula IS NULL', (nombre_completo,))
        row = cursor.fetchone()
        if row:
            return row[0]

    try:
        cursor.execute('''
            INSERT INTO funcionarios (cedula, nombres, apellidos, nombre_completo)
            VALUES (?, ?, ?, ?)
        ''', (cedula, nombres, apellidos, nombre_completo))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        if cedula:
            cursor.execute('SELECT id FROM funcionarios WHERE cedula = ?', (cedula,))
            row = cursor.fetchone()
            if row:
                return row[0]
        return None


def save_resolucion(conn: sqlite3.Connection, data: Dict, filepath: str,
                    text: str, extraction_method: str) -> int:
    """Guarda una resolución en la BD"""
    cursor = conn.cursor()

    filename = os.path.basename(filepath)
    anio_path = extract_year_from_path(filepath)

    # Extraer datos
    numero_resolucion = data.get('numero_resolucion')
    anio = data.get('anio_resolucion') or anio_path

    cursor.execute('''
        INSERT INTO resoluciones (
            numero_resolucion, fecha_resolucion_texto, anio,
            dia_resolucion, mes_resolucion, anio_resolucion,
            archivo_origen, ruta_completa, tipo_extraccion,
            contenido_texto, tiene_multiples_funcionarios,
            es_remunerada, autoridad_firma, articulos_aplicables,
            razonamiento_llm, requiere_revision_humana, motivo_revision
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        numero_resolucion,
        data.get('fecha_resolucion'),
        anio,
        data.get('dia_resolucion'),
        data.get('mes_resolucion'),
        data.get('anio_resolucion'),
        filename,
        filepath,
        extraction_method,
        text,
        len(data.get('funcionarios', [])) > 1,
        data.get('es_remunerada', True),
        data.get('autoridad_firma'),
        json.dumps(data.get('articulos_aplicables', [])),
        data.get('razonamiento'),
        data.get('requiere_revision_humana', False),
        data.get('motivo_revision')
    ))

    conn.commit()
    return cursor.lastrowid


def save_novedad_resolucion(conn: sqlite3.Connection, resolucion_id: int,
                            funcionario_id: int, data: Dict, func_data: Dict = None):
    """Guarda una novedad de resolución en la BD"""
    cursor = conn.cursor()

    # Usar datos del funcionario si están disponibles
    cargo = (func_data.get('cargo') if func_data else None) or data.get('cargo')
    codigo_cargo = (func_data.get('codigo_cargo') if func_data else None)
    grado = (func_data.get('grado') if func_data else None)
    dependencia = (func_data.get('dependencia') if func_data else None)
    sede = (func_data.get('sede') if func_data else None)
    fecha_inicio = (func_data.get('fecha_inicio') if func_data else None)
    fecha_fin = (func_data.get('fecha_fin') if func_data else None)
    dias_otorgados = (func_data.get('dias_otorgados') if func_data else None)
    motivo = (func_data.get('motivo') if func_data else None)

    cursor.execute('''
        INSERT INTO novedades_resoluciones (
            resolucion_id, funcionario_id, codigo_novedad, tipo_novedad,
            descripcion_novedad, cargo_actual, codigo_cargo, grado_cargo,
            dependencia, sede, fecha_inicio_texto, fecha_fin_texto,
            dias_otorgados, motivo, es_remunerada, observaciones, confianza_extraccion
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        resolucion_id,
        funcionario_id,
        data.get('codigo_novedad'),
        data.get('tipo_novedad'),
        CODIGOS_RESOLUCION.get(data.get('codigo_novedad', ''), {}).get('descripcion'),
        cargo,
        codigo_cargo,
        grado,
        dependencia,
        sede,
        fecha_inicio,
        fecha_fin,
        dias_otorgados,
        motivo,
        data.get('es_remunerada', True),
        data.get('observaciones'),
        'LLM'
    ))

    conn.commit()


def save_error(conn: sqlite3.Connection, filepath: str, error_type: str, message: str):
    """Guarda un error de procesamiento"""
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO errores_procesamiento (archivo, tipo_error, mensaje_error)
        VALUES (?, ?, ?)
    ''', (filepath, error_type, message))
    conn.commit()


# =============================================================================
# GENERACIÓN DE ARCHIVOS METADATA (.graphrag.json y .md)
# =============================================================================

def generate_graphrag_json(data: Dict, filepath: str, extraction_method: str) -> Dict:
    """Genera estructura JSON para GraphRAG"""
    filename = os.path.basename(filepath)

    entities = []
    relationships = []

    # Entidad de la resolución
    resolucion_id = f"resolucion_{data.get('numero_resolucion')}_{data.get('anio_resolucion')}"
    entities.append({
        "id": resolucion_id,
        "type": "RESOLUCION",
        "name": f"Resolución {data.get('numero_resolucion')} de {data.get('anio_resolucion')}",
        "properties": {
            "numero": data.get('numero_resolucion'),
            "anio": data.get('anio_resolucion'),
            "fecha": data.get('fecha_resolucion'),
            "codigo_novedad": data.get('codigo_novedad'),
            "tipo_novedad": data.get('tipo_novedad'),
            "es_remunerada": data.get('es_remunerada'),
            "autoridad_firma": data.get('autoridad_firma'),
            "archivo": filepath
        }
    })

    # Entidades de funcionarios
    for func in data.get('funcionarios', []):
        func_id = f"funcionario_{func.get('cedula', 'unknown')}"
        entities.append({
            "id": func_id,
            "type": "FUNCIONARIO",
            "name": func.get('nombre_completo', 'Desconocido'),
            "properties": {
                "cedula": func.get('cedula'),
                "cargo": func.get('cargo'),
                "dependencia": func.get('dependencia'),
                "sede": func.get('sede')
            }
        })

        # Relación funcionario -> resolución
        relationships.append({
            "source": func_id,
            "target": resolucion_id,
            "type": data.get('codigo_novedad', 'NOVEDAD'),
            "properties": {
                "tipo_novedad": data.get('tipo_novedad'),
                "fecha_inicio": func.get('fecha_inicio'),
                "fecha_fin": func.get('fecha_fin'),
                "dias_otorgados": func.get('dias_otorgados'),
                "motivo": func.get('motivo')
            }
        })

    return {
        "document": filename,
        "source_file": filepath,
        "extraction_date": datetime.now().isoformat(),
        "document_type": "RESOLUCION",
        "entities": entities,
        "relationships": relationships,
        "extraction_method": extraction_method
    }


def generate_markdown(data: Dict, filepath: str, text: str, extraction_method: str) -> str:
    """Genera archivo Markdown con la información extraída"""
    filename = os.path.basename(filepath)

    md = f"""# {data.get('numero_resolucion', 'N/A')}-{data.get('anio_resolucion', 'N/A')}: {filename}

**Archivo:** `{filepath}`

**Procesado:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Método:** {extraction_method}

**Tipo de Documento:** RESOLUCIÓN

## Datos Extraídos

| Campo | Valor |
|-------|-------|
| Número Resolución | **{data.get('numero_resolucion', 'N/A')}** |
| Fecha | {data.get('fecha_resolucion', 'N/A')} |
| Código Novedad | **{data.get('codigo_novedad', 'N/A')}** |
| Tipo | {data.get('tipo_novedad', 'N/A')} |
| Remunerada | {'Sí' if data.get('es_remunerada') else 'No'} |
| Autoridad | {data.get('autoridad_firma', 'N/A')} |

## Razonamiento LLM

> {data.get('razonamiento', 'No disponible')}

"""

    # Funcionarios
    funcionarios = data.get('funcionarios', [])
    if funcionarios:
        md += "\n## Funcionarios Afectados\n\n"
        md += "| Cédula | Nombre | Cargo | Dependencia | Período | Días |\n"
        md += "|--------|--------|-------|-------------|---------|------|\n"
        for func in funcionarios:
            periodo = f"{func.get('fecha_inicio', '')} - {func.get('fecha_fin', '')}"
            md += f"| {func.get('cedula', 'N/A')} | {func.get('nombre_completo', 'N/A')} | {func.get('cargo', 'N/A')} | {func.get('dependencia', 'N/A')} | {periodo} | {func.get('dias_otorgados', 'N/A')} |\n"

    # Artículos aplicables
    articulos = data.get('articulos_aplicables', [])
    if articulos:
        md += f"\n## Marco Legal\n\nArtículos aplicables: {', '.join(map(str, articulos))}\n"

    # Observaciones
    if data.get('observaciones'):
        md += f"\n## Observaciones\n\n{data.get('observaciones')}\n"

    # Revisión humana
    if data.get('requiere_revision_humana'):
        md += f"\n## ⚠️ REQUIERE REVISIÓN HUMANA\n\n**Motivo:** {data.get('motivo_revision', 'No especificado')}\n"

    # JSON completo
    md += f"\n## JSON Completo\n\n```json\n{json.dumps(data, indent=2, ensure_ascii=False)}\n```\n"

    # Texto original
    md += f"\n## Texto Extraído\n\n```text\n{text[:3000]}\n```\n"

    return md


def save_metadata_files(data: Dict, filepath: str, text: str, extraction_method: str, output_dir: str):
    """Guarda archivos .graphrag.json y .md"""
    filename = os.path.basename(filepath)
    base_name = os.path.splitext(filename)[0]

    # Crear directorios
    graphrag_dir = os.path.join(output_dir, 'graphrag')
    md_dir = os.path.join(output_dir, 'md')
    os.makedirs(graphrag_dir, exist_ok=True)
    os.makedirs(md_dir, exist_ok=True)

    # Guardar GraphRAG JSON
    graphrag_data = generate_graphrag_json(data, filepath, extraction_method)
    graphrag_path = os.path.join(graphrag_dir, f"{base_name}.graphrag.json")
    with open(graphrag_path, 'w', encoding='utf-8') as f:
        json.dump(graphrag_data, f, indent=2, ensure_ascii=False)

    # Guardar Markdown
    md_content = generate_markdown(data, filepath, text, extraction_method)
    md_path = os.path.join(md_dir, f"{base_name}.md")
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)


# =============================================================================
# BÚSQUEDA Y PROCESAMIENTO
# =============================================================================

def find_pdfs_recursive(directory: str) -> List[str]:
    """Busca PDFs recursivamente"""
    pdf_files = []

    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith('.') and not d.startswith('~')]

        for f in files:
            if f.lower().endswith('.pdf') and not f.startswith('~') and not f.startswith('.'):
                pdf_files.append(os.path.join(root, f))

    return sorted(pdf_files)


def process_resolucion(filepath: str, conn: sqlite3.Connection, output_dir: str) -> bool:
    """Procesa una resolución individual"""
    try:
        # 1. Extraer texto
        text, method = extract_pdf_text(filepath)

        if not text or method.startswith('ERROR'):
            save_error(conn, filepath, 'EXTRACCION', method)
            return False

        filename = os.path.basename(filepath)

        # 2. Analizar con LLM
        extracted = extract_novedad_resolucion_with_llm(text, filename, conn)

        # 3. Guardar resolución en BD
        resolucion_id = save_resolucion(conn, extracted, filepath, text, method)

        # 4. Procesar funcionarios y novedades
        funcionarios = extracted.get('funcionarios', [])

        if funcionarios:
            for func_data in funcionarios:
                func_id = get_or_create_funcionario(conn, func_data)
                if func_id:
                    save_novedad_resolucion(conn, resolucion_id, func_id, extracted, func_data)
        else:
            save_novedad_resolucion(conn, resolucion_id, None, extracted, None)

        # 5. Guardar archivos de metadata
        save_metadata_files(extracted, filepath, text, method, output_dir)

        return True

    except Exception as e:
        save_error(conn, filepath, 'EXCEPCION', str(e))
        return False


def get_processed_resoluciones(conn: sqlite3.Connection) -> set:
    """Obtiene el conjunto de resoluciones ya procesadas"""
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT ruta_completa FROM resoluciones WHERE ruta_completa IS NOT NULL')
        return {row[0] for row in cursor.fetchall()}
    except sqlite3.OperationalError:
        return set()


def process_all_resoluciones(input_dir: str, output_dir: str, limit: int = None, resume: bool = True):
    """Procesa todas las resoluciones del directorio"""

    conn = sqlite3.connect(DB_PATH)

    # Inicializar tablas
    init_resoluciones_tables(conn)

    print(f"Buscando PDFs en: {input_dir}")
    all_files = find_pdfs_recursive(input_dir)
    print(f"Encontrados: {len(all_files)} archivos PDF")

    # Filtrar ya procesados
    if resume:
        processed = get_processed_resoluciones(conn)
        files = [f for f in all_files if f not in processed]
        skipped = len(all_files) - len(files)
        if skipped > 0:
            print(f"Saltando: {skipped} archivos ya procesados")
            print(f"Pendientes: {len(files)} archivos")
    else:
        files = all_files
        skipped = 0

    if limit and limit < len(files):
        files = files[:limit]
        print(f"Limitado a: {limit} archivos")

    if not files:
        print("\nNo hay archivos pendientes por procesar.")
        conn.close()
        return {'total': 0, 'ok': 0, 'error': 0, 'skipped': skipped}

    print("=" * 60)

    stats = {'total': 0, 'ok': 0, 'error': 0, 'skipped': skipped}

    for i, filepath in enumerate(files):
        stats['total'] += 1

        rel_path = os.path.relpath(filepath, input_dir)

        success = process_resolucion(filepath, conn, output_dir)

        if success:
            stats['ok'] += 1
            print(f"[{i+1}/{len(files)}] ✓ OK: {rel_path[:60]}")
        else:
            stats['error'] += 1
            print(f"[{i+1}/{len(files)}] ✗ ERROR: {rel_path[:60]}")

    conn.close()

    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN DE PROCESAMIENTO - RESOLUCIONES")
    print("=" * 60)
    print(f"Directorio: {input_dir}")
    print(f"Salida metadata: {output_dir}")
    if resume and stats['skipped'] > 0:
        print(f"Archivos saltados (ya procesados): {stats['skipped']}")
    print(f"Total procesados esta sesión: {stats['total']}")
    print(f"Exitosos: {stats['ok']} ({stats['ok']/max(stats['total'],1)*100:.1f}%)")
    print(f"Con errores: {stats['error']}")

    return stats


# =============================================================================
# VERIFICACIÓN DE SERVICIOS
# =============================================================================

def check_services(model: str = None) -> Tuple[bool, bool]:
    """Verifica disponibilidad de servicios"""

    ocr_ok = False
    try:
        resp = requests.get(f"http://{OCR_HOST}:{OCR_PORT}/v1/health/ready", timeout=10)
        ocr_ok = resp.status_code == 200
    except:
        pass

    llm_ok = False
    try:
        test = query_ollama("Responde solo OK", model=model)
        llm_ok = test is not None
    except:
        pass

    return ocr_ok, llm_ok


# =============================================================================
# CLI
# =============================================================================

def parse_args():
    """Parsea argumentos de línea de comandos"""
    parser = argparse.ArgumentParser(
        description='Extractor de novedades de RESOLUCIONES PGN',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python extract_resoluciones.py --dir-in "C:\\temp\\Decretos\\RESOLUCIONES 2024" --llm gpt-oss:120b-cloud
  python extract_resoluciones.py --dir-in "C:\\temp\\Decretos\\RESOLUCIONES -2023" --llm gpt-oss:20b-cloud --limit 50
  python extract_resoluciones.py --dir-in "C:\\temp\\Decretos\\RESOLUCIONES 2025" --output "C:\\temp\\output_res_2025"
        """
    )

    parser.add_argument(
        '--dir-in', '-d',
        type=str,
        default=DEFAULT_DIR,
        help=f'Directorio de entrada con PDFs. Default: {DEFAULT_DIR}'
    )

    parser.add_argument(
        '--output', '-o',
        type=str,
        default=OUTPUT_BASE,
        help=f'Directorio de salida para metadata. Default: {OUTPUT_BASE}'
    )

    parser.add_argument(
        '--llm', '-m',
        type=str,
        default=DEFAULT_MODEL,
        choices=['gpt-oss:120b-cloud', 'gpt-oss:20b-cloud', 'gpt-oss:20b', 'llama3.1:8b', 'qwen2.5:7b-instruct'],
        help=f'Modelo de Ollama a usar. Default: {DEFAULT_MODEL}'
    )

    parser.add_argument(
        '--limit', '-l',
        type=int,
        default=None,
        help='Límite de archivos a procesar.'
    )

    parser.add_argument(
        '--db',
        type=str,
        default=DB_PATH,
        help=f'Ruta de la base de datos SQLite. Default: {DB_PATH}'
    )

    parser.add_argument(
        '--no-resume',
        action='store_true',
        default=False,
        help='Procesar todos los archivos desde cero'
    )

    return parser.parse_args()


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    args = parse_args()

    # Configurar globales
    OLLAMA_MODEL = args.llm
    DB_PATH = args.db

    print("=" * 60)
    print("EXTRACTOR DE NOVEDADES DE RESOLUCIONES PGN")
    print("Basado en Decreto Ley 262 de 2000")
    print("=" * 60)
    print(f"Directorio entrada: {args.dir_in}")
    print(f"Directorio salida:  {args.output}")
    print(f"Modelo LLM: {args.llm}")
    print(f"Base de datos: {args.db}")
    print(f"Límite: {args.limit if args.limit else 'Sin límite'}")
    print(f"Resume: {'Desactivado' if args.no_resume else 'Activado'}")
    print()

    print("Verificando servicios...")
    ocr_ok, llm_ok = check_services(args.llm)

    print(f"  OCR (NIM PaddleOCR): {'✓ OK' if ocr_ok else '✗ NO DISPONIBLE'}")
    print(f"  LLM (Ollama/{args.llm}): {'✓ OK' if llm_ok else '✗ NO DISPONIBLE'}")

    if not llm_ok:
        print(f"\nERROR: Modelo {args.llm} no está disponible en Ollama.")
        exit(1)

    if not ocr_ok:
        print("\nADVERTENCIA: OCR no disponible. Solo se procesarán PDFs con texto nativo.")

    if not os.path.isdir(args.dir_in):
        print(f"\nERROR: Directorio no encontrado: {args.dir_in}")
        exit(1)

    # Crear directorio de salida
    os.makedirs(args.output, exist_ok=True)

    print()
    process_all_resoluciones(args.dir_in, args.output, limit=args.limit, resume=not args.no_resume)
