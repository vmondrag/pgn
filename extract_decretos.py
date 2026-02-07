"""
Script de extracción de novedades de decretos PGN
Combina extracción nativa de PDF con OCR (NIM PaddleOCR) y análisis LLM

Uso:
    python extract_decretos.py --dir-in C:\ruta\decretos --llm gpt-oss:20b-cloud
    python extract_decretos.py --dir-in C:\ruta\decretos --llm llama3.1:8b --limit 100
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

# Configuración por defecto
DB_PATH = r"C:\temp\PNG_CERTIFICADO_V3\novedades_pgn.db"
DEFAULT_DIR = r"C:\temp\PNG_CERTIFICADO_V3\Decretos"
OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "gpt-oss:20b-cloud"
OCR_HOST = "localhost"
OCR_PORT = 8000

# Variable global para modelo (se configurará via argparse)
OLLAMA_MODEL = DEFAULT_MODEL

# Intentar importar dependencias
try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False
    print("ADVERTENCIA: PyMuPDF no instalado. Ejecute: pip install pymupdf")


# =============================================================================
# FUNCIONES DE EXTRACCIÓN DE PDF
# =============================================================================

def extract_text_native(pdf_path: str) -> Tuple[Optional[str], bool]:
    """
    Extrae texto de PDF usando PyMuPDF
    Retorna: (texto, es_nativo)
    """
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
        # Si hay menos de 100 caracteres útiles, consideramos que es escaneado
        clean_text = re.sub(r'\s+', '', combined)
        is_native = len(clean_text) > 100
        
        return combined if is_native else None, is_native
        
    except Exception as e:
        print(f"Error extrayendo PDF nativo: {e}")
        return None, False


def render_page_to_base64(pdf_path: str, page_index: int = 0, dpi: int = 300) -> Optional[str]:
    """Renderiza página PDF a imagen base64 para OCR"""
    if not HAS_FITZ:
        return None
    
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
        print(f"Error renderizando página: {e}")
        return None


def ocr_with_nim(data_url: str, timeout: int = 120) -> Optional[str]:
    """
    Realiza OCR usando NIM PaddleOCR
    """
    try:
        url = f"http://{OCR_HOST}:{OCR_PORT}/v1/infer"
        payload = {"input": [{"type": "image_url", "url": data_url}]}
        
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        
        result = response.json()
        
        # Parsear respuesta OCR
        text_parts = []
        _extract_ocr_text(result, text_parts)
        
        return '\n'.join(text_parts)
        
    except requests.exceptions.ConnectionError:
        print("Error: No se puede conectar a NIM PaddleOCR en localhost:8000")
        return None
    except Exception as e:
        print(f"Error en OCR: {e}")
        return None


def _extract_ocr_text(obj, texts: List[str]):
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


def extract_pdf_text(pdf_path: str) -> Tuple[str, str]:
    """
    Extrae texto de PDF, usando nativo si es posible, OCR si no
    Retorna: (texto, método)
    """
    # Intentar extracción nativa
    text, is_native = extract_text_native(pdf_path)
    
    if is_native and text:
        return text, 'NATIVO'
    
    # Si es escaneado, usar OCR
    if not HAS_FITZ:
        return '', 'ERROR_NO_FITZ'
    
    try:
        doc = fitz.open(pdf_path)
        num_pages = len(doc)
        doc.close()
        
        all_text = []
        for i in range(min(num_pages, 10)):  # Máximo 10 páginas
            data_url = render_page_to_base64(pdf_path, i)
            if data_url:
                page_text = ocr_with_nim(data_url)
                if page_text:
                    all_text.append(page_text)
        
        if all_text:
            return '\n'.join(all_text), 'OCR'
        else:
            return '', 'ERROR_OCR'
            
    except Exception as e:
        return '', f'ERROR: {str(e)}'


# =============================================================================
# FUNCIONES DE ANÁLISIS LLM
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
                "num_predict": 2000,
            }
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        response = requests.post(OLLAMA_URL, json=payload, timeout=90)
        
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


def get_codigos_catalogo(conn: sqlite3.Connection) -> List[Dict]:
    """Obtiene el catálogo completo de códigos de novedad"""
    cursor = conn.cursor()
    cursor.execute('SELECT codigo, descripcion, tipo_general FROM codigos_novedad ORDER BY codigo')
    return [{'codigo': r[0], 'descripcion': r[1], 'tipo': r[2]} for r in cursor.fetchall()]


def get_codigos_validos_set(conn: sqlite3.Connection) -> set:
    """Obtiene set de códigos válidos para validación rápida"""
    cursor = conn.cursor()
    cursor.execute('SELECT codigo FROM codigos_novedad')
    return {r[0] for r in cursor.fetchall()}


def get_ejemplos_aprendizaje(conn: sqlite3.Connection, codigo: str = None, limit: int = 3) -> List[Dict]:
    """
    Obtiene ejemplos previos exitosos para enriquecer el prompt (few-shot learning).
    
    Args:
        conn: Conexión a la base de datos
        codigo: Código específico para buscar ejemplos similares
        limit: Número máximo de ejemplos a retornar
    """
    cursor = conn.cursor()
    try:
        if codigo:
            cursor.execute('''
                SELECT codigo_novedad, texto_ejemplo, razonamiento 
                FROM ejemplos_aprendizaje 
                WHERE codigo_novedad = ? AND confianza >= 0.8
                ORDER BY confianza DESC, fecha_creacion DESC
                LIMIT ?
            ''', (codigo, limit))
        else:
            # Obtener ejemplos diversos de diferentes códigos
            cursor.execute('''
                SELECT codigo_novedad, texto_ejemplo, razonamiento 
                FROM ejemplos_aprendizaje 
                WHERE confianza >= 0.8
                GROUP BY codigo_novedad
                ORDER BY confianza DESC
                LIMIT ?
            ''', (limit * 2,))
        
        return [{'codigo': r[0], 'texto': r[1][:400] if r[1] else '', 'razonamiento': r[2]} 
                for r in cursor.fetchall()]
    except sqlite3.OperationalError:
        return []  # Tabla no existe aún


def save_ejemplo_aprendizaje(conn: sqlite3.Connection, codigo: str, 
                              texto: str, respuesta_llm: str, razonamiento: str, 
                              filename: str, confianza: float = 1.0):
    """
    Guarda un ejemplo exitoso para aprendizaje futuro.
    Solo guarda si el código es válido y hay razonamiento.
    """
    if not codigo or not texto or codigo == 'PENDIENTE_REVISION':
        return
    
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO ejemplos_aprendizaje 
            (codigo_novedad, texto_ejemplo, respuesta_llm, razonamiento, nombre_archivo, confianza)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (codigo, texto[:2000], respuesta_llm[:2000] if respuesta_llm else None, 
              razonamiento, filename, confianza))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Ya existe un ejemplo similar


def extract_novedad_with_llm(text: str, filename: str, conn: sqlite3.Connection = None) -> Dict:
    """
    Usa LLM como FUENTE PRINCIPAL de clasificación de novedades.
    
    Mejoras v2:
    - El LLM tiene la responsabilidad principal de clasificar
    - Incluye ejemplos de aprendizaje previo (few-shot)
    - Valida códigos contra catálogo
    - Detecta nombres/apellidos por contexto (cerca de cédulas)
    - Incluye campo de razonamiento para explicar la decisión
    """
    # Obtener catálogo y ejemplos si hay conexión a BD
    codigos_catalogo = []
    codigos_validos = set()
    ejemplos = []
    
    if conn:
        codigos_catalogo = get_codigos_catalogo(conn)
        codigos_validos = get_codigos_validos_set(conn)
        
    # Obtener hint del nombre de archivo (puede ser None)
    codigo_hint = extract_codigo_from_filename(filename, codigos_validos)
    
    # Obtener ejemplos de aprendizaje previo
    if conn:
        ejemplos = get_ejemplos_aprendizaje(conn, codigo_hint)
    
    # Construir sección de ejemplos para few-shot learning
    ejemplos_str = ""
    if ejemplos:
        ejemplos_str = "\n\n=== EJEMPLOS DE CLASIFICACIONES ANTERIORES (APRENDE DE ESTOS) ===\n"
        for ej in ejemplos[:3]:
            ejemplos_str += f"\n--- Código: {ej['codigo']} ---\n"
            ejemplos_str += f"Fragmento: {ej['texto'][:300]}...\n"
            if ej.get('razonamiento'):
                ejemplos_str += f"Razonamiento: {ej['razonamiento']}\n"
    
    # Construir lista de códigos válidos para el prompt
    codigos_str = "\n".join(f"  - {c['codigo']}: {c['descripcion']} ({c['tipo']})" 
                            for c in codigos_catalogo) if codigos_catalogo else """
  - N: Nombramiento (INGRESO)
  - R: Renuncia/Retiro (RETIRO)
  - E: Encargo (MOVIMIENTO)
  - ASIG: Asignación (MOVIMIENTO)
  - REU: Renuncia Encargo (RETIRO)
  - C: Comisión (MOVIMIENTO)
  - RN: Revocatoria Nombramiento (RETIRO)
  - VADH: Vacaciones Ad Honorem (LICENCIA)
  - AC: Aceptación Comisión (MOVIMIENTO)
  - NAADH: Nombramiento Ad Honorem (INGRESO)
  - INSUB: Insubsistencia (RETIRO)
  - TE: Traslado Encargo (MOVIMIENTO)
  - TP: Traslado Provisional (MOVIMIENTO)
  - MD: Modificación Decreto (ESPECIAL)
  - RFZ: Retiro Forzoso (RETIRO)
  - REUADH: Renuncia Encargo Ad Honorem (RETIRO)"""

    system_prompt = f"""Eres un experto en análisis de decretos y actos administrativos de la 
Procuraduría General de la Nación de Colombia. Tu experiencia te permite clasificar 
novedades administrativas con alta precisión.

=== TU RESPONSABILIDAD PRINCIPAL ===
Determinar el CÓDIGO DE NOVEDAD correcto basándote en:
1. El CONTENIDO del documento (sección DECRETA o RESUELVE) - PRIORIDAD MÁXIMA
2. La ACCIÓN específica que se realiza sobre cada funcionario
3. El CONTEXTO legal colombiano de administración de personal

=== CÓDIGOS VÁLIDOS (DEBES usar EXACTAMENTE uno de estos) ===
{codigos_str}

=== REGLAS DE CLASIFICACIÓN ===
1. PRIORIZA el CONTENIDO del documento sobre el nombre del archivo
2. El nombre del archivo puede contener NOMBRES y APELLIDOS de personas (ej: "JUAN PEREZ GARCIA"),
   estos NO son códigos de novedad. Los NOMBRES siempre van acompañados de un número de CÉDULA.
3. Si hay MÚLTIPLES personas, cada una puede tener DIFERENTE acción
4. Analiza la sección "DECRETA:" o "RESUELVE:" para determinar la acción:
   - "NOMBRAR" → código N
   - "TERMINAR" vinculación/encargo → código REU o R
   - "ACEPTAR RENUNCIA" → código R
   - "ENCARGAR" → código E
   - "TRASLADAR" → código TRAS o TP
   - "DECLARAR INSUBSISTENTE" → código INSUB
5. Si no puedes determinar con certeza, usa código "PENDIENTE_REVISION"

=== IMPORTANTE: RAZONAMIENTO ===
DEBES explicar brevemente POR QUÉ elegiste el código. Esto ayuda al aprendizaje del sistema.

Responde SOLO con JSON válido, sin explicaciones adicionales fuera del JSON."""

    prompt = f"""Analiza el siguiente decreto y extrae TODAS las novedades.
{ejemplos_str}

=== INFORMACIÓN DEL ARCHIVO ===
Nombre de archivo (CORRELACIONA con contenido): {filename}
Código sugerido por archivo (puede ser INCORRECTO): {codigo_hint or 'No detectado'}

=== INSTRUCCIONES CRÍTICAS SOBRE NÚMERO DE DECRETO Y AÑO ===
1. El NÚMERO DE DECRETO y el AÑO son campos SEPARADOS. NUNCA los concatenes.
   - CORRECTO: numero_decreto="2297", anio_decreto=2009
   - INCORRECTO: numero_decreto="22972009"
   
2. ANALIZA el nombre del archivo para inferir el número de decreto:
   - Si el archivo es "DECRETO 2297-2009.pdf" → numero_decreto="2297"
   - Si el archivo es "022-2009.pdf" → numero_decreto="022"
   - CORRELACIONA el nombre del archivo con el contenido del documento.

3. El año puede extraerse de:
   - El nombre del archivo (ej: "-2009.pdf")
   - El encabezado del decreto (ej: "Decreto 2297 del 15 de enero de 2009")
   - El directorio de origen (esto lo hace el sistema)

4. Si hay INCONSISTENCIA entre el número en el archivo y el contenido (errores de OCR),
   PRIORIZA el nombre del archivo ya que es más confiable.

=== TEXTO COMPLETO DEL DOCUMENTO ===
{text[:6500]}

=== INSTRUCCIONES DE RAZONAMIENTO ===
1. LEE cuidadosamente la sección "DECRETA:" o "RESUELVE:"
2. IDENTIFICA qué ACCIÓN se toma para cada persona mencionada
3. DETERMINA el código de novedad basándote en la ACCIÓN, NO en el nombre del archivo
4. Si el nombre del archivo parece ser un nombre de persona (ej: "MARIA LOPEZ 1234.pdf"), 
   el código debe determinarse por el CONTENIDO, no por el nombre
5. EXTRAE la fecha completa: día, mes y año por separado

=== EXTRAER en formato JSON ===
{{
    "razonamiento": "Explica brevemente: ¿Qué acción se toma? ¿Por qué elegiste este código?",
    "numero_decreto": "SOLO el número del decreto SIN el año (ej: 2297, 022, 571)",
    "fecha_decreto": "fecha completa del documento (ej: 15 de enero de 2009)",
    "dia_decreto": 15,
    "mes_decreto": 1,
    "anio_decreto": 2009,
    "tipo_documento": "DECRETO | RESOLUCION | ACTO ADMINISTRATIVO",
    "codigo_novedad_determinado": "CÓDIGO del catálogo que mejor aplica según el CONTENIDO",
    "funcionarios": [
        {{
            "cedula": "número de cédula (solo números, sin puntos)",
            "nombres": "nombres de pila",
            "apellidos": "apellidos",
            "nombre_completo": "nombre completo como aparece",
            "accion_especifica": "qué se decreta para esta persona (ej: NOMBRAR, TERMINAR, ACEPTAR renuncia)",
            "cargo": "cargo del funcionario",
            "codigo_cargo": "código del cargo si aparece (ej: 1AS-19)",
            "grado": "grado del cargo si aparece",
            "dependencia": "dependencia o área",
            "sede": "ciudad o regional",
            "fecha_efectos": "desde cuándo aplica la acción",
            "fecha_hasta": "hasta cuándo si aplica",
            "tipo_vinculacion": "provisional | carrera | ad honorem | encargo",
            "articulo_aplicable": "número del artículo del decreto que le aplica",
            "codigo_novedad_individual": "código específico si es diferente al general"
        }}
    ],
    "novedad_general": {{
        "codigo": "código determinado por TI (el LLM) basado en el CONTENIDO",
        "tipo": "tipo general (Nombramiento, Renuncia, Encargo, Terminación, etc.)",
        "descripcion_general": "resumen del decreto",
        "observaciones": "notas adicionales importantes"
    }}
}}

IMPORTANTE: 
- El código en "novedad_general.codigo" DEBE ser uno de los códigos válidos listados arriba.
- El "numero_decreto" DEBE ser SOLO el número, SIN el año concatenado.
Responde ÚNICAMENTE con el JSON válido:"""

    response = query_ollama(prompt, system_prompt)
    response_raw = response  # Guardar para aprendizaje
    
    if response:
        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                result = json.loads(json_match.group())
                
                # Extraer código determinado por el LLM
                codigo_llm = result.get('codigo_novedad_determinado') or \
                             result.get('novedad_general', {}).get('codigo')
                
                # Validar código contra catálogo
                if codigos_validos and codigo_llm and codigo_llm not in codigos_validos:
                    if codigo_llm != 'PENDIENTE_REVISION':
                        result['novedad_general'] = result.get('novedad_general', {})
                        result['novedad_general']['codigo_original'] = codigo_llm
                        result['novedad_general']['codigo'] = 'PENDIENTE_REVISION'
                        result['novedad_general']['observaciones'] = \
                            f"Código '{codigo_llm}' no está en catálogo. Requiere revisión."
                
                # Normalizar estructura para compatibilidad
                if 'novedad_general' in result and 'novedad' not in result:
                    result['novedad'] = result['novedad_general']
                
                # Guardar ejemplo para aprendizaje si es exitoso
                codigo_final = result.get('novedad', {}).get('codigo')
                razonamiento = result.get('razonamiento', '')
                if conn and codigo_final and codigo_final != 'PENDIENTE_REVISION':
                    save_ejemplo_aprendizaje(
                        conn, codigo_final, text[:1500], response_raw, 
                        razonamiento, filename, 0.9
                    )
                
                return result
                
        except json.JSONDecodeError as e:
            print(f"Error parseando JSON del LLM: {e}")
    
    return {
        'numero_decreto': None,
        'fecha_decreto': None,
        'funcionarios': [],
        'novedad': {'codigo': 'PENDIENTE_REVISION', 'observaciones': 'Error en extracción LLM'},
        'razonamiento': 'No se pudo obtener respuesta válida del LLM'
    }


def extract_codigo_from_filename(filename: str, codigos_validos: set = None) -> Optional[str]:
    """
    Extrae HINT de código del nombre del archivo.
    Usa detección contextual: los nombres/apellidos van acompañados de cédulas.
    Solo retorna códigos si están en el catálogo válido.
    
    Args:
        filename: Nombre del archivo PDF
        codigos_validos: Set de códigos válidos del catálogo (opcional)
    
    Returns:
        Código válido o None si no puede determinarse con certeza
    """
    # Palabras que definitivamente NO son códigos
    PALABRAS_EXCLUIR = {
        'DE', 'DEL', 'LA', 'LAS', 'LOS', 'Y', 'OTRO', 'OTROS', 'CON', 'SIN',
        'DECRETO', 'RESOLUCION', 'ACTO', 'ADMINISTRATIVO', 'PDF'
    }
    
    text = filename.replace('.pdf', '').replace('.PDF', '')
    parts = text.split()
    
    # Buscar patrón: si hay un número largo (cédula), las palabras cercanas son nombres
    cedula_pattern = re.compile(r'\b\d{6,10}\b')
    tiene_cedula = cedula_pattern.search(text) is not None
    
    # Buscar código al final del nombre de archivo
    for i, part in enumerate(reversed(parts)):
        part_upper = part.upper().strip('.,;:')
        
        # Saltar números (incluye año, cédula, número de decreto)
        if part_upper.isdigit() or re.match(r'^\d+$', part_upper):
            continue
        
        # Saltar palabras excluidas
        if part_upper in PALABRAS_EXCLUIR:
            continue
        
        # Si el archivo tiene cédula, las palabras en mayúsculas largas son probablemente nombres
        if tiene_cedula and len(part_upper) > 4:
            # Palabras largas cerca de cédulas son probablemente nombres/apellidos
            continue
        
        # Validar contra catálogo si está disponible
        if codigos_validos:
            if part_upper in codigos_validos:
                return part_upper
        else:
            # Sin catálogo, aceptar solo códigos cortos típicos
            if len(part_upper) <= 6 and part_upper.isupper() and part_upper.isalpha():
                return part_upper
    
    return None  # El LLM decidirá


def extract_year_from_path(filepath: str) -> Optional[int]:
    r"""
    Extrae el año del path del directorio.
    Soporta: \2009\, \DECRETOS 2021\, \DECRETO 2024\, etc.
    
    Args:
        filepath: Ruta completa al archivo
        
    Returns:
        Año como entero o None
    """
    parts = filepath.replace('\\', '/').split('/')
    
    for p in parts:
        p_upper = p.upper()
        # Buscar directorio que sea solo año (ej: 2009)
        if re.match(r'^\d{4}$', p):
            year = int(p)
            if 2000 <= year <= 2030:
                return year
        
        # Buscar año en directorios como "DECRETOS 2021" o "DECRETO 2024"
        if 'DECRETO' in p_upper or 'RESOLUCI' in p_upper:
            match = re.search(r'(\d{4})', p)
            if match:
                year = int(match.group(1))
                if 2000 <= year <= 2030:
                    return year
    
    return None


def parse_filename_decree_info(filename: str, year_from_path: int = None) -> Dict:
    """
    Extrae información del decreto desde el nombre del archivo.
    
    Patrones soportados:
    - DECRETO 2297-2009.pdf → decreto=2297, año=2009
    - 022-2009.pdf → decreto=022, año=2009
    - DECRETO 571 DE 2009.pdf → decreto=571, año=2009
    
    Args:
        filename: Nombre del archivo PDF
        year_from_path: Año extraído del directorio (fuente de verdad)
        
    Returns:
        Dict con 'numero_decreto' y 'anio' (pueden ser None)
    """
    result = {'numero_decreto': None, 'anio': year_from_path}
    
    # Limpiar nombre
    name = filename.replace('.pdf', '').replace('.PDF', '').strip()
    
    # Patrón 1: DECRETO XXXX-YYYY o XXXX-YYYY
    match = re.search(r'(\d{1,5})\s*[-_]\s*(\d{4})', name)
    if match:
        result['numero_decreto'] = match.group(1).zfill(4) if len(match.group(1)) < 4 else match.group(1)
        year_from_name = int(match.group(2))
        if 2000 <= year_from_name <= 2030:
            # Usar año del directorio si está disponible, sino del nombre
            result['anio'] = year_from_path or year_from_name
        return result
    
    # Patrón 2: DECRETO XXXX DE YYYY
    match = re.search(r'DECRETO\s+(\d{1,5})\s+DE\s+(\d{4})', name, re.IGNORECASE)
    if match:
        result['numero_decreto'] = match.group(1).zfill(4) if len(match.group(1)) < 4 else match.group(1)
        year_from_name = int(match.group(2))
        if 2000 <= year_from_name <= 2030:
            result['anio'] = year_from_path or year_from_name
        return result
    
    # Patrón 3: Solo DECRETO XXXX (sin año)
    match = re.search(r'DECRETO\s+(\d{1,5})(?!\d)', name, re.IGNORECASE)
    if match:
        result['numero_decreto'] = match.group(1).zfill(4) if len(match.group(1)) < 4 else match.group(1)
        return result
    
    return result


def separate_concatenated_decree(value: str, year_from_path: int = None) -> Tuple[str, int]:
    """
    Separa un número de decreto concatenado con el año.
    
    Ejemplos:
    - "22972009" con year_from_path=2009 → ("2297", 2009)
    - "0222009" con year_from_path=2009 → ("022", 2009)
    - "2817" (no concatenado) → ("2817", year_from_path)
    
    Args:
        value: Valor del decreto (puede estar concatenado)
        year_from_path: Año del directorio (fuente de verdad)
        
    Returns:
        Tuple de (numero_decreto, año)
    """
    if not value:
        return None, year_from_path
    
    # Limpiar a solo dígitos
    clean = re.sub(r'[^\d]', '', str(value))
    
    if not clean:
        return None, year_from_path
    
    # Si termina en un año válido (2009-2025) y tiene más de 4 dígitos
    if len(clean) > 4:
        for year in range(2009, 2026):
            year_str = str(year)
            if clean.endswith(year_str):
                decreto = clean[:-4]
                # Verificar que el decreto resultante es razonable
                if decreto and int(decreto) < 10000:
                    # Si tenemos año del path, usarlo para validar
                    if year_from_path and year == year_from_path:
                        return decreto.zfill(4) if len(decreto) < 4 else decreto, year
                    elif not year_from_path:
                        return decreto.zfill(4) if len(decreto) < 4 else decreto, year
    
    # No está concatenado, retornar como está
    return clean, year_from_path


# =============================================================================
# FUNCIONES DE BASE DE DATOS
# =============================================================================

def get_or_create_funcionario(conn: sqlite3.Connection, data: Dict) -> Optional[int]:
    """
    Obtiene o crea un funcionario en la BD.
    Verifica existencia por cédula antes de insertar para evitar duplicados.
    """
    cursor = conn.cursor()
    
    cedula = data.get('cedula')
    if cedula:
        # Limpiar cédula: quitar puntos, espacios, y caracteres no numéricos
        cedula = re.sub(r'[^\d]', '', str(cedula))
    
    nombres = data.get('nombres', '')
    apellidos = data.get('apellidos', '')
    nombre_completo = data.get('nombre_completo') or f"{nombres} {apellidos}".strip()
    
    if not nombre_completo and not cedula:
        return None
    
    # Primero verificar si ya existe por cédula
    if cedula:
        cursor.execute('SELECT id FROM funcionarios WHERE cedula = ?', (cedula,))
        row = cursor.fetchone()
        if row:
            # Actualizar nombre si está vacío
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
    
    # Verificar si existe por nombre completo (sin cédula)
    if nombre_completo and not cedula:
        cursor.execute('SELECT id FROM funcionarios WHERE nombre_completo = ? AND cedula IS NULL', (nombre_completo,))
        row = cursor.fetchone()
        if row:
            return row[0]
    
    # Insertar nuevo funcionario
    try:
        cursor.execute('''
            INSERT INTO funcionarios (cedula, nombres, apellidos, nombre_completo)
            VALUES (?, ?, ?, ?)
        ''', (cedula, nombres, apellidos, nombre_completo))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        # Si falla por duplicado, buscar el existente
        if cedula:
            cursor.execute('SELECT id FROM funcionarios WHERE cedula = ?', (cedula,))
            row = cursor.fetchone()
            if row:
                return row[0]
        return None


def save_decreto(conn: sqlite3.Connection, data: Dict, filepath: str, 
                 text: str, extraction_method: str) -> int:
    """
    Guarda un decreto en la BD.
    
    Mejoras:
    - Extrae año del directorio usando extract_year_from_path()
    - Parsea decreto del nombre de archivo usando parse_filename_decree_info()
    - Separa valores concatenados usando separate_concatenated_decree()
    - Extrae fecha completa (día, mes, año) del texto
    """
    cursor = conn.cursor()
    
    filename = os.path.basename(filepath)
    
    # 1. Extraer año del directorio (FUENTE DE VERDAD)
    anio_path = extract_year_from_path(filepath)
    
    # 2. Extraer info del nombre del archivo
    filename_info = parse_filename_decree_info(filename, anio_path)
    
    # 3. Obtener número de decreto del LLM
    numero_decreto_llm = data.get('numero_decreto')
    
    # 4. Determinar número de decreto y año final
    numero_decreto = None
    anio = anio_path  # Año del directorio es la fuente de verdad
    
    if numero_decreto_llm:
        # Verificar si el LLM concatenó decreto con año
        decreto_separado, anio_separado = separate_concatenated_decree(
            numero_decreto_llm, anio_path
        )
        
        if decreto_separado:
            numero_decreto = decreto_separado
            # Si no tenemos año del path, usar el separado
            if not anio and anio_separado:
                anio = anio_separado
    
    # 5. Si no hay decreto del LLM, usar el del nombre de archivo
    if not numero_decreto and filename_info.get('numero_decreto'):
        numero_decreto = filename_info['numero_decreto']
    
    # 6. Asegurar que el año está definido
    if not anio and filename_info.get('anio'):
        anio = filename_info['anio']
    
    # 7. Extraer componentes de fecha del decreto
    dia_decreto = None
    mes_decreto = None
    anio_decreto = anio
    
    fecha_texto = data.get('fecha_decreto', '')
    if fecha_texto:
        # Intentar extraer día
        match_dia = re.search(r'(\d{1,2})\s+de\s+', fecha_texto, re.IGNORECASE)
        if match_dia:
            dia_decreto = int(match_dia.group(1))
        
        # Intentar extraer mes
        meses = {
            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
            'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
            'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
        }
        fecha_lower = fecha_texto.lower()
        for mes_nombre, mes_num in meses.items():
            if mes_nombre in fecha_lower:
                mes_decreto = mes_num
                break
        
        # Intentar extraer año de la fecha si no lo tenemos
        match_anio = re.search(r'(\d{4})', fecha_texto)
        if match_anio and not anio_decreto:
            anio_candidato = int(match_anio.group(1))
            if 2000 <= anio_candidato <= 2030:
                anio_decreto = anio_candidato
    
    # Asegurarse que anio_decreto = anio (consistencia)
    if not anio_decreto:
        anio_decreto = anio
    if not anio:
        anio = anio_decreto
    
    cursor.execute('''
        INSERT INTO decretos (
            numero_decreto, fecha_decreto_texto, anio,
            dia_decreto, mes_decreto, anio_decreto,
            archivo_origen, ruta_completa, tipo_extraccion,
            contenido_texto, tiene_multiples_funcionarios
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        numero_decreto,
        data.get('fecha_decreto'),
        anio,
        dia_decreto,
        mes_decreto,
        anio_decreto,
        filename,
        filepath,
        extraction_method,
        text,
        len(data.get('funcionarios', [])) > 1
    ))
    
    conn.commit()
    return cursor.lastrowid


def save_novedad(conn: sqlite3.Connection, decreto_id: int, 
                 funcionario_id: int, novedad: Dict, func_data: Dict = None):
    """
    Guarda una novedad en la BD.
    func_data: datos específicos del funcionario si el LLM extrajo info individual.
    """
    cursor = conn.cursor()
    
    # Si hay datos específicos del funcionario, usarlos; si no, usar novedad general
    cargo = (func_data.get('cargo') if func_data else None) or novedad.get('cargo')
    codigo_cargo = (func_data.get('codigo_cargo') if func_data else None) or novedad.get('codigo_cargo')
    grado = (func_data.get('grado') if func_data else None) or novedad.get('grado')
    dependencia = (func_data.get('dependencia') if func_data else None) or novedad.get('dependencia')
    sede = (func_data.get('sede') if func_data else None) or novedad.get('sede')
    fecha_inicio = (func_data.get('fecha_efectos') if func_data else None) or novedad.get('fecha_inicio')
    fecha_fin = (func_data.get('fecha_hasta') if func_data else None) or novedad.get('fecha_fin')
    tipo_vinculacion = func_data.get('tipo_vinculacion') if func_data else None
    accion = func_data.get('accion_especifica') if func_data else None
    
    # Construir observaciones combinando info
    observaciones_parts = []
    if accion:
        observaciones_parts.append(f"Acción: {accion}")
    if tipo_vinculacion:
        observaciones_parts.append(f"Vinculación: {tipo_vinculacion}")
    if novedad.get('observaciones'):
        observaciones_parts.append(novedad.get('observaciones'))
    if func_data and func_data.get('articulo_aplicable'):
        observaciones_parts.append(f"Artículo: {func_data.get('articulo_aplicable')}")
    
    observaciones = '. '.join(observaciones_parts) if observaciones_parts else None
    
    cursor.execute('''
        INSERT INTO novedades (
            decreto_id, funcionario_id, codigo_novedad, tipo_novedad,
            descripcion_novedad, cargo_actual, codigo_cargo, grado_cargo,
            dependencia, sede, fecha_inicio_texto, fecha_fin_texto,
            es_provisional, observaciones, confianza_extraccion
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        decreto_id,
        funcionario_id,
        novedad.get('codigo'),
        novedad.get('tipo'),
        novedad.get('descripcion') or novedad.get('descripcion_general'),
        cargo,
        codigo_cargo,
        grado,
        dependencia,
        sede,
        fecha_inicio,
        fecha_fin,
        tipo_vinculacion == 'provisional' if tipo_vinculacion else novedad.get('es_provisional', False),
        observaciones,
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
# FUNCIONES DE BÚSQUEDA RECURSIVA
# =============================================================================

def find_pdfs_recursive(directory: str) -> List[str]:
    """
    Busca PDFs recursivamente en todo el árbol de directorios
    Retorna lista de rutas completas a archivos PDF
    """
    pdf_files = []
    
    for root, dirs, files in os.walk(directory):
        # Filtrar directorios ocultos o de sistema
        dirs[:] = [d for d in dirs if not d.startswith('.') and not d.startswith('~')]
        
        for f in files:
            if f.lower().endswith('.pdf') and not f.startswith('~') and not f.startswith('.'):
                pdf_files.append(os.path.join(root, f))
    
    return sorted(pdf_files)


# =============================================================================
# PROCESAMIENTO PRINCIPAL
# =============================================================================

def process_decreto(filepath: str, conn: sqlite3.Connection) -> bool:
    """Procesa un decreto individual"""
    try:
        # 1. Extraer texto
        text, method = extract_pdf_text(filepath)
        
        if not text or method.startswith('ERROR'):
            save_error(conn, filepath, 'EXTRACCION', method)
            return False
        
        filename = os.path.basename(filepath)
        
        # 2. Analizar con LLM (pasando conexión BD para aprendizaje y catálogo)
        extracted = extract_novedad_with_llm(text, filename, conn)
        
        # 3. Guardar decreto
        decreto_id = save_decreto(conn, extracted, filepath, text, method)
        
        # 4. Procesar funcionarios y novedades
        funcionarios = extracted.get('funcionarios', [])
        novedad = extracted.get('novedad', {})
        
        if funcionarios:
            for func_data in funcionarios:
                func_id = get_or_create_funcionario(conn, func_data)
                if func_id:
                    # Pasar datos individuales del funcionario a save_novedad
                    save_novedad(conn, decreto_id, func_id, novedad, func_data)
        else:
            save_novedad(conn, decreto_id, None, novedad, None)
        
        return True
        
    except Exception as e:
        save_error(conn, filepath, 'EXCEPCION', str(e))
        return False


def get_processed_files(conn: sqlite3.Connection) -> set:
    """Obtiene el conjunto de archivos ya procesados en la BD"""
    cursor = conn.cursor()
    cursor.execute('SELECT ruta_completa FROM decretos WHERE ruta_completa IS NOT NULL')
    return {row[0] for row in cursor.fetchall()}


def process_all_decretos(input_dir: str, limit: int = None, resume: bool = True):
    """
    Procesa todos los decretos del directorio (recursivamente)
    
    Args:
        input_dir: Directorio de entrada
        limit: Límite de archivos a procesar (después de filtrar ya procesados)
        resume: Si True, salta archivos ya procesados en la BD
    """
    
    conn = sqlite3.connect(DB_PATH)
    
    # Buscar PDFs recursivamente
    print(f"Buscando PDFs en: {input_dir}")
    all_files = find_pdfs_recursive(input_dir)
    print(f"Encontrados: {len(all_files)} archivos PDF")
    
    # Filtrar archivos ya procesados si resume=True
    if resume:
        processed = get_processed_files(conn)
        files = [f for f in all_files if f not in processed]
        skipped = len(all_files) - len(files)
        if skipped > 0:
            print(f"Saltando: {skipped} archivos ya procesados")
            print(f"Pendientes: {len(files)} archivos")
    else:
        files = all_files
    
    if limit and limit < len(files):
        files = files[:limit]
        print(f"Limitado a: {limit} archivos")
    
    if not files:
        print("\nNo hay archivos pendientes por procesar.")
        conn.close()
        return {'total': 0, 'ok': 0, 'error': 0, 'skipped': skipped if resume else 0}
    
    print("=" * 60)
    
    stats = {'total': 0, 'ok': 0, 'error': 0, 'skipped': skipped if resume else 0}
    
    for i, filepath in enumerate(files):
        stats['total'] += 1
        
        # Mostrar ruta relativa para claridad
        rel_path = os.path.relpath(filepath, input_dir)
        
        success = process_decreto(filepath, conn)
        
        if success:
            stats['ok'] += 1
            print(f"[{i+1}/{len(files)}] OK: {rel_path[:60]}")
        else:
            stats['error'] += 1
            print(f"[{i+1}/{len(files)}] ERROR: {rel_path[:60]}")
    
    conn.close()
    
    # Generar reporte
    print("\n" + "=" * 60)
    print("RESUMEN DE PROCESAMIENTO")
    print("=" * 60)
    print(f"Directorio: {input_dir}")
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
    """Verifica disponibilidad de servicios OCR y LLM"""
    
    # Verificar OCR
    ocr_ok = False
    try:
        resp = requests.get(f"http://{OCR_HOST}:{OCR_PORT}/v1/health/ready", timeout=10)
        ocr_ok = resp.status_code == 200
    except:
        pass
    
    # Verificar Ollama con el modelo especificado
    llm_ok = False
    try:
        test = query_ollama("Responde solo OK", model=model)
        llm_ok = test is not None
    except:
        pass
    
    return ocr_ok, llm_ok


# =============================================================================
# CLI - ARGUMENTOS DE LÍNEA DE COMANDOS
# =============================================================================

def parse_args():
    """Parsea argumentos de línea de comandos"""
    parser = argparse.ArgumentParser(
        description='Extractor de novedades de decretos PGN',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python extract_decretos.py --dir-in C:\\temp\\Decretos --llm gpt-oss:20b-cloud
  python extract_decretos.py --dir-in C:\\temp\\Decretos --llm llama3.1:8b --limit 100
  python extract_decretos.py --dir-in C:\\temp\\Decretos --llm qwen2.5:7b-instruct
        """
    )
    
    parser.add_argument(
        '--dir-in', '-d',
        type=str,
        default=DEFAULT_DIR,
        help=f'Directorio de entrada con PDFs (búsqueda recursiva). Default: {DEFAULT_DIR}'
    )
    
    parser.add_argument(
        '--llm', '-m',
        type=str,
        default=DEFAULT_MODEL,
        choices=['gpt-oss:20b-cloud', 'gpt-oss:20b', 'gpt-oss:120b-cloud', 'llama3.1:8b', 'qwen2.5:7b-instruct'],
        help=f'Modelo de Ollama a usar. Default: {DEFAULT_MODEL}'
    )
    
    parser.add_argument(
        '--limit', '-l',
        type=int,
        default=None,
        help='Límite de archivos a procesar. Sin límite si no se especifica.'
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
        help='Procesar todos los archivos desde cero (ignorar archivos ya procesados)'
    )
    
    return parser.parse_args()


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    args = parse_args()
    
    # Configurar modelo y BD globalmente
    OLLAMA_MODEL = args.llm
    db_path = args.db
    
    print("=" * 60)
    print("EXTRACTOR DE NOVEDADES DE DECRETOS PGN")
    print("=" * 60)
    print(f"Directorio entrada: {args.dir_in}")
    print(f"Modelo LLM: {args.llm}")
    print(f"Base de datos: {db_path}")
    print(f"Límite: {args.limit if args.limit else 'Sin límite'}")
    print(f"Resume: {'Desactivado' if args.no_resume else 'Activado (salta archivos ya procesados)'}")
    print()
    
    print("Verificando servicios...")
    ocr_ok, llm_ok = check_services(args.llm)
    
    print(f"  OCR (NIM PaddleOCR): {'OK' if ocr_ok else 'NO DISPONIBLE'}")
    print(f"  LLM (Ollama/{args.llm}): {'OK' if llm_ok else 'NO DISPONIBLE'}")
    
    if not llm_ok:
        print(f"\nERROR: Modelo {args.llm} no está disponible en Ollama.")
        print("Verifique que Ollama esté ejecutándose y el modelo cargado.")
        exit(1)
    
    if not ocr_ok:
        print("\nADVERTENCIA: OCR no disponible. Solo se procesarán PDFs con texto nativo.")
    
    # Verificar directorio
    if not os.path.isdir(args.dir_in):
        print(f"\nERROR: Directorio no encontrado: {args.dir_in}")
        exit(1)
    
    print()
    process_all_decretos(args.dir_in, limit=args.limit, resume=not args.no_resume)
