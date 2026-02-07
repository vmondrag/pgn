"""
Script de extracción híbrido para certificaciones PGN
Combina regex para campos de alta fiabilidad con LLM para campos inciertos
"""
import os
import re
import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import requests

# Configuración
DB_PATH = r"C:\temp\PNG_CERTIFICADO_V3\certificaciones_pgn.db"
CERT_DIR = r"C:\temp\PNG_CERTIFICADO_V3\Certificaciones"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gpt-oss:20b-cloud"

# Intentar importar dependencias para lectura de Word
try:
    from docx import Document
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

try:
    import win32com.client
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


# =============================================================================
# PATRONES REGEX PARA EXTRACCIÓN DE ALTA FIABILIDAD
# =============================================================================

PATTERNS = {
    # Cédula de ciudadanía - Alta fiabilidad
    'cedula': [
        r'c[ée]dula\s+(?:de\s+ciudadan[ií]a\s+)?(?:n[úu]mero|No\.?|N[°º]\.?)\s*[:\.]?\s*([\d\.]+)',
        r'identificad[oa]\s+con\s+(?:la\s+)?c[ée]dula\s+(?:de\s+ciudadan[ií]a\s+)?(?:n[úu]mero|No\.?|N[°º]\.?)?\s*[:\.]?\s*([\d\.]+)',
        r'C\.?C\.?\s+(?:No\.?|N[°º]\.?)?\s*([\d\.]+)',
    ],
    
    # Lugar de expedición de cédula - Alta fiabilidad
    'lugar_cc': [
        r'c[ée]dula[^,]+de\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)?)',
        r'[\d\.]+\s+de\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+de\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)?)',
    ],
    
    # Nombre completo - Alta fiabilidad
    'nombre': [
        r'(?:el\s+doctor|la\s+doctora|el\s+señor|la\s+señora)\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]+?),?\s+identificad',
        r'Que\s+(?:el\s+doctor|la\s+doctora|el\s+señor|la\s+señora)\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]+?),?\s+identificad',
    ],
    
    # Tratamiento - Alta fiabilidad
    'tratamiento': [
        r'Que\s+(el\s+doctor|la\s+doctora|el\s+señor|la\s+señora)',
    ],
    
    # Número H.R. - Alta fiabilidad
    'numero_hr': [
        r'H\.?R\.?\s*[:\.]?\s*(\d+)',
        r'H\.R\.\s+(\d+)',
    ],
    
    # Elaboró - Alta fiabilidad
    'elaboro': [
        r'Elabor[óo]\.?:?\s*(.+?)(?:\r|\n|Revis)',
        r'Proyect[óo]\.?:?\s*(.+?)(?:\r|\n|Revis)',
    ],
    
    # Revisó - Alta fiabilidad
    'reviso': [
        r'Revis[óo]\.?:?\s*(.+?)(?:\r|\n|H\.R)',
    ],
    
    # Firmante - Alta fiabilidad
    'firmante': [
        r'(CARLOS WILLIAM RODR[ÍI]GUEZ MILL[ÁA]N)',
        r'(TULIO ANCIZAR CARDONA SALAZAR)',
        r'(MARTHA JULIETA TOVAR CARDONA)',
        r'(CARLOS ALBERTO CABALLERO OSORIO)',
    ],
    
    # Fecha de expedición - Media fiabilidad
    'fecha_expedicion': [
        r'(?:se\s+expide|se\s+expedi[óo])[^,]*?(?:a\s+)?(?:los\s+)?(\d+)\s+d[ií]as?\s+del\s+mes\s+de\s+(\w+)\s+de\s+(?:dos\s+mil\s+)?(\d+|[\w\s]+)',
        r'expide\s+en\s+Bogot[áa][^,]*?,?\s*(?:a\s+)?(?:los\s+)?(\d+)\s+d[ií]as?\s+del\s+mes\s+de\s+(\w+)\s+de\s+(\d{4})',
        r'el\s+d[ií]a\s+(\d+)\s+de\s+(\w+)\s+de\s+(\d{4})',
    ],
    
    # Solicitante - Media fiabilidad
    'solicitante': [
        r'(?:a\s+petici[óo]n|a\s+solicitud)\s+(?:de[l]?\s+)?(.+?)(?:\.|$)',
    ],
    
    # Licencias no remuneradas - Alta fiabilidad
    'licencias': [
        r'(NO\s+LE\s+FIGURAN\s+LICENCIAS\s+NO\s+REMUNERADAS)',
        r'(no\s+le\s+(?:figuran|aparecen)[^\.]+licencias)',
        r'LICENCIAS\s+NO\s+REMUNERADAS[:\s]*(.+?)(?:\r|\n|La\s+presente)',
    ],
    
    # Funciones anexas - Alta fiabilidad
    'anexa_funciones': [
        r'(Se\s+anexan\s+funciones)',
    ],
}

# Patrones para cargos (simplificados para evitar backtracking)
CARGO_PATTERNS = [
    # Patrón simple: buscar líneas con "desde X hasta Y"
    r'desde\s+(?:el\s+)?(\d+[^\r\n]+?)\s+hasta\s+(?:el\s+)?(\d+[^\r\n]+?)(?:\.|,|$)',
    # Patrón simple: buscar líneas con "del X al Y"
    r'del\s+(\d+[^\r\n]+?)\s+al\s+(\d+[^\r\n]+?)(?:\.|,|$)',
]


# =============================================================================
# FUNCIONES DE EXTRACCIÓN DE DOCUMENTOS WORD
# =============================================================================

def extract_docx(filepath: str) -> Optional[str]:
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


def extract_doc(filepath: str) -> Optional[str]:
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


def extract_word_content(filepath: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extrae contenido de archivo Word
    Retorna: (contenido, error)
    """
    filepath = os.path.abspath(filepath)
    if not os.path.exists(filepath):
        return None, f"Archivo no encontrado: {filepath}"
    
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext == '.docx':
        content = extract_docx(filepath)
    elif ext == '.doc':
        content = extract_doc(filepath)
    else:
        return None, f"Extensión no soportada: {ext}"
    
    if content and content.startswith("ERROR:"):
        return None, content
    
    return content, None


# =============================================================================
# FUNCIONES DE EXTRACCIÓN CON REGEX
# =============================================================================

def extract_with_regex(text: str, pattern_name: str) -> Tuple[Optional[str], str]:
    """
    Extrae un campo usando patrones regex
    Retorna: (valor_extraído, nivel_confianza)
    """
    if pattern_name not in PATTERNS:
        return None, 'BAJA'
    
    for pattern in PATTERNS[pattern_name]:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            value = match.group(1) if match.lastindex >= 1 else match.group(0)
            return value.strip(), 'ALTA'
    
    return None, 'BAJA'


def extract_cedula(text: str) -> Tuple[Optional[str], str]:
    """Extrae número de cédula"""
    value, confidence = extract_with_regex(text, 'cedula')
    if value:
        # Limpiar puntos del número
        value = value.replace('.', '').replace(' ', '')
    return value, confidence


def extract_nombre(text: str) -> Tuple[Optional[str], str]:
    """Extrae nombre completo"""
    value, confidence = extract_with_regex(text, 'nombre')
    if value:
        # Limpiar espacios extras
        value = ' '.join(value.split())
    return value, confidence


def extract_tratamiento(text: str) -> Optional[str]:
    """Extrae tratamiento (Dr., Dra., etc.)"""
    value, _ = extract_with_regex(text, 'tratamiento')
    if value:
        value = value.lower()
        if 'doctora' in value:
            return 'Dra.'
        elif 'doctor' in value:
            return 'Dr.'
        elif 'señora' in value:
            return 'Sra.'
        elif 'señor' in value:
            return 'Sr.'
    return None


def extract_fecha_expedicion(text: str) -> Tuple[Optional[str], Optional[str], str]:
    """
    Extrae fecha de expedición
    Retorna: (fecha_texto, fecha_iso, confianza)
    """
    meses = {
        'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
        'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
        'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
    }
    
    for pattern in PATTERNS['fecha_expedicion']:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) >= 3:
                dia = groups[0].zfill(2)
                mes_texto = groups[1].lower()
                anio = groups[2]
                
                # Convertir año en texto a número
                if not anio.isdigit():
                    # Intentar extraer año de texto como "dos mil siete"
                    if 'siete' in anio.lower():
                        anio = '2007'
                    elif 'diez' in anio.lower():
                        anio = '2010'
                    # ... etc
                
                mes = meses.get(mes_texto, '01')
                fecha_texto = f"{dia} de {mes_texto} de {anio}"
                
                try:
                    if len(anio) == 4:
                        fecha_iso = f"{anio}-{mes}-{dia}"
                        return fecha_texto, fecha_iso, 'ALTA'
                except:
                    pass
                
                return fecha_texto, None, 'MEDIA'
    
    return None, None, 'BAJA'


def extract_cargos_regex(text: str) -> List[Dict]:
    """
    Intenta extraer cargos usando regex simplificado
    Solo extrae fechas, los detalles del cargo se dejarán para LLM
    """
    cargos = []
    
    # Buscar patrones de fechas en todo el texto
    # Limitar texto para evitar timeout
    text_limited = text[:5000]
    
    for pattern in CARGO_PATTERNS:
        matches = re.findall(pattern, text_limited, re.IGNORECASE)
        for match in matches:
            if len(match) >= 2:
                cargo_info = {
                    'cargo': None,  # Se completará con LLM
                    'codigo': None,
                    'grado': None,
                    'dependencia': None,
                    'fecha_inicio_texto': match[0].strip() if match[0] else None,
                    'fecha_fin_texto': match[1].strip() if match[1] else None,
                    'confianza': 'MEDIA',
                }
                cargos.append(cargo_info)
    
    return cargos


# =============================================================================
# FUNCIONES DE EXTRACCIÓN CON LLM (OLLAMA)
# =============================================================================

def query_ollama(prompt: str, system_prompt: str = None) -> Optional[Dict]:
    """
    Consulta al modelo LLM via Ollama
    """
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 2000,
            }
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            return result.get('response', '')
        else:
            print(f"Error Ollama: {response.status_code} - {response.text}")
            return None
            
    except requests.exceptions.ConnectionError:
        print("Error: No se puede conectar a Ollama. Asegúrese de que está ejecutándose.")
        return None
    except Exception as e:
        print(f"Error consultando Ollama: {str(e)}")
        return None


def extract_with_llm(text: str, campos_faltantes: List[str]) -> Dict:
    """
    Usa LLM para extraer campos que no se pudieron obtener con regex
    """
    system_prompt = """Eres un experto en extracción de información de documentos legales colombianos.
Tu tarea es extraer información específica de certificaciones laborales de la Procuraduría General de la Nación.
Responde SOLO en formato JSON válido, sin explicaciones adicionales."""

    campos_descripcion = {
        'nombre': 'Nombre completo del funcionario (en mayúsculas)',
        'cedula': 'Número de cédula de ciudadanía (solo números)',
        'lugar_cc': 'Ciudad de expedición de la cédula',
        'cargos': 'Lista de cargos desempeñados con fechas de inicio y fin',
        'fecha_expedicion': 'Fecha de expedición de la certificación',
        'solicitante': 'Persona o entidad que solicitó la certificación',
    }
    
    campos_a_extraer = {k: v for k, v in campos_descripcion.items() if k in campos_faltantes}
    
    prompt = f"""Analiza el siguiente documento de certificación laboral y extrae la información solicitada.

DOCUMENTO:
{text[:3000]}

CAMPOS A EXTRAER:
{json.dumps(campos_a_extraer, ensure_ascii=False, indent=2)}

Responde ÚNICAMENTE con un JSON válido con los campos solicitados. 
Para los cargos, usa el formato:
{{"cargos": [{{"cargo": "nombre", "codigo": "XXX", "grado": "YY", "dependencia": "lugar", "fecha_inicio": "texto", "fecha_fin": "texto"}}]}}

Si no encuentras un campo, usa null como valor.
JSON:"""

    response = query_ollama(prompt, system_prompt)
    
    if response:
        try:
            # Intentar parsear JSON de la respuesta
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                extracted = json.loads(json_match.group())
                return {
                    'data': extracted,
                    'confianza': 'MEDIA',
                    'razonamiento': 'Extraído con LLM'
                }
        except json.JSONDecodeError:
            pass
    
    return {'data': {}, 'confianza': 'BAJA', 'razonamiento': 'No se pudo extraer con LLM'}


# =============================================================================
# FUNCIÓN PRINCIPAL DE EXTRACCIÓN
# =============================================================================

def extract_certification(content: str, filename: str) -> Dict:
    """
    Extrae toda la información de una certificación
    Estrategia híbrida:
    - REGEX: campos simples y de alta fiabilidad (cédula, nombre, H.R., etc.)
    - LLM: campos complejos (cargos con fechas, dependencias, etc.)
    """
    result = {
        'archivo': filename,
        'metodo': 'HIBRIDO',
        'campos': {},
        'cargos': [],
        'campos_llm': [],
    }
    
    # 1. Extraer campos SIMPLES con REGEX (alta fiabilidad)
    cedula, conf_cedula = extract_cedula(content)
    result['campos']['cedula'] = {'valor': cedula, 'confianza': conf_cedula}
    
    nombre, conf_nombre = extract_nombre(content)
    result['campos']['nombre'] = {'valor': nombre, 'confianza': conf_nombre}
    
    tratamiento = extract_tratamiento(content)
    result['campos']['tratamiento'] = {'valor': tratamiento, 'confianza': 'ALTA' if tratamiento else 'BAJA'}
    
    lugar_cc, conf_lugar = extract_with_regex(content, 'lugar_cc')
    result['campos']['lugar_cc'] = {'valor': lugar_cc, 'confianza': conf_lugar}
    
    fecha_texto, fecha_iso, conf_fecha = extract_fecha_expedicion(content)
    result['campos']['fecha_expedicion'] = {
        'valor': fecha_texto,
        'valor_iso': fecha_iso,
        'confianza': conf_fecha
    }
    
    numero_hr, conf_hr = extract_with_regex(content, 'numero_hr')
    result['campos']['numero_hr'] = {'valor': numero_hr, 'confianza': conf_hr}
    
    elaboro, conf_elaboro = extract_with_regex(content, 'elaboro')
    result['campos']['elaboro'] = {'valor': elaboro, 'confianza': conf_elaboro}
    
    reviso, conf_reviso = extract_with_regex(content, 'reviso')
    result['campos']['reviso'] = {'valor': reviso, 'confianza': conf_reviso}
    
    firmante, conf_firmante = extract_with_regex(content, 'firmante')
    result['campos']['firmante'] = {'valor': firmante, 'confianza': conf_firmante}
    
    solicitante, conf_solicitante = extract_with_regex(content, 'solicitante')
    result['campos']['solicitante'] = {'valor': solicitante, 'confianza': conf_solicitante}
    
    licencias, conf_licencias = extract_with_regex(content, 'licencias')
    result['campos']['licencias'] = {'valor': licencias, 'confianza': conf_licencias}
    
    anexa_funciones, _ = extract_with_regex(content, 'anexa_funciones')
    result['campos']['anexa_funciones'] = {'valor': bool(anexa_funciones), 'confianza': 'ALTA'}
    
    # 2. Usar LLM para extraer CARGOS (campos complejos)
    # El LLM es mejor para inferir cargos, códigos, grados y fechas
    llm_result = extract_cargos_with_llm(content)
    
    if llm_result.get('cargos'):
        for cargo in llm_result['cargos']:
            cargo['confianza'] = 'LLM'
        result['cargos'] = llm_result['cargos']
        result['campos_llm'] = llm_result
    
    # 3. Si LLM no está disponible, intentar regex simple
    if not result['cargos']:
        cargos_regex = extract_cargos_regex(content)
        result['cargos'] = cargos_regex
    
    # 4. Si aún faltan campos críticos, usar LLM para completar
    if not cedula or not nombre:
        llm_campos = extract_with_llm(content, ['cedula', 'nombre'])
        if llm_campos.get('data'):
            if not cedula and llm_campos['data'].get('cedula'):
                result['campos']['cedula'] = {
                    'valor': str(llm_campos['data']['cedula']).replace('.', '').replace(' ', ''),
                    'confianza': 'LLM'
                }
            if not nombre and llm_campos['data'].get('nombre'):
                result['campos']['nombre'] = {
                    'valor': llm_campos['data']['nombre'],
                    'confianza': 'LLM'
                }
    
    return result


def extract_cargos_with_llm(text: str) -> Dict:
    """
    Usa LLM para extraer todos los cargos del documento
    Este es el método PRINCIPAL para extracción de cargos
    """
    system_prompt = """Eres un experto en extracción de información de certificaciones laborales colombianas.
Tu tarea es extraer TODOS los cargos desempeñados que aparecen en el documento.
Responde SOLO con JSON válido, sin explicaciones."""

    prompt = f"""Extrae TODOS los cargos desempeñados del siguiente documento de certificación laboral.

DOCUMENTO:
{text[:4000]}

Para CADA cargo encontrado, extrae:
- cargo: nombre del cargo (ej: "Procurador 41 Judicial II Penal")
- codigo: código del cargo si aparece (ej: "3PJ", "OPP")
- grado: grado del cargo si aparece (ej: "EC", "ED", "17", "18")
- dependencia: dependencia o lugar de trabajo (ej: "Procuraduría Regional de Sucre")
- sede: ciudad sede (ej: "Armenia", "Bogotá")
- fecha_inicio: fecha de inicio en formato texto
- fecha_fin: fecha de fin en formato texto ("hasta la fecha" si está activo)
- es_encargo: true si es un encargo temporal, false si es cargo regular

Responde ÚNICAMENTE con JSON válido en este formato:
{{"cargos": [
  {{"cargo": "...", "codigo": "...", "grado": "...", "dependencia": "...", "sede": "...", "fecha_inicio": "...", "fecha_fin": "...", "es_encargo": false}}
]}}

Si no encuentras cargos, responde: {{"cargos": []}}
JSON:"""

    response = query_ollama(prompt, system_prompt)
    
    if response:
        try:
            # Buscar JSON en la respuesta
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                extracted = json.loads(json_match.group())
                if 'cargos' in extracted and isinstance(extracted['cargos'], list):
                    return extracted
        except json.JSONDecodeError:
            pass
    
    return {'cargos': []}


# =============================================================================
# FUNCIONES DE BASE DE DATOS
# =============================================================================

def get_or_create_funcionario(conn: sqlite3.Connection, data: Dict) -> int:
    """Obtiene o crea un funcionario en la BD"""
    cursor = conn.cursor()
    
    cedula = data.get('cedula', {}).get('valor')
    if not cedula:
        return None
    
    # Buscar existente
    cursor.execute('SELECT id FROM funcionarios WHERE cedula = ?', (cedula,))
    row = cursor.fetchone()
    
    if row:
        return row[0]
    
    # Crear nuevo
    nombre = data.get('nombre', {}).get('valor', 'DESCONOCIDO')
    tratamiento = data.get('tratamiento', {}).get('valor')
    lugar_cc = data.get('lugar_cc', {}).get('valor')
    
    cursor.execute('''
        INSERT INTO funcionarios (cedula, tratamiento, nombre_completo, lugar_expedicion_cc)
        VALUES (?, ?, ?, ?)
    ''', (cedula, tratamiento, nombre, lugar_cc))
    
    conn.commit()
    return cursor.lastrowid


def save_certificacion(conn: sqlite3.Connection, funcionario_id: int, 
                       extraction: Dict, filepath: str, content: str) -> int:
    """Guarda una certificación en la BD"""
    cursor = conn.cursor()
    
    campos = extraction['campos']
    anio = os.path.basename(os.path.dirname(filepath))
    
    # Determinar tipo de certificación del nombre del archivo
    filename = os.path.basename(filepath)
    tipo = None
    for t in ['TP', 'LS', 'EP', 'DC', 'AB', 'LAS']:
        if f'_{t}' in filename or f'_{t}.' in filename:
            tipo = t
            break
    
    cursor.execute('''
        INSERT INTO certificaciones (
            funcionario_id, archivo_origen, ruta_completa, anio_carpeta,
            tipo_certificacion, fecha_expedicion_texto, ciudad_expedicion,
            solicitante, firmante, elaboro, reviso, numero_hr,
            tiene_licencias_no_remuneradas, anexa_funciones,
            contenido_original, metodo_extraccion
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        funcionario_id,
        filename,
        filepath,
        anio,
        tipo,
        campos.get('fecha_expedicion', {}).get('valor'),
        'Bogotá D.C.',
        campos.get('solicitante', {}).get('valor'),
        campos.get('firmante', {}).get('valor'),
        campos.get('elaboro', {}).get('valor'),
        campos.get('reviso', {}).get('valor'),
        campos.get('numero_hr', {}).get('valor'),
        campos.get('licencias', {}).get('valor') is not None,
        campos.get('anexa_funciones', {}).get('valor', False),
        content,
        extraction['metodo']
    ))
    
    conn.commit()
    return cursor.lastrowid


def save_cargos(conn: sqlite3.Connection, funcionario_id: int, 
                certificacion_id: int, cargos: List[Dict]):
    """Guarda los cargos extraídos"""
    cursor = conn.cursor()
    
    for cargo in cargos:
        cursor.execute('''
            INSERT INTO cargos (
                funcionario_id, cargo, codigo, grado, dependencia,
                fecha_inicio_texto, fecha_fin_texto, 
                confianza_extraccion, certificacion_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            funcionario_id,
            cargo.get('cargo'),
            cargo.get('codigo'),
            cargo.get('grado'),
            cargo.get('dependencia'),
            cargo.get('fecha_inicio_texto') or cargo.get('fecha_inicio'),
            cargo.get('fecha_fin_texto') or cargo.get('fecha_fin'),
            cargo.get('confianza', 'MEDIA'),
            certificacion_id
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
# PROCESAMIENTO PRINCIPAL
# =============================================================================

def process_all_documents():
    """Procesa todos los documentos de certificación"""
    
    conn = sqlite3.connect(DB_PATH)
    
    stats = {
        'total': 0,
        'procesados': 0,
        'errores': 0,
        'por_anio': {},
        'funcionarios_unicos': set(),
    }
    
    # Obtener todos los años disponibles
    years = sorted([d for d in os.listdir(CERT_DIR) 
                   if os.path.isdir(os.path.join(CERT_DIR, d)) and d.isdigit()])
    
    print(f"Años encontrados: {years}")
    print("="*60)
    
    for year in years:
        year_dir = os.path.join(CERT_DIR, year)
        stats['por_anio'][year] = {'procesados': 0, 'errores': 0}
        
        # Obtener archivos Word
        files = [f for f in os.listdir(year_dir)
                if (f.endswith('.doc') or f.endswith('.docx'))
                and not f.startswith('~')
                and 'copia' not in f.lower()]
        
        print(f"\nProcesando año {year}: {len(files)} archivos")
        
        for filename in files:
            filepath = os.path.join(year_dir, filename)
            stats['total'] += 1
            
            try:
                # Extraer contenido
                content, error = extract_word_content(filepath)
                
                if error:
                    save_error(conn, filepath, 'LECTURA', error)
                    stats['errores'] += 1
                    stats['por_anio'][year]['errores'] += 1
                    print(f"  ERROR: {filename} - {error}")
                    continue
                
                # Extraer información
                extraction = extract_certification(content, filename)
                
                # Guardar en BD
                funcionario_id = get_or_create_funcionario(conn, extraction['campos'])
                
                if funcionario_id:
                    cedula = extraction['campos'].get('cedula', {}).get('valor')
                    if cedula:
                        stats['funcionarios_unicos'].add(cedula)
                    
                    cert_id = save_certificacion(conn, funcionario_id, extraction, filepath, content)
                    
                    if extraction['cargos']:
                        save_cargos(conn, funcionario_id, cert_id, extraction['cargos'])
                    
                    stats['procesados'] += 1
                    stats['por_anio'][year]['procesados'] += 1
                    print(f"  OK: {filename}")
                else:
                    save_error(conn, filepath, 'EXTRACCION', 'No se pudo extraer cédula')
                    stats['errores'] += 1
                    stats['por_anio'][year]['errores'] += 1
                    print(f"  WARN: {filename} - Sin cédula identificada")
                    
            except Exception as e:
                save_error(conn, filepath, 'EXCEPCION', str(e))
                stats['errores'] += 1
                stats['por_anio'][year]['errores'] += 1
                print(f"  ERROR: {filename} - {str(e)}")
    
    conn.close()
    
    # Convertir set a contador
    stats['funcionarios_unicos'] = len(stats['funcionarios_unicos'])
    
    return stats


def generate_quality_report(stats: Dict) -> str:
    """Genera reporte de calidad del procesamiento"""
    
    report = []
    report.append("=" * 60)
    report.append("REPORTE DE CALIDAD - EXTRACCIÓN DE CERTIFICACIONES PGN")
    report.append("=" * 60)
    report.append(f"Fecha de generación: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    report.append("RESUMEN GENERAL")
    report.append("-" * 40)
    report.append(f"Total de archivos:           {stats['total']}")
    report.append(f"Procesados exitosamente:     {stats['procesados']}")
    report.append(f"Con errores:                 {stats['errores']}")
    report.append(f"Tasa de éxito:               {stats['procesados']/max(stats['total'],1)*100:.1f}%")
    report.append(f"Funcionarios únicos:         {stats['funcionarios_unicos']}")
    report.append("")
    
    report.append("DETALLE POR AÑO")
    report.append("-" * 40)
    for year, data in sorted(stats['por_anio'].items()):
        total = data['procesados'] + data['errores']
        report.append(f"{year}: {data['procesados']}/{total} OK ({data['procesados']/max(total,1)*100:.0f}%)")
    
    report.append("")
    report.append("=" * 60)
    
    return "\n".join(report)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("Iniciando procesamiento de certificaciones PGN...")
    print("="*60)
    
    # Verificar conexión con Ollama
    print("Verificando conexión con Ollama...")
    test_response = query_ollama("Responde solo 'OK'")
    if test_response:
        print(f"Ollama conectado: {OLLAMA_MODEL}")
    else:
        print("ADVERTENCIA: Ollama no disponible. Se usará solo extracción por regex.")
    
    print("")
    
    # Procesar documentos
    stats = process_all_documents()
    
    # Generar reporte
    report = generate_quality_report(stats)
    print("\n" + report)
    
    # Guardar reporte
    report_path = os.path.join(os.path.dirname(DB_PATH), 'reporte_calidad.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\nReporte guardado en: {report_path}")
    print(f"Base de datos: {DB_PATH}")
