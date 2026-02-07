"""
Extracción Híbrida de Decretos (Estrategia E3)
- OCR DPI 150
- Metadata del filename (número decreto, año)
- Estructuración con LLM (Ollama local o Azure OpenAI)
- Integración con BD novedades_pgn.db
- Generación de archivos .md y .graphrag.json
"""
import os
import re
import json
import base64
import sqlite3
import requests
import fitz  # PyMuPDF
from datetime import datetime
from typing import Dict, Optional, Tuple, List

# Importar OpenAI SDK (opcional para Azure)
try:
    from openai import AzureOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    print("NOTA: SDK OpenAI no instalado. Use 'pip install openai' para Azure OpenAI.")

# Configuración OCR
OCR_HOST = "localhost"
OCR_PORT = 8000

# Configuración Ollama (LLM local)
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gpt-oss:20b-cloud"  # Default, puede cambiarse con --llm

# Configuración Azure OpenAI
AZURE_ENDPOINT = "https://iacertificaciones.cognitiveservices.azure.com/"
AZURE_API_KEY = os.environ.get("AZURE_API_KEY", "")
AZURE_API_VERSION = "2024-12-01-preview"
AZURE_MODEL = "gpt-5-mini"
USE_AZURE = False  # Se activa con --llm_azure

# Paths
DB_PATH = r"C:\temp\PNG_CERTIFICADO_V3\novedades_pgn.db"
OUTPUT_DIR = r"C:\temp\PNG_CERTIFICADO_V3\output_2009_hybrid"



def ensure_dir(path: str):
    if not os.path.exists(path):
        os.makedirs(path)


# =============================================================================
# EXTRACCIÓN DE METADATA DEL FILENAME
# =============================================================================

def extract_filename_metadata(filename: str) -> Dict:
    """
    Extrae número de decreto y año del nombre del archivo.
    Ejemplos:
        DECRETO 001-2009.pdf -> {numero: '001', anio: 2009}
        DECRETO 003 2009.pdf -> {numero: '003', anio: 2009}
    """
    result = {'numero_decreto': None, 'anio': None, 'filename': filename}
    
    # Limpiar extensión
    name = filename.replace('.pdf', '').replace('.PDF', '')
    
    # Patrón 1: DECRETO 001-2009 o DECRETO 001 2009
    match = re.search(r'DECRETO\s*(\d{1,5})[\s_-]+(\d{4})', name, re.IGNORECASE)
    if match:
        result['numero_decreto'] = match.group(1).zfill(3)  # Normalizar a 3 dígitos
        result['anio'] = int(match.group(2))
        return result
    
    # Patrón 2: Solo números como 001-2009
    match = re.search(r'(\d{1,5})[\s_-]+(\d{4})', name)
    if match:
        result['numero_decreto'] = match.group(1).zfill(3)
        result['anio'] = int(match.group(2))
    
    return result


# =============================================================================
# OCR
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
    """OCR usando NIM PaddleOCR"""
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


def extract_pdf_ocr(pdf_path: str, max_pages: int = 3) -> Tuple[str, str]:
    """Extrae texto de PDF usando OCR"""
    try:
        doc = fitz.open(pdf_path)
        num_pages = min(len(doc), max_pages)
        doc.close()
        
        all_text = []
        for i in range(num_pages):
            img_bytes = render_page_to_bytes(pdf_path, i, dpi=150)
            page_text = ocr_from_bytes(img_bytes)
            if page_text:
                all_text.append(page_text)
        
        if all_text:
            return '\n'.join(all_text), 'OCR_DPI150'
        return '', 'ERROR_OCR'
    except Exception as e:
        return '', f'ERROR_OCR: {e}'


# =============================================================================
# LLM ESTRUCTURACIÓN CON FEW-SHOT LEARNING
# =============================================================================

def get_ejemplos_aprendizaje(conn, codigo: str = None, limit: int = 3):
    """
    Obtiene ejemplos previos exitosos de la BD para few-shot learning.
    """
    if not conn:
        return []
    
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
    except:
        return []


def save_ejemplo_aprendizaje(conn, codigo: str, texto: str, razonamiento: str, filename: str):
    """Guarda un ejemplo exitoso para aprendizaje futuro."""
    if not conn or not codigo or codigo == 'PENDIENTE_REVISION':
        return
    
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO ejemplos_aprendizaje 
            (codigo_novedad, texto_ejemplo, razonamiento, nombre_archivo, confianza)
            VALUES (?, ?, ?, ?, 0.9)
        ''', (codigo, texto[:2000], razonamiento, filename))
        conn.commit()
    except:
        pass


def call_azure_openai(prompt: str, system_prompt: str = None) -> Optional[str]:
    """
    Llama a Azure OpenAI GPT-5-mini para procesar el prompt.
    Retorna la respuesta del modelo o None si falla.
    """
    global AZURE_ENDPOINT, AZURE_API_KEY, AZURE_API_VERSION, AZURE_MODEL
    
    if not HAS_OPENAI:
        print("ERROR: SDK OpenAI no instalado. Ejecute: pip install openai")
        return None
    
    try:
        client = AzureOpenAI(
            api_version=AZURE_API_VERSION,
            azure_endpoint=AZURE_ENDPOINT,
            api_key=AZURE_API_KEY,
        )
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = client.chat.completions.create(
            model=AZURE_MODEL,
            messages=messages,
            max_completion_tokens=2500
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        print(f"Error Azure OpenAI: {e}")
        return None


def call_ollama(prompt: str) -> Optional[str]:
    """
    Llama a Ollama local para procesar el prompt.
    Retorna la respuesta del modelo o None si falla.
    """
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 2500}
        }
        
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        if response.status_code == 200:
            return response.json().get('response', '')
    except Exception as e:
        print(f"Error Ollama: {e}")
    
    return None


def extract_with_llm(text: str, filename_meta: Dict, conn = None) -> Dict:
    """
    Usa LLM para extraer datos estructurados.
    V3 OPTIMIZADA - Soporta Ollama local o Azure OpenAI con --llm_azure.
    """
    
    # Obtener ejemplos de aprendizaje previo para few-shot
    ejemplos = get_ejemplos_aprendizaje(conn) if conn else []
    
    ejemplos_str = ""
    if ejemplos:
        ejemplos_str = "\n\n=== EJEMPLOS DE CLASIFICACIONES ANTERIORES (APRENDE DE ESTOS) ===\n"
        for ej in ejemplos[:3]:
            ejemplos_str += f"\n--- Ejemplo {ej['codigo']} ---\n"
            ejemplos_str += f"Texto: {ej['texto'][:250]}...\n"
            if ej.get('razonamiento'):
                ejemplos_str += f"Razonamiento: {ej['razonamiento']}\n"
    
    # Construir prompt V3 OPTIMIZADO con todos los tipos de decreto
    prompt = f"""Eres un experto legal en análisis de decretos de la Procuraduría General de la Nación (PGN) de Colombia.

=== CONTEXTO LEGAL ===
Marco normativo: Ley 909 de 2004, Decreto 262 de 2000, Art. 125 Constitución.
Los decretos regulan novedades de personal: nombramientos, encargos, renuncias, asignaciones, prórrogas, etc.

=== INFORMACIÓN DEL DECRETO ===
- Número: {filename_meta.get('numero_decreto', 'desconocido')}
- Año: {filename_meta.get('anio', 'desconocido')}
- Archivo: {filename_meta.get('filename', '')}
{ejemplos_str}

=== TEXTO OCR (puede tener errores) ===
{text[:5000]}

=== ERRORES OCR COMUNES - SEPARA MENTALMENTE ===
- "GENERALDELANACION" = "GENERAL DE LA NACION"
- "25MAR2014" = "25 MAR 2014"
- "27AG02009" = "27 AGO 2009"
- "No.43.168.876" = cédula 43168876
- "Codigo50FGrado06" = "Codigo 5OF Grado 06"
- "OficinistaCodigo" = "Oficinista Codigo"

=== TIPOS DE DECRETO ===

1. NOMBRAMIENTO (N):
   Patrón: "Nombrar en Provisionalidad, a [NOMBRE], cedula [X], en el cargo de [CARGO]"
   → cargo = cargo al que se nombra
   → "en el cargo de [PERSONA]" = persona reemplazada (sin novedad)

2. ENCARGO (E):
   Patrón: "Encargar, a [NOMBRE], [CARGO_ACTUAL], del cargo de [CARGO_ENCARGADO]"
   → cargo_actual = cargo que YA tiene
   → cargo = cargo que asume temporalmente (CARGO_ENCARGADO)
   → "en el cargo de [PERSONA]" = persona reemplazada (sin novedad)

3. RENUNCIA (R):
   Patrón: "Aceptar, la renuncia presentada por [NOMBRE]"

4. ASIGNACIÓN DE FUNCIONES (ASIG):
   Patrón: "Asignar funciones, a [NOMBRE], funciones en [DESTINO]"
   → Movimiento de funciones sin cambio de cargo
   → NO hay persona reemplazada

5. PRÓRROGA (PROR):
   Patrón: "Prorrogar el encargo/provisionalidad, a [NOMBRE]"
   → Extiende un nombramiento o encargo existente

6. MODIFICACIÓN/REVOCACIÓN DECRETO (MD):
   Patrón: "Revocar el Decreto No.X" o "Aclarar el Decreto No.X"
   → NO hay funcionarios, es modificación administrativa
   → funcionarios = []

7. COMISIÓN (C):
   Patrón: "Comisionar" o "Comision, a [NOMBRE]"

8. AUXILIAR AD HONOREM (NAADH):
   Patrón: "Nombrar auxiliar juridico ad-honorem"

9. REVOCACIÓN NOMBRAMIENTO (RN):
   Patrón: "Revocar el nombramiento de [NOMBRE]" por no tomar posesión

10. INSUBSISTENCIA (INSUB):
    Patrón: "Declarar insubsistente"

=== REGLA CRÍTICA: DOS PERSONAS ===
1. PERSONA CON CÉDULA → ES el funcionario, VA en el array
2. PERSONA SIN CÉDULA (después de "en el cargo de [NOMBRE]") → NO es funcionario, va en persona_reemplazada

=== RESPUESTA JSON ===
{{
    "razonamiento": "PASO 1: Corregí OCR [lista]. PASO 2: Palabra clave '[X]' indica [TIPO]. PASO 3: Funcionario es [NOMBRE] con cédula [X]. PASO 4: [NOMBRE2] es persona reemplazada (sin cédula).",
    "numero_decreto": "{filename_meta.get('numero_decreto', '')}",
    "anio": {filename_meta.get('anio', 2009)},
    "fecha_texto": "fecha si aparece",
    "codigo_novedad": "N/E/R/ASIG/PROR/MD/C/NAADH/RN/INSUB",
    "tipo_novedad": "Nombramiento/Encargo/Renuncia/Asignación/Prórroga/Modificación/Comisión",
    "funcionarios": [
        {{
            "cedula": "número SIN puntos",
            "nombre_completo": "NOMBRE APELLIDO",
            "cargo_actual": "solo en encargos",
            "cargo": "cargo nuevo o encargado",
            "codigo_cargo": "ej: 5OF",
            "grado_cargo": "ej: 06",
            "dependencia": "dependencia destino"
        }}
    ],
    "persona_reemplazada": "nombre de quien ocupaba el cargo (sin cédula)",
    "es_modificacion_decreto": false,
    "decreto_modificado": "número si es revocación/aclaración",
    "resumen": "Decreto N-año: [Tipo] de [NOMBRE] como [cargo]"
}}

JSON:"""

    # Llamar al LLM (Azure OpenAI o Ollama local)
    system_prompt = "Eres un experto legal en análisis de decretos de la Procuraduría General de la Nación de Colombia."
    
    if USE_AZURE:
        resp_text = call_azure_openai(prompt, system_prompt)
    else:
        resp_text = call_ollama(prompt)
    
    if resp_text:
        # Extraer JSON de la respuesta
        match = re.search(r'\{[\s\S]*\}', resp_text)
        if match:
            try:
                result = json.loads(match.group())
                
                # Guardar ejemplo para aprendizaje si es exitoso
                codigo = result.get('codigo_novedad')
                razonamiento = result.get('razonamiento', '')
                if conn and codigo and codigo != 'PENDIENTE_REVISION':
                    save_ejemplo_aprendizaje(
                        conn, codigo, text[:1500], razonamiento, 
                        filename_meta.get('filename', '')
                    )
                
                return result
            except json.JSONDecodeError:
                pass
    
    # Retornar estructura mínima con datos del filename
    return {
        'numero_decreto': filename_meta.get('numero_decreto'),
        'anio': filename_meta.get('anio'),
        'codigo_novedad': 'PENDIENTE_REVISION',
        'funcionarios': [],
        'razonamiento': 'No se pudo extraer con LLM',
        'error': 'No se pudo extraer con LLM'
    }


# =============================================================================
# GENERACIÓN DE ARCHIVOS
# =============================================================================

def generate_markdown(filename: str, filepath: str, text: str, 
                      extracted: Dict, filename_meta: Dict) -> str:
    """Genera archivo Markdown con toda la información"""
    md = []
    md.append(f"# {extracted.get('numero_decreto', 'N/A')}-{extracted.get('anio', 'N/A')}: {filename}\n")
    md.append(f"**Archivo:** `{filepath}`\n")
    md.append(f"**Procesado:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    md.append(f"**Método:** OCR Híbrido (DPI 150 + LLM)\n")
    
    md.append("\n## Metadata del Filename\n")
    md.append(f"- **Número Decreto (filename):** {filename_meta.get('numero_decreto')}")
    md.append(f"- **Año (filename):** {filename_meta.get('anio')}")
    
    md.append("\n## Datos Extraídos\n")
    md.append(f"| Campo | Valor |")
    md.append(f"|-------|-------|")
    md.append(f"| Código Novedad | **{extracted.get('codigo_novedad', 'N/A')}** |")
    md.append(f"| Tipo | {extracted.get('tipo_novedad', 'N/A')} |")
    md.append(f"| Fecha | {extracted.get('fecha_texto', 'N/A')} |")
    md.append(f"| Caracteres OCR | {len(text)} |")
    
    md.append("\n## Razonamiento LLM\n")
    md.append(f"> {extracted.get('razonamiento', 'No disponible')}\n")
    
    md.append("\n## Funcionarios\n")
    funcionarios = extracted.get('funcionarios', [])
    if funcionarios:
        md.append("| Cédula | Nombre | Cargo | Acción |")
        md.append("|--------|--------|-------|--------|")
        for func in funcionarios:
            cedula = func.get('cedula', 'N/A') or 'N/A'
            nombre_raw = func.get('nombre_completo') or func.get('nombres') or 'N/A'
            nombre = nombre_raw[:40] if nombre_raw else 'N/A'
            cargo_raw = func.get('cargo') or 'N/A'
            cargo = cargo_raw[:35] if cargo_raw else 'N/A'
            accion_raw = func.get('accion') or 'N/A'
            accion = accion_raw[:25] if accion_raw else 'N/A'
            md.append(f"| {cedula} | {nombre} | {cargo} | {accion} |")
    else:
        md.append("*No se detectaron funcionarios*\n")
    
    md.append("\n## Resumen\n")
    md.append(f"{extracted.get('resumen', 'No disponible')}\n")
    
    md.append("\n## JSON Completo\n")
    md.append("```json")
    md.append(json.dumps(extracted, indent=2, ensure_ascii=False, default=str)[:3000])
    md.append("```\n")
    
    md.append("\n## Texto OCR\n")
    md.append("```text")
    md.append(text[:2500])
    md.append("```\n")
    
    return "\n".join(md)


def generate_graphrag_json(filename: str, filepath: str, 
                           extracted: Dict, filename_meta: Dict) -> Dict:
    """Genera estructura JSON para GraphRAG"""
    entities = []
    relationships = []
    
    # Entidad del decreto
    decreto_id = f"decreto_{extracted.get('numero_decreto', 'X')}_{extracted.get('anio', 'X')}"
    entities.append({
        "id": decreto_id,
        "type": "DECRETO",
        "name": f"Decreto {extracted.get('numero_decreto')} de {extracted.get('anio')}",
        "properties": {
            "numero": extracted.get('numero_decreto'),
            "anio": extracted.get('anio'),
            "fecha": extracted.get('fecha_texto'),
            "codigo_novedad": extracted.get('codigo_novedad'),
            "tipo_novedad": extracted.get('tipo_novedad'),
            "archivo": filepath,
            "resumen": extracted.get('resumen')
        }
    })
    
    # Entidades de funcionarios
    for i, func in enumerate(extracted.get('funcionarios', [])):
        cedula = func.get('cedula', f'unknown_{i}')
        # Limpiar cédula
        cedula_clean = re.sub(r'[^\d]', '', str(cedula))
        func_id = f"funcionario_{cedula_clean or i}"
        
        entities.append({
            "id": func_id,
            "type": "FUNCIONARIO",
            "name": func.get('nombre_completo', func.get('nombres', 'Desconocido')),
            "properties": {
                "cedula": cedula,
                "nombres": func.get('nombres'),
                "apellidos": func.get('apellidos'),
                "cargo": func.get('cargo'),
                "dependencia": func.get('dependencia')
            }
        })
        
        # Relación funcionario -> decreto
        rel_type = extracted.get('codigo_novedad', 'RELACIONADO')
        relationships.append({
            "source": func_id,
            "target": decreto_id,
            "type": rel_type,
            "properties": {
                "accion": func.get('accion'),
                "tipo_novedad": extracted.get('tipo_novedad')
            }
        })
    
    return {
        "document": filename,
        "source_file": filepath,
        "extraction_date": datetime.now().isoformat(),
        "filename_metadata": filename_meta,
        "entities": entities,
        "relationships": relationships,
        "extraction_method": "HYBRID_OCR_LLM"
    }


# =============================================================================
# INTEGRACIÓN CON BASE DE DATOS
# =============================================================================

def save_to_database(conn: sqlite3.Connection, filepath: str, text: str, 
                     extracted: Dict, filename_meta: Dict) -> int:
    """Guarda los datos extraídos en la base de datos"""
    cursor = conn.cursor()
    
    # 1. Insertar decreto (usando columnas reales del esquema)
    cursor.execute('''
        INSERT INTO decretos (
            numero_decreto, anio, fecha_decreto_texto, 
            archivo_origen, ruta_completa, contenido_texto, tipo_extraccion,
            estado_procesamiento, fecha_procesamiento, razonamiento_llm
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        extracted.get('numero_decreto') or filename_meta.get('numero_decreto'),
        extracted.get('anio') or filename_meta.get('anio'),
        extracted.get('fecha_texto'),
        os.path.basename(filepath),
        filepath,
        text[:10000],  # Limitar tamaño
        'HYBRID_OCR_LLM',
        'PROCESADO',
        datetime.now().isoformat(),
        extracted.get('razonamiento')  # Guardar razonamiento del LLM
    ))
    decreto_id = cursor.lastrowid
    
    # 2. Insertar funcionarios y novedades
    funcionarios_list = extracted.get('funcionarios', [])
    
    if funcionarios_list:
        # Tiene funcionarios - crear novedad por cada uno
        for func in funcionarios_list:
            cedula = func.get('cedula')
            cedula_clean = re.sub(r'[^\d]', '', str(cedula)) if cedula else None
            
            # Buscar o crear funcionario
            if cedula_clean:
                cursor.execute('SELECT id FROM funcionarios WHERE cedula = ?', (cedula_clean,))
                row = cursor.fetchone()
                if row:
                    func_id = row[0]
                else:
                    cursor.execute('''
                        INSERT INTO funcionarios (cedula, nombres, apellidos, nombre_completo)
                        VALUES (?, ?, ?, ?)
                    ''', (
                        cedula_clean,
                        func.get('nombres'),
                        func.get('apellidos'),
                        func.get('nombre_completo')
                    ))
                    func_id = cursor.lastrowid
            else:
                func_id = None
            
            # Insertar novedad
            cursor.execute('''
                INSERT INTO novedades (
                    decreto_id, funcionario_id, codigo_novedad, tipo_novedad, 
                    cargo_actual, dependencia, observaciones, fecha_creacion
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                decreto_id,
                func_id,
                extracted.get('codigo_novedad'),
                extracted.get('tipo_novedad'),
                func.get('cargo'),
                func.get('dependencia'),
                extracted.get('resumen'),
                datetime.now().isoformat()
            ))
    else:
        # NO tiene funcionarios - crear novedad de placeholder para que no quede huérfano
        codigo = extracted.get('codigo_novedad', 'PENDIENTE_REVISION')
        cursor.execute('''
            INSERT INTO novedades (
                decreto_id, funcionario_id, codigo_novedad, tipo_novedad, 
                observaciones, fecha_creacion
            ) VALUES (?, NULL, ?, ?, ?, ?)
        ''', (
            decreto_id,
            codigo,
            extracted.get('tipo_novedad'),
            extracted.get('resumen') or 'Decreto sin funcionarios identificados - revisar manualmente',
            datetime.now().isoformat()
        ))
    
    conn.commit()
    return decreto_id


# =============================================================================
# PROCESAMIENTO PRINCIPAL
# =============================================================================

def process_decree_hybrid(filepath: str, conn: sqlite3.Connection) -> Dict:
    """Procesa un decreto con la estrategia híbrida completa"""
    filename = os.path.basename(filepath)
    
    result = {
        'filename': filename,
        'filepath': filepath,
        'success': False,
        'text': '',
        'extracted': {},
        'filename_meta': {},
        'decreto_id': None,
        'error': None
    }
    
    try:
        # 1. Extraer metadata del filename
        filename_meta = extract_filename_metadata(filename)
        result['filename_meta'] = filename_meta
        
        # 2. OCR
        text, method = extract_pdf_ocr(filepath)
        result['text'] = text
        result['method'] = method
        
        if not text or len(text) < 50:
            result['error'] = f"OCR falló o texto muy corto ({len(text)} chars)"
            return result
        
        # 3. LLM estructuración con few-shot learning
        extracted = extract_with_llm(text, filename_meta, conn)
        result['extracted'] = extracted
        
        # 4. Guardar en BD
        decreto_id = save_to_database(conn, filepath, text, extracted, filename_meta)
        result['decreto_id'] = decreto_id
        
        result['success'] = True
        
    except Exception as e:
        result['error'] = str(e)
    
    return result


def generate_metrics_summary(results: List[Dict], output_path: str):
    """Genera reporte de métricas"""
    md = []
    md.append("# Métricas de Extracción Híbrida - Decretos 2009\n")
    md.append(f"**Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    md.append(f"**Total:** {len(results)} archivos\n")
    
    # Estadísticas
    ok = sum(1 for r in results if r['success'])
    err = len(results) - ok
    total = len(results) if len(results) > 0 else 1  # Evitar división por cero
    
    md.append("\n## Resumen\n")
    md.append(f"| Métrica | Valor |")
    md.append(f"|---------|-------|")
    md.append(f"| Exitosos | {ok} ({ok/total*100:.0f}%) |")
    md.append(f"| Errores | {err} |")
    
    # Códigos
    codigos = {}
    for r in results:
        if r['success']:
            cod = r['extracted'].get('codigo_novedad', 'N/A')
            codigos[cod] = codigos.get(cod, 0) + 1
    
    md.append("\n## Distribución por Código\n")
    md.append(f"| Código | Cantidad |")
    md.append(f"|--------|----------|")
    for cod, cnt in sorted(codigos.items(), key=lambda x: -x[1]):
        md.append(f"| {cod} | {cnt} |")
    
    # Tabla detallada
    md.append("\n## Detalle\n")
    md.append("| # | Decreto | Año | Código | Funcionario | DB ID |")
    md.append("|---|---------|-----|--------|-------------|-------|")
    for i, r in enumerate(results, 1):
        st = "✅" if r['success'] else "❌"
        num = r['filename_meta'].get('numero_decreto', 'N/A')
        anio = r['filename_meta'].get('anio', 'N/A')
        cod = r['extracted'].get('codigo_novedad', 'ERR') if r['success'] else 'ERR'
        funcs = r['extracted'].get('funcionarios', [])
        # Validar que funcs[0] exista y no sea None
        if funcs and funcs[0] is not None:
            func_name = (funcs[0].get('nombre_completo') or 'N/A')[:25]
        else:
            func_name = 'N/A'
        db_id = r.get('decreto_id', '-')
        md.append(f"| {i} | {st} {num} | {anio} | {cod} | {func_name} | {db_id} |")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md))


def main():
    global OLLAMA_MODEL, USE_AZURE  # Declarar globales al inicio
    import argparse
    parser = argparse.ArgumentParser(description='Extracción híbrida de decretos')
    parser.add_argument('--dir-in', default=r"C:\temp\PNG_CERTIFICADO_V3\Decretos\2009")
    parser.add_argument('--output-dir', default=OUTPUT_DIR)
    parser.add_argument('--limit', type=int, default=None, help='Límite de archivos a procesar. Sin especificar = todos')
    parser.add_argument('--db', default=DB_PATH)
    parser.add_argument('--llm', '-m', default="gpt-oss:20b-cloud",
                        choices=['gpt-oss:20b-cloud', 'gpt-oss:20b', 'gpt-oss:120b-cloud', 'llama3.1:8b', 'qwen2.5:7b-instruct'],
                        help='Modelo de Ollama a usar. Default: gpt-oss:20b-cloud')
    parser.add_argument('--llm_azure', action='store_true', 
                        help='Usar Azure OpenAI (gpt-5-mini) en lugar de Ollama local')
    parser.add_argument('--resume', '-r', action='store_true', 
                        help='Continuar desde el último archivo procesado (salta archivos ya procesados)')
    args = parser.parse_args()
    
    # Actualizar modelo global
    OLLAMA_MODEL = args.llm
    USE_AZURE = args.llm_azure
    
    # Verificar dependencias para Azure
    if USE_AZURE and not HAS_OPENAI:
        print("ERROR: Para usar Azure OpenAI, instale el SDK: pip install openai")
        return

    
    print("=" * 60)
    print("EXTRACCIÓN HÍBRIDA DE DECRETOS (E3)")
    print("=" * 60)
    print(f"Directorio entrada: {args.dir_in}")
    print(f"Directorio salida: {args.output_dir}")
    print(f"Base de datos: {args.db}")
    if USE_AZURE:
        print(f"LLM: Azure OpenAI ({AZURE_MODEL}) en {AZURE_ENDPOINT}")
    else:
        print(f"LLM: Ollama local ({args.llm})")
    print(f"Límite: {args.limit if args.limit else 'Sin límite (todos)'}")
    print(f"Modo resume: {'Sí - saltando archivos ya procesados' if args.resume else 'No'}")
    print()
    
    # Crear directorios
    ensure_dir(args.output_dir)
    ensure_dir(os.path.join(args.output_dir, 'md'))
    ensure_dir(os.path.join(args.output_dir, 'graphrag'))
    
    # Conectar BD
    conn = sqlite3.connect(args.db)
    
    # Buscar PDFs
    pdf_files = sorted([
        os.path.join(args.dir_in, f)
        for f in os.listdir(args.dir_in)
        if f.lower().endswith('.pdf')
    ])
    if args.limit:
        pdf_files = pdf_files[:args.limit]
    
    # Si resume está activo, filtrar archivos ya procesados
    if args.resume:
        md_dir = os.path.join(args.output_dir, 'md')
        original_count = len(pdf_files)
        pdf_files = [
            f for f in pdf_files 
            if not os.path.exists(os.path.join(md_dir, os.path.basename(f).replace('.pdf', '.md').replace('.PDF', '.md')))
        ]
        skipped = original_count - len(pdf_files)
        if skipped > 0:
            print(f">>> RESUME: Saltando {skipped} archivos ya procesados")
            print()
    
    print(f"Archivos a procesar: {len(pdf_files)}\n")
    
    results = []
    for i, filepath in enumerate(pdf_files):
        filename = os.path.basename(filepath)
        print(f"[{i+1}/{len(pdf_files)}] {filename[:40]}...", end=" ", flush=True)
        
        result = process_decree_hybrid(filepath, conn)
        results.append(result)
        
        if result['success']:
            cod = result['extracted'].get('codigo_novedad', '?')
            print(f"OK ({cod}, DB:{result['decreto_id']})")
            
            # Generar MD
            md_content = generate_markdown(
                filename, filepath, result['text'],
                result['extracted'], result['filename_meta']
            )
            md_path = os.path.join(args.output_dir, 'md', filename.replace('.pdf', '.md').replace('.PDF', '.md'))
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            
            # Generar GraphRAG JSON
            graphrag = generate_graphrag_json(
                filename, filepath, result['extracted'], result['filename_meta']
            )
            json_path = os.path.join(args.output_dir, 'graphrag', filename.replace('.pdf', '.graphrag.json').replace('.PDF', '.graphrag.json'))
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(graphrag, f, indent=2, ensure_ascii=False, default=str)
        else:
            print(f"ERROR: {result.get('error', 'Unknown')[:40]}")
    
    conn.close()
    
    # Generar reporte
    metrics_path = os.path.join(args.output_dir, 'extraction_metrics_hybrid.md')
    generate_metrics_summary(results, metrics_path)
    
    print("\n" + "=" * 60)
    print("COMPLETADO")
    print("=" * 60)
    ok = sum(1 for r in results if r['success'])
    print(f"Total: {len(results)}")
    print(f"Exitosos: {ok} ({ok/len(results)*100:.0f}%)")
    print(f"\nArchivos en: {args.output_dir}")
    print(f"  - MD: {args.output_dir}/md/")
    print(f"  - GraphRAG: {args.output_dir}/graphrag/")
    print(f"  - Métricas: {metrics_path}")


if __name__ == "__main__":
    main()
