"""
API REST Flask para consulta de novedades de decretos y resoluciones PGN
Permite buscar por cédula, nombre/apellidos y filtrar por año
Soporta tanto decretos como resoluciones (Decreto Ley 262 de 2000)
"""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import os
import json

# Cargar variables de entorno desde .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # Si no está instalado python-dotenv, usar variables del sistema

app = Flask(__name__, static_folder='static')
CORS(app)

# Configuración
DB_PATH = r"C:\temp\PNG_CERTIFICADO_V3\novedades_pgn.db"


def get_db():
    """Conexión a la base de datos"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_config(clave, default=None):
    """Obtener un valor de configuración de la BD"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT valor FROM configuracion_llm WHERE clave = ?', (clave,))
    row = cursor.fetchone()
    conn.close()
    return row['valor'] if row else default


def set_config(clave, valor):
    """Guardar un valor de configuración en la BD"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO configuracion_llm (clave, valor, fecha_actualizacion)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(clave) DO UPDATE SET valor = ?, fecha_actualizacion = datetime('now')
    ''', (clave, valor, valor))
    conn.commit()
    conn.close()


def get_all_config():
    """Obtener toda la configuración LLM"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT clave, valor, descripcion, fecha_actualizacion FROM configuracion_llm ORDER BY clave')
    config = {row['clave']: {'valor': row['valor'], 'descripcion': row['descripcion'], 'fecha_actualizacion': row['fecha_actualizacion']} for row in cursor.fetchall()}
    conn.close()
    return config


def init_configuracion_db():
    """Inicializar tabla de configuración LLM con valores por defecto"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS configuracion_llm (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clave VARCHAR(50) UNIQUE NOT NULL,
            valor TEXT,
            descripcion VARCHAR(200),
            fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    defaults = [
        ('proveedor_activo', 'openai', 'Proveedor activo: openai, azure, ollama, ollama_cloud'),
        ('modelo_activo', 'gpt-4o-mini', 'Modelo seleccionado para validacion'),
        ('openai_api_key', os.environ.get('OPENAI_API_KEY', ''), 'Clave API de OpenAI'),
        ('openai_modelos', 'gpt-4o-mini,gpt-4o,gpt-4.1', 'Modelos OpenAI disponibles'),
        ('azure_endpoint', os.environ.get('AZURE_OPENAI_ENDPOINT', ''), 'Endpoint Azure OpenAI'),
        ('azure_api_key', os.environ.get('AZURE_OPENAI_API_KEY', ''), 'Clave API Azure OpenAI'),
        ('azure_modelo', 'gpt-4.1', 'Modelo Azure desplegado'),
        ('azure_api_version', '2025-01-01-preview', 'Version API Azure'),
        ('ollama_url', 'http://localhost:11434', 'URL del servidor Ollama local'),
        ('ollama_modelo', 'llama3.1', 'Modelo Ollama local seleccionado'),
        ('ollama_cloud_url', '', 'URL de Ollama Cloud API'),
        ('ollama_cloud_api_key', '', 'Clave API Ollama Cloud'),
        ('ollama_cloud_modelo', 'kimi-k2.5', 'Modelo Ollama Cloud seleccionado'),
    ]
    for clave, valor, descripcion in defaults:
        cursor.execute('''
            INSERT OR IGNORE INTO configuracion_llm (clave, valor, descripcion)
            VALUES (?, ?, ?)
        ''', (clave, valor, descripcion))
    conn.commit()
    conn.close()


def llamar_llm(prompt, system_message, temperature=0.2, max_tokens=1500):
    """
    Llamar al LLM configurado. Soporta OpenAI, Azure, Ollama local y Ollama Cloud.
    Retorna: dict con 'content' (string) y 'modelo' (string)
    """
    import requests as http_requests

    proveedor = get_config('proveedor_activo', 'openai')
    modelo = get_config('modelo_activo', 'gpt-4o-mini')

    if proveedor == 'openai':
        api_key = get_config('openai_api_key', '')
        if not api_key:
            raise ValueError('OpenAI API key no configurada. Vaya a /configuracion para configurarla.')
        response = http_requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": modelo,
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens
            },
            timeout=30
        )
        if response.status_code != 200:
            raise Exception(f'Error API OpenAI ({response.status_code}): {response.text[:500]}')
        result = response.json()
        return {'content': result['choices'][0]['message']['content'], 'modelo': modelo}

    elif proveedor == 'azure':
        endpoint = get_config('azure_endpoint', '')
        api_key = get_config('azure_api_key', '')
        azure_modelo = get_config('azure_modelo', 'gpt-4.1')
        api_version = get_config('azure_api_version', '2025-01-01-preview')
        if not endpoint or not api_key:
            raise ValueError('Azure OpenAI no configurado. Vaya a /configuracion.')
        url = f"{endpoint.rstrip('/')}/openai/deployments/{azure_modelo}/chat/completions?api-version={api_version}"
        response = http_requests.post(
            url,
            headers={"api-key": api_key, "Content-Type": "application/json"},
            json={
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens
            },
            timeout=30
        )
        if response.status_code != 200:
            raise Exception(f'Error Azure OpenAI ({response.status_code}): {response.text[:500]}')
        result = response.json()
        return {'content': result['choices'][0]['message']['content'], 'modelo': f'azure/{azure_modelo}'}

    elif proveedor == 'ollama':
        ollama_url = get_config('ollama_url', 'http://localhost:11434')
        ollama_modelo = get_config('ollama_modelo', 'llama3.1')
        response = http_requests.post(
            f"{ollama_url.rstrip('/')}/api/chat",
            json={
                "model": ollama_modelo,
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens}
            },
            timeout=120
        )
        if response.status_code != 200:
            raise Exception(f'Error Ollama ({response.status_code}): {response.text[:500]}')
        result = response.json()
        return {'content': result['message']['content'], 'modelo': f'ollama/{ollama_modelo}'}

    elif proveedor == 'ollama_cloud':
        cloud_url = get_config('ollama_cloud_url', '')
        cloud_key = get_config('ollama_cloud_api_key', '')
        cloud_modelo = get_config('ollama_cloud_modelo', 'kimi-k2.5')
        if not cloud_url:
            raise ValueError('Ollama Cloud URL no configurada. Vaya a /configuracion.')
        headers = {"Content-Type": "application/json"}
        if cloud_key:
            headers["Authorization"] = f"Bearer {cloud_key}"
        response = http_requests.post(
            f"{cloud_url.rstrip('/')}/v1/chat/completions",
            headers=headers,
            json={
                "model": cloud_modelo,
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens
            },
            timeout=60
        )
        if response.status_code != 200:
            raise Exception(f'Error Ollama Cloud ({response.status_code}): {response.text[:500]}')
        result = response.json()
        return {'content': result['choices'][0]['message']['content'], 'modelo': f'ollama_cloud/{cloud_modelo}'}

    else:
        raise ValueError(f'Proveedor LLM no soportado: {proveedor}')


@app.route('/')
def index():
    """Página principal"""
    return send_from_directory('static', 'index.html')


@app.route('/errores')
def errores_page():
    """Página de errores de procesamiento"""
    return send_from_directory('static', 'errores.html')


@app.route('/pdf/<path:filepath>')
def serve_pdf(filepath):
    """Servir archivo PDF desde el sistema de archivos"""
    import urllib.parse
    # Decodificar la ruta
    decoded_path = urllib.parse.unquote(filepath)
    
    # Verificar que el archivo existe y es un PDF
    if os.path.exists(decoded_path) and decoded_path.lower().endswith('.pdf'):
        directory = os.path.dirname(decoded_path)
        filename = os.path.basename(decoded_path)
        return send_from_directory(directory, filename, mimetype='application/pdf')
    
    return jsonify({'error': 'PDF no encontrado'}), 404


@app.route('/huerfanos')
def huerfanos_page():
    """Página de revisión de decretos huérfanos"""
    return send_from_directory('static', 'huerfanos.html')


@app.route('/api/huerfanos')
def get_huerfanos():
    """
    Obtener decretos huérfanos (sin novedades o con PENDIENTE_REVISION)
    Parámetros:
        - anio: filtrar por año
        - decreto: buscar por número de decreto
        - solo_pendientes: solo PENDIENTE_REVISION (default: false)
    """
    anio = request.args.get('anio', '')
    decreto = request.args.get('decreto', '').strip()
    solo_pendientes = request.args.get('solo_pendientes', 'false') == 'true'
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Decretos sin novedades
    query = '''
        SELECT 
            d.id,
            d.numero_decreto,
            d.anio,
            d.fecha_decreto_texto,
            d.contenido_texto,
            d.ruta_completa,
            d.archivo_origen,
            d.tipo_extraccion,
            (SELECT COUNT(*) FROM novedades n WHERE n.decreto_id = d.id) as num_novedades,
            (SELECT n.codigo_novedad FROM novedades n WHERE n.decreto_id = d.id LIMIT 1) as codigo
        FROM decretos d
        WHERE 1=1
    '''
    params = []
    
    if anio and anio.isdigit():
        query += ' AND d.anio = ?'
        params.append(int(anio))
        
    if decreto:
        query += ' AND d.numero_decreto LIKE ?'
        params.append(f'%{decreto}%')
    
    if solo_pendientes:
        query += ''' AND d.id IN (
            SELECT decreto_id FROM novedades WHERE codigo_novedad = 'PENDIENTE_REVISION'
        )'''
    else:
        # Huérfanos: sin novedades O con PENDIENTE_REVISION
        query += ''' AND (
            (SELECT COUNT(*) FROM novedades n WHERE n.decreto_id = d.id) = 0
            OR d.id IN (SELECT decreto_id FROM novedades WHERE codigo_novedad = 'PENDIENTE_REVISION')
        )'''
    
    query += ' ORDER BY d.anio DESC, d.numero_decreto LIMIT 500'
    
    cursor.execute(query, params)
    results = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        'total': len(results),
        'huerfanos': results
    })


@app.route('/api/decreto/<int:decreto_id>')
def get_decreto_detail(decreto_id):
    """Obtener detalles completos de un decreto para revisión"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM decretos WHERE id = ?', (decreto_id,))
    decreto = cursor.fetchone()
    
    if not decreto:
        conn.close()
        return jsonify({'error': 'Decreto no encontrado'}), 404
    
    # Obtener novedades existentes
    cursor.execute('''
        SELECT n.*, f.cedula, f.nombre_completo, f.nombres, f.apellidos
        FROM novedades n
        LEFT JOIN funcionarios f ON n.funcionario_id = f.id
        WHERE n.decreto_id = ?
    ''', (decreto_id,))
    novedades = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        'decreto': dict(decreto),
        'novedades': novedades,
        'tiene_novedades': len(novedades) > 0
    })


@app.route('/api/corregir', methods=['POST'])
def corregir_decreto():
    """
    Guardar corrección manual de un decreto.
    Crea las novedades y funcionarios, y guarda en ejemplos_aprendizaje.
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Datos no proporcionados'}), 400
    
    decreto_id = data.get('decreto_id')
    codigo_novedad = data.get('codigo_novedad')
    tipo_novedad = data.get('tipo_novedad')
    funcionarios = data.get('funcionarios', [])
    razonamiento = data.get('razonamiento', '')
    
    if not decreto_id or not codigo_novedad:
        return jsonify({'error': 'decreto_id y codigo_novedad son requeridos'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Verificar que el decreto existe
        cursor.execute('SELECT * FROM decretos WHERE id = ?', (decreto_id,))
        decreto = cursor.fetchone()
        if not decreto:
            conn.close()
            return jsonify({'error': 'Decreto no encontrado'}), 404
        
        # Eliminar novedades anteriores con PENDIENTE_REVISION
        cursor.execute('''
            DELETE FROM novedades 
            WHERE decreto_id = ? AND codigo_novedad = 'PENDIENTE_REVISION'
        ''', (decreto_id,))
        
        created_novedades = []
        created_funcionarios = []
        
        # Crear funcionarios y novedades
        for func_data in funcionarios:
            cedula = func_data.get('cedula', '').replace('.', '').strip()
            nombre_completo = func_data.get('nombre_completo', '')
            nombres = func_data.get('nombres', '')
            apellidos = func_data.get('apellidos', '')
            cargo = func_data.get('cargo', '')
            dependencia = func_data.get('dependencia', '')
            accion = func_data.get('accion', '')
            
            # Crear o buscar funcionario
            funcionario_id = None
            if cedula:
                cursor.execute('SELECT id FROM funcionarios WHERE cedula = ?', (cedula,))
                existing = cursor.fetchone()
                if existing:
                    funcionario_id = existing[0]
                else:
                    cursor.execute('''
                        INSERT INTO funcionarios (cedula, nombre_completo, nombres, apellidos)
                        VALUES (?, ?, ?, ?)
                    ''', (cedula, nombre_completo, nombres, apellidos))
                    funcionario_id = cursor.lastrowid
                    created_funcionarios.append(funcionario_id)
            
            # Crear novedad
            cursor.execute('''
                INSERT INTO novedades (
                    decreto_id, funcionario_id, codigo_novedad, tipo_novedad,
                    cargo_actual, dependencia, observaciones, fecha_creacion
                ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ''', (decreto_id, funcionario_id, codigo_novedad, tipo_novedad,
                  cargo, dependencia, accion))
            created_novedades.append(cursor.lastrowid)
        
        # Si no hay funcionarios, crear novedad sin funcionario
        if not funcionarios:
            cursor.execute('''
                INSERT INTO novedades (
                    decreto_id, codigo_novedad, tipo_novedad, observaciones, fecha_creacion
                ) VALUES (?, ?, ?, ?, datetime('now'))
            ''', (decreto_id, codigo_novedad, tipo_novedad, razonamiento))
            created_novedades.append(cursor.lastrowid)
        
        # Guardar en ejemplos_aprendizaje para refuerzo
        texto_ejemplo = decreto['contenido_texto'][:5000] if decreto['contenido_texto'] else ''
        respuesta_llm = json.dumps({
            'codigo_novedad': codigo_novedad,
            'tipo_novedad': tipo_novedad,
            'funcionarios': funcionarios
        }, ensure_ascii=False)
        
        cursor.execute('''
            INSERT INTO ejemplos_aprendizaje (
                codigo_novedad, texto_ejemplo, respuesta_llm, razonamiento, 
                nombre_archivo, confianza
            ) VALUES (?, ?, ?, ?, ?, 1.0)
        ''', (codigo_novedad, texto_ejemplo, respuesta_llm, razonamiento, 
              decreto['archivo_origen'] if decreto['archivo_origen'] else ''))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Corrección guardada: {len(created_novedades)} novedades, {len(created_funcionarios)} funcionarios nuevos',
            'novedades_creadas': created_novedades,
            'funcionarios_creados': created_funcionarios
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/buscar_funcionario')
def buscar_funcionario():
    """Buscar funcionario por cédula para evitar duplicados"""
    cedula = request.args.get('cedula', '').replace('.', '').replace(' ', '').strip()
    
    if not cedula:
        return jsonify({'error': 'Cédula requerida'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, cedula, nombre_completo, nombres, apellidos
        FROM funcionarios 
        WHERE cedula = ? OR cedula LIKE ?
    ''', (cedula, f'%{cedula}%'))
    
    funcionarios = [dict(row) for row in cursor.fetchall()]
    
    # También buscar novedades previas para obtener cargo y dependencia
    if funcionarios:
        for func in funcionarios:
            cursor.execute('''
                SELECT cargo_actual, dependencia 
                FROM novedades 
                WHERE funcionario_id = ?
                ORDER BY id DESC LIMIT 1
            ''', (func['id'],))
            novedad = cursor.fetchone()
            if novedad:
                func['cargo'] = novedad['cargo_actual']
                func['dependencia'] = novedad['dependencia']
    
    conn.close()
    
    return jsonify({
        'encontrados': len(funcionarios),
        'funcionarios': funcionarios
    })


# OpenAI API Key - Cargar desde variable de entorno
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')


def validar_integridad_cedulas(funcionarios_extraidos):
    """
    Valida la integridad de las cédulas extraídas contra la base de datos.
    Detecta discrepancias como:
    - CEDULA_OTRO_NOMBRE: La cédula existe pero con otro nombre
    - NOMBRE_OTRA_CEDULA: El nombre existe pero con otra cédula
    - CEDULA_NUEVA: Primera aparición de esta cédula
    
    Args:
        funcionarios_extraidos: Lista de dicts con 'cedula' y 'nombre_completo'
    
    Returns:
        Lista de alertas con detalles de las discrepancias encontradas
    """
    alertas = []
    
    if not funcionarios_extraidos:
        return alertas
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        for func in funcionarios_extraidos:
            cedula = str(func.get('cedula', '')).replace('.', '').replace(' ', '').strip()
            nombre = func.get('nombre_completo', '').upper().strip()
            
            if not cedula or cedula == 'None':
                continue
            
            # 1. Buscar si la cédula ya existe en la BD
            cursor.execute('''
                SELECT id, cedula, nombre_completo 
                FROM funcionarios 
                WHERE cedula = ?
            ''', (cedula,))
            funcionario_existente = cursor.fetchone()
            
            if funcionario_existente:
                nombre_bd = funcionario_existente['nombre_completo'].upper() if funcionario_existente['nombre_completo'] else ''
                
                # Comparar nombres (ignorando espacios extra y case)
                nombre_normalizado = ' '.join(nombre.split())
                nombre_bd_normalizado = ' '.join(nombre_bd.split())
                
                if nombre_normalizado != nombre_bd_normalizado and nombre_normalizado and nombre_bd_normalizado:
                    # La cédula existe pero con otro nombre
                    alertas.append({
                        'tipo': 'CEDULA_OTRO_NOMBRE',
                        'nivel': 'warning',
                        'cedula': cedula,
                        'nombre_decreto': nombre,
                        'nombre_bd': nombre_bd,
                        'funcionario_id_bd': funcionario_existente['id'],
                        'mensaje': f'⚠️ ALERTA: La cédula {cedula} ya está registrada para "{nombre_bd}", '
                                   f'pero en este decreto aparece como "{nombre}". '
                                   f'Posible error en el decreto original o error de OCR.',
                        'sugerencia': 'Verificar el documento físico para confirmar la cédula correcta.'
                    })
            else:
                # La cédula no existe en la BD - es nueva
                # Buscar si el nombre ya existe con otra cédula
                cursor.execute('''
                    SELECT id, cedula, nombre_completo 
                    FROM funcionarios 
                    WHERE nombre_completo LIKE ?
                    LIMIT 5
                ''', (f'%{nombre}%',))
                nombres_similares = cursor.fetchall()
                
                for similar in nombres_similares:
                    nombre_similar = similar['nombre_completo'].upper() if similar['nombre_completo'] else ''
                    cedula_similar = similar['cedula']
                    
                    # Si el nombre es muy similar pero la cédula es diferente
                    if nombre in nombre_similar or nombre_similar in nombre:
                        alertas.append({
                            'tipo': 'NOMBRE_OTRA_CEDULA',
                            'nivel': 'info',
                            'cedula_decreto': cedula,
                            'nombre_decreto': nombre,
                            'cedula_bd': cedula_similar,
                            'nombre_bd': nombre_similar,
                            'funcionario_id_bd': similar['id'],
                            'mensaje': f'ℹ️ NOTA: El nombre "{nombre}" es similar a "{nombre_similar}" '
                                       f'que tiene cédula {cedula_similar} (diferente a {cedula}). '
                                       f'Podría ser la misma persona con cédula mal capturada.',
                            'sugerencia': 'Verificar si es la misma persona y cuál es la cédula correcta.'
                        })
                
                # Marcar como nueva si no hay alertas para esta cédula
                if not any(a.get('cedula') == cedula or a.get('cedula_decreto') == cedula for a in alertas):
                    alertas.append({
                        'tipo': 'CEDULA_NUEVA',
                        'nivel': 'info',
                        'cedula': cedula,
                        'nombre': nombre,
                        'mensaje': f'ℹ️ Nueva cédula: {cedula} - {nombre} (primera aparición en el sistema)'
                    })
    
    finally:
        conn.close()
    
    return alertas


@app.route('/api/validar_correccion', methods=['POST'])
def validar_correccion():
    """
    Validar corrección usando GPT-4o-mini.
    Analiza el razonamiento del usuario contra el texto OCR.
    Extrae automáticamente los funcionarios del texto.
    """
    import requests
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos no proporcionados'}), 400
    
    texto_ocr = data.get('texto_ocr', '')[:4000]
    codigo_propuesto = data.get('codigo_novedad', '')
    tipo_propuesto = data.get('tipo_novedad', '')
    razonamiento_usuario = data.get('razonamiento', '')
    funcionarios_previos = data.get('funcionarios', [])
    
    # Construir prompt para GPT - MEJORADO para manejar ENCARGOS
    prompt = f"""Eres un experto en análisis de decretos administrativos de la Procuraduría General de la Nación de Colombia.

TEXTO OCR DEL DECRETO (puede tener errores - palabras pegadas):
{texto_ocr}

CORRECCIÓN PROPUESTA POR EL USUARIO:
- Código de novedad: {codigo_propuesto} ({tipo_propuesto})
- Razonamiento: {razonamiento_usuario}

REGLAS CRÍTICAS:

1. ESTRUCTURA DE DECRETOS - HAY DOS PERSONAS:
   - PERSONA CON NOVEDAD: tiene cédula, ES EL SUJETO del decreto → VA en funcionarios
   - PERSONA REEMPLAZADA: aparece después de "en el cargo de [NOMBRE]", NO tiene cédula → NO VA en funcionarios

2. TIPOS DE NOVEDAD:
   
   NOMBRAMIENTO (N):
   - "Nombrar en Provisionalidad, a [NOMBRE], cedula [X], en el cargo de [CARGO]"
   - cargo = el cargo al que se nombra
   
   ENCARGO (E):
   - "Encargar, a [NOMBRE], [CARGO_ACTUAL] Codigo XX, del cargo de [CARGO_ENCARGADO]"
   - La persona YA TIENE un cargo (cargo_actual) y se le ENCARGA otro temporalmente
   - cargo = CARGO_ENCARGADO (no el actual)
   - Ejemplo: "Encargar a ALIRIO, Conductor Codigo 6CH, del cargo de Auxiliar Administrativo"
     → cargo_actual: Conductor, cargo: Auxiliar Administrativo (el encargado)

3. SOLO extrae funcionarios con CÉDULA. La persona sin cédula es la reemplazada.

CÓDIGOS VÁLIDOS:
N=Nombramiento, E=Encargo, R=Renuncia, RN=Revocación, INSUB=Insubsistencia, 
C=Comisión, T=Traslado, RE=Retorno Encargo, REU=Renuncia Encargo, NAADH=Nombramiento Ad Honorem

Responde ÚNICAMENTE con JSON (sin markdown):
{{
    "codigo_valido": true/false,
    "codigo_sugerido": "código correcto si incorrecto",
    "tipo_sugerido": "descripción del código",
    "confianza": 0.0-1.0,
    "observaciones": "breve análisis",
    "funcionarios_extraidos": [
        {{
            "cedula": "número SIN puntos",
            "nombre_completo": "NOMBRES APELLIDOS",
            "cargo_actual": "cargo que ya tiene (solo en encargos)",
            "cargo": "cargo nuevo (nombramiento) o cargo encargado (encargo)",
            "dependencia": "dependencia destino",
            "accion": "Encargo como [cargo]" o "Nombramiento como [cargo]"
        }}
    ],
    "persona_reemplazada": "Nombre de quien ocupaba el cargo (sin cédula, NO es funcionario)",
    "correcciones_ocr": ["errores OCR corregidos"],
    "razonamiento_mejorado": "razonamiento para aprendizaje"
}}"""

    try:
        system_message = "Eres un experto legal en decretos administrativos colombianos. Responde ÚNICAMENTE con JSON válido, sin marcadores de código ni texto adicional."
        llm_result = llamar_llm(prompt, system_message, temperature=0.2, max_tokens=1500)
        content = llm_result['content']
        modelo_usado = llm_result['modelo']

        # Intentar parsear JSON de la respuesta
        try:
            # Limpiar posibles marcadores de código
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]

            validacion = json.loads(content.strip())
        except json.JSONDecodeError:
            validacion = {
                'codigo_valido': True,
                'observaciones': content[:500],
                'confianza': 0.5
            }

        # === VALIDACIÓN DE INTEGRIDAD DE CÉDULAS ===
        alertas_cedula = []
        funcionarios_extraidos = validacion.get('funcionarios_extraidos', [])

        if funcionarios_extraidos:
            alertas_cedula = validar_integridad_cedulas(funcionarios_extraidos)

            alertas_warning = [a for a in alertas_cedula if a.get('nivel') == 'warning']
            if alertas_warning:
                advertencia = "\n\n⚠️ ADVERTENCIA DE INTEGRIDAD:\n"
                for alerta in alertas_warning:
                    advertencia += f"- {alerta.get('mensaje', '')}\n"
                    advertencia += f"  Sugerencia: {alerta.get('sugerencia', '')}\n"

                if 'observaciones' in validacion:
                    validacion['observaciones'] += advertencia
                else:
                    validacion['observaciones'] = advertencia

        return jsonify({
            'success': True,
            'validacion': validacion,
            'alertas_cedula': alertas_cedula,
            'modelo': modelo_usado
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def get_stats():
    """Estadísticas generales de la BD (decretos + resoluciones)"""
    conn = get_db()
    cursor = conn.cursor()

    stats = {}

    # Conteos generales - Decretos
    cursor.execute('SELECT COUNT(*) FROM decretos')
    stats['total_decretos'] = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM funcionarios')
    stats['total_funcionarios'] = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM novedades')
    stats['total_novedades_decretos'] = cursor.fetchone()[0]

    # Conteos - Resoluciones (si existe la tabla)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='resoluciones'")
    if cursor.fetchone():
        cursor.execute('SELECT COUNT(*) FROM resoluciones')
        stats['total_resoluciones'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM novedades_resoluciones')
        stats['total_novedades_resoluciones'] = cursor.fetchone()[0]

        # Años de resoluciones
        cursor.execute('SELECT DISTINCT anio FROM resoluciones WHERE anio IS NOT NULL ORDER BY anio DESC')
        stats['anios_resoluciones'] = [row[0] for row in cursor.fetchall()]
    else:
        stats['total_resoluciones'] = 0
        stats['total_novedades_resoluciones'] = 0
        stats['anios_resoluciones'] = []

    # Total combinado
    stats['total_novedades'] = stats['total_novedades_decretos'] + stats['total_novedades_resoluciones']
    stats['total_documentos'] = stats['total_decretos'] + stats['total_resoluciones']

    # Novedades de decretos por tipo
    cursor.execute('''
        SELECT codigo_novedad, tipo_novedad, COUNT(*) as total
        FROM novedades
        GROUP BY codigo_novedad
        ORDER BY total DESC
    ''')
    stats['por_tipo_decretos'] = [dict(row) for row in cursor.fetchall()]

    # Novedades de resoluciones por tipo (si existe)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='novedades_resoluciones'")
    if cursor.fetchone():
        cursor.execute('''
            SELECT codigo_novedad, tipo_novedad, COUNT(*) as total
            FROM novedades_resoluciones
            GROUP BY codigo_novedad
            ORDER BY total DESC
        ''')
        stats['por_tipo_resoluciones'] = [dict(row) for row in cursor.fetchall()]
    else:
        stats['por_tipo_resoluciones'] = []

    # Años disponibles (combinados)
    cursor.execute('SELECT DISTINCT anio FROM decretos WHERE anio IS NOT NULL ORDER BY anio DESC')
    anios_decretos = set(row[0] for row in cursor.fetchall())

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='resoluciones'")
    if cursor.fetchone():
        cursor.execute('SELECT DISTINCT anio FROM resoluciones WHERE anio IS NOT NULL')
        anios_resoluciones = set(row[0] for row in cursor.fetchall())
        stats['anios'] = sorted(anios_decretos | anios_resoluciones, reverse=True)
    else:
        stats['anios'] = sorted(anios_decretos, reverse=True)

    conn.close()
    return jsonify(stats)


@app.route('/api/buscar')
def buscar():
    """
    Buscar novedades por cédula y/o apellidos
    Parámetros: 
        - decreto: número de decreto (opcional)
        - cedula: número de cédula (opcional)
        - apellido1: primer apellido (opcional)
        - apellido2: segundo apellido (opcional)
        - anio: filtrar por año (opcional)
        - tipo: filtrar por código de novedad (opcional)
    """
    decreto = request.args.get('decreto', '').strip()
    cedula = request.args.get('cedula', '').strip()
    apellido1 = request.args.get('apellido1', '').strip()
    apellido2 = request.args.get('apellido2', '').strip()
    anio = request.args.get('anio', '')
    tipo = request.args.get('tipo', '')
    
    if not decreto and not cedula and not apellido1 and not apellido2 and not anio and not tipo:
        return jsonify({'error': 'Debe proporcionar al menos un criterio de búsqueda'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Construir query dinámicamente
    query = '''
        SELECT 
            f.cedula,
            f.nombre_completo,
            f.nombres,
            f.apellidos,
            n.codigo_novedad,
            n.tipo_novedad,
            n.cargo_actual,
            n.dependencia,
            n.fecha_inicio_texto,
            n.fecha_fin_texto,
            n.observaciones,
            d.numero_decreto,
            d.fecha_decreto_texto,
            d.anio,
            d.dia_decreto,
            d.mes_decreto,
            d.anio_decreto,
            d.archivo_origen,
            d.ruta_completa
        FROM novedades n
        LEFT JOIN funcionarios f ON n.funcionario_id = f.id
        LEFT JOIN decretos d ON n.decreto_id = d.id
        WHERE 1=1
    '''
    params = []
    
    # Búsqueda por número de decreto
    if decreto:
        query += ' AND d.numero_decreto LIKE ?'
        params.append(f'%{decreto}%')
    
    # Búsqueda por cédula
    if cedula:
        query += ' AND f.cedula LIKE ?'
        params.append(f'%{cedula}%')
    
    # Búsqueda por primer apellido
    if apellido1:
        query += ' AND (f.apellidos LIKE ? OR f.nombre_completo LIKE ?)'
        params.append(f'{apellido1}%')
        params.append(f'%{apellido1}%')
    
    # Búsqueda por segundo apellido
    if apellido2:
        query += ' AND (f.apellidos LIKE ? OR f.nombre_completo LIKE ?)'
        params.append(f'%{apellido2}%')
        params.append(f'%{apellido2}%')
    
    # Filtro por año
    if anio and anio.isdigit():
        query += ' AND d.anio = ?'
        params.append(int(anio))

    
    # Filtro por tipo de novedad
    if tipo:
        query += ' AND n.codigo_novedad = ?'
        params.append(tipo)
    
    query += ' ORDER BY d.anio DESC, f.nombre_completo LIMIT 500'
    
    cursor.execute(query, params)
    results = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        'total': len(results),
        'resultados': results
    })


@app.route('/api/funcionario/<cedula>')
def get_funcionario(cedula):
    """Obtener todas las novedades de un funcionario por cédula"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Info del funcionario
    cursor.execute('SELECT * FROM funcionarios WHERE cedula = ?', (cedula,))
    funcionario = cursor.fetchone()
    
    if not funcionario:
        conn.close()
        return jsonify({'error': 'Funcionario no encontrado'}), 404
    
    # Novedades del funcionario
    cursor.execute('''
        SELECT 
            n.*,
            d.numero_decreto,
            d.fecha_decreto_texto,
            d.anio,
            d.dia_decreto,
            d.mes_decreto,
            d.anio_decreto,
            d.archivo_origen,
            d.ruta_completa
        FROM novedades n
        LEFT JOIN decretos d ON n.decreto_id = d.id
        WHERE n.funcionario_id = ?
        ORDER BY d.anio DESC, n.id DESC
    ''', (funcionario['id'],))
    
    novedades = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        'funcionario': dict(funcionario),
        'novedades': novedades,
        'total_novedades': len(novedades)
    })


@app.route('/api/tipos')
def get_tipos():
    """Obtener lista de tipos de novedades"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT codigo, descripcion, tipo_general FROM codigos_novedad ORDER BY codigo')
    tipos = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return jsonify(tipos)


@app.route('/api/errores')
def get_errores():
    """Obtener lista de errores de procesamiento"""
    tipo = request.args.get('tipo', '')
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Query base
    query = '''
        SELECT id, archivo, tipo_error, mensaje_error as mensaje, fecha_error as fecha
        FROM errores_procesamiento
        WHERE 1=1
    '''
    params = []
    
    if tipo:
        query += ' AND tipo_error = ?'
        params.append(tipo)
    
    query += ' ORDER BY fecha_error DESC LIMIT 500'
    
    cursor.execute(query, params)
    errores = [dict(row) for row in cursor.fetchall()]
    
    # Obtener tipos de errores para filtro
    cursor.execute('SELECT DISTINCT tipo_error, COUNT(*) as total FROM errores_procesamiento GROUP BY tipo_error ORDER BY total DESC')
    tipos_error = [dict(row) for row in cursor.fetchall()]
    
    # Total de errores
    cursor.execute('SELECT COUNT(*) FROM errores_procesamiento')
    total = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'total': total,
        'tipos': tipos_error,
        'errores': errores
    })


@app.route('/api/aprendizaje')
def get_aprendizaje():
    """Obtener ejemplos de aprendizaje del LLM"""
    codigo = request.args.get('codigo', '')
    limit = int(request.args.get('limit', 50))
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Verificar si la tabla existe
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ejemplos_aprendizaje'")
    if not cursor.fetchone():
        conn.close()
        return jsonify({'total': 0, 'ejemplos': [], 'por_codigo': []})
    
    # Query base
    query = '''
        SELECT id, codigo_novedad, 
               substr(texto_ejemplo, 1, 300) as texto_preview,
               razonamiento, nombre_archivo, confianza, fecha_creacion
        FROM ejemplos_aprendizaje
        WHERE 1=1
    '''
    params = []
    
    if codigo:
        query += ' AND codigo_novedad = ?'
        params.append(codigo)
    
    query += ' ORDER BY fecha_creacion DESC LIMIT ?'
    params.append(limit)
    
    cursor.execute(query, params)
    ejemplos = [dict(row) for row in cursor.fetchall()]
    
    # Estadísticas por código
    cursor.execute('''
        SELECT codigo_novedad, COUNT(*) as total, AVG(confianza) as confianza_promedio
        FROM ejemplos_aprendizaje 
        GROUP BY codigo_novedad 
        ORDER BY total DESC
    ''')
    por_codigo = [dict(row) for row in cursor.fetchall()]
    
    # Total
    cursor.execute('SELECT COUNT(*) FROM ejemplos_aprendizaje')
    total = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'total': total,
        'ejemplos': ejemplos,
        'por_codigo': por_codigo
    })


@app.route('/api/stats/detallado')
def get_stats_detallado():
    """Estadísticas detalladas incluyendo métodos de extracción (decretos + resoluciones)"""
    conn = get_db()
    cursor = conn.cursor()

    stats = {}

    # ========== DECRETOS ==========
    cursor.execute('SELECT COUNT(*) FROM decretos')
    stats['total_decretos'] = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM funcionarios')
    stats['total_funcionarios'] = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM novedades')
    stats['total_novedades_decretos'] = cursor.fetchone()[0]

    # Por método de extracción - Decretos
    cursor.execute('''
        SELECT tipo_extraccion, COUNT(*) as cantidad
        FROM decretos
        GROUP BY tipo_extraccion
    ''')
    stats['decretos_por_metodo'] = [dict(row) for row in cursor.fetchall()]

    # Por año - Decretos
    cursor.execute('''
        SELECT anio, COUNT(*) as cantidad
        FROM decretos
        WHERE anio IS NOT NULL
        GROUP BY anio
        ORDER BY anio DESC
    ''')
    stats['decretos_por_anio'] = [dict(row) for row in cursor.fetchall()]

    # Novedades de decretos por tipo
    cursor.execute('''
        SELECT n.codigo_novedad, c.descripcion, c.tipo_general, COUNT(*) as total
        FROM novedades n
        LEFT JOIN codigos_novedad c ON n.codigo_novedad = c.codigo
        GROUP BY n.codigo_novedad
        ORDER BY total DESC
        LIMIT 20
    ''')
    stats['novedades_decretos_por_tipo'] = [dict(row) for row in cursor.fetchall()]

    # Pendientes de revisión - Decretos
    cursor.execute('''
        SELECT COUNT(*) FROM novedades
        WHERE codigo_novedad = 'PENDIENTE_REVISION' OR codigo_novedad NOT IN
        (SELECT codigo FROM codigos_novedad)
    ''')
    stats['decretos_pendientes_revision'] = cursor.fetchone()[0]

    # ========== RESOLUCIONES ==========
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='resoluciones'")
    if cursor.fetchone():
        cursor.execute('SELECT COUNT(*) FROM resoluciones')
        stats['total_resoluciones'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM novedades_resoluciones')
        stats['total_novedades_resoluciones'] = cursor.fetchone()[0]

        # Por método de extracción - Resoluciones
        cursor.execute('''
            SELECT tipo_extraccion, COUNT(*) as cantidad
            FROM resoluciones
            GROUP BY tipo_extraccion
        ''')
        stats['resoluciones_por_metodo'] = [dict(row) for row in cursor.fetchall()]

        # Por año - Resoluciones
        cursor.execute('''
            SELECT anio, COUNT(*) as cantidad
            FROM resoluciones
            WHERE anio IS NOT NULL
            GROUP BY anio
            ORDER BY anio DESC
        ''')
        stats['resoluciones_por_anio'] = [dict(row) for row in cursor.fetchall()]

        # Novedades de resoluciones por tipo
        cursor.execute('''
            SELECT nr.codigo_novedad, cnr.descripcion, cnr.tipo_general, COUNT(*) as total
            FROM novedades_resoluciones nr
            LEFT JOIN codigos_novedad_resolucion cnr ON nr.codigo_novedad = cnr.codigo
            GROUP BY nr.codigo_novedad
            ORDER BY total DESC
            LIMIT 20
        ''')
        stats['novedades_resoluciones_por_tipo'] = [dict(row) for row in cursor.fetchall()]

        # Pendientes de revisión humana - Resoluciones
        cursor.execute("SELECT COUNT(*) FROM resoluciones WHERE requiere_revision_humana = 1")
        stats['resoluciones_pendientes_revision'] = cursor.fetchone()[0]

        # Por autoridad que firma
        cursor.execute('''
            SELECT autoridad_firma, COUNT(*) as total
            FROM resoluciones
            WHERE autoridad_firma IS NOT NULL AND autoridad_firma != ''
            GROUP BY autoridad_firma
            ORDER BY total DESC
            LIMIT 10
        ''')
        stats['resoluciones_por_autoridad'] = [dict(row) for row in cursor.fetchall()]
    else:
        stats['total_resoluciones'] = 0
        stats['total_novedades_resoluciones'] = 0
        stats['resoluciones_por_metodo'] = []
        stats['resoluciones_por_anio'] = []
        stats['novedades_resoluciones_por_tipo'] = []
        stats['resoluciones_pendientes_revision'] = 0
        stats['resoluciones_por_autoridad'] = []

    # ========== TOTALES COMBINADOS ==========
    stats['total_novedades'] = stats['total_novedades_decretos'] + stats['total_novedades_resoluciones']
    stats['total_documentos'] = stats['total_decretos'] + stats['total_resoluciones']
    stats['pendientes_revision'] = stats['decretos_pendientes_revision'] + stats.get('resoluciones_pendientes_revision', 0)

    # Ejemplos de aprendizaje
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ejemplos_aprendizaje'")
    if cursor.fetchone():
        cursor.execute('SELECT COUNT(*) FROM ejemplos_aprendizaje')
        stats['total_ejemplos_aprendizaje'] = cursor.fetchone()[0]
    else:
        stats['total_ejemplos_aprendizaje'] = 0

    # Errores
    cursor.execute('SELECT COUNT(*) FROM errores_procesamiento')
    stats['total_errores'] = cursor.fetchone()[0]

    conn.close()
    return jsonify(stats)


@app.route('/analisis')
def analisis_page():
    """Página de análisis del sistema de aprendizaje"""
    return send_from_directory('static', 'analisis.html')


@app.route('/api/razonamientos')
def get_razonamientos():
    """Obtener ejemplos de razonamientos del LLM para análisis"""
    limit = int(request.args.get('limit', 20))

    conn = get_db()
    cursor = conn.cursor()

    # Verificar si la tabla existe
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ejemplos_aprendizaje'")
    if not cursor.fetchone():
        conn.close()
        return jsonify({'razonamientos': []})

    cursor.execute('''
        SELECT codigo_novedad, razonamiento, nombre_archivo, confianza
        FROM ejemplos_aprendizaje
        WHERE razonamiento IS NOT NULL AND razonamiento != ''
        ORDER BY fecha_creacion DESC
        LIMIT ?
    ''', (limit,))

    razonamientos = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({'razonamientos': razonamientos})


# ==================== RESOLUCIONES ====================

@app.route('/resoluciones')
def resoluciones_page():
    """Página de consulta de resoluciones"""
    return send_from_directory('static', 'resoluciones.html')


@app.route('/resoluciones/huerfanas')
def resoluciones_huerfanas_page():
    """Página de revisión de resoluciones huérfanas/pendientes"""
    return send_from_directory('static', 'resoluciones_huerfanas.html')


@app.route('/api/resoluciones/stats')
def get_resoluciones_stats():
    """Estadísticas de resoluciones"""
    conn = get_db()
    cursor = conn.cursor()

    stats = {}

    # Verificar si la tabla existe
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='resoluciones'")
    if not cursor.fetchone():
        conn.close()
        return jsonify({
            'total_resoluciones': 0,
            'total_novedades_resoluciones': 0,
            'por_tipo': [],
            'por_anio': [],
            'pendientes_revision': 0,
            'mensaje': 'Tabla de resoluciones no existe aún'
        })

    # Conteos generales
    cursor.execute('SELECT COUNT(*) FROM resoluciones')
    stats['total_resoluciones'] = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM novedades_resoluciones')
    stats['total_novedades_resoluciones'] = cursor.fetchone()[0]

    # Funcionarios unicos en resoluciones
    cursor.execute('SELECT COUNT(DISTINCT funcionario_id) FROM novedades_resoluciones WHERE funcionario_id IS NOT NULL')
    stats['total_funcionarios'] = cursor.fetchone()[0]

    # Por tipo de novedad
    cursor.execute('''
        SELECT nr.codigo_novedad, cnr.descripcion, cnr.tipo_general, COUNT(*) as total
        FROM novedades_resoluciones nr
        LEFT JOIN codigos_novedad_resolucion cnr ON nr.codigo_novedad = cnr.codigo
        GROUP BY nr.codigo_novedad
        ORDER BY total DESC
    ''')
    stats['por_tipo'] = [dict(row) for row in cursor.fetchall()]

    # Por año
    cursor.execute('''
        SELECT anio, COUNT(*) as cantidad
        FROM resoluciones
        WHERE anio IS NOT NULL
        GROUP BY anio
        ORDER BY anio DESC
    ''')
    stats['por_anio'] = [dict(row) for row in cursor.fetchall()]

    # Pendientes de revisión humana
    cursor.execute("SELECT COUNT(*) FROM resoluciones WHERE requiere_revision_humana = 1")
    stats['pendientes_revision'] = cursor.fetchone()[0]

    # Por autoridad que firma
    cursor.execute('''
        SELECT autoridad_firma, COUNT(*) as total
        FROM resoluciones
        WHERE autoridad_firma IS NOT NULL
        GROUP BY autoridad_firma
        ORDER BY total DESC
        LIMIT 10
    ''')
    stats['por_autoridad'] = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return jsonify(stats)


@app.route('/api/resoluciones/buscar')
def buscar_resoluciones():
    """
    Buscar novedades de resoluciones por cédula y/o apellidos
    Parámetros:
        - resolucion: número de resolución (opcional)
        - cedula: número de cédula (opcional)
        - apellido1: primer apellido (opcional)
        - apellido2: segundo apellido (opcional)
        - anio: filtrar por año (opcional)
        - tipo: filtrar por código de novedad (opcional)
    """
    resolucion = request.args.get('resolucion', '').strip()
    cedula = request.args.get('cedula', '').strip()
    apellido1 = request.args.get('apellido1', '').strip()
    apellido2 = request.args.get('apellido2', '').strip()
    anio = request.args.get('anio', '')
    tipo = request.args.get('tipo', '')

    conn = get_db()
    cursor = conn.cursor()

    # Verificar si la tabla existe
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='resoluciones'")
    if not cursor.fetchone():
        conn.close()
        return jsonify({'total': 0, 'resultados': [], 'mensaje': 'Tabla de resoluciones no existe'})

    query = '''
        SELECT
            f.cedula,
            f.nombre_completo,
            f.nombres,
            f.apellidos,
            nr.codigo_novedad,
            nr.tipo_novedad,
            nr.cargo_actual,
            nr.dependencia,
            nr.fecha_inicio_texto,
            nr.fecha_fin_texto,
            nr.dias_otorgados,
            nr.motivo,
            nr.es_remunerada,
            nr.observaciones,
            r.numero_resolucion,
            r.fecha_resolucion_texto,
            r.anio,
            r.dia_resolucion,
            r.mes_resolucion,
            r.anio_resolucion,
            r.archivo_origen,
            r.ruta_completa,
            r.autoridad_firma,
            r.requiere_revision_humana,
            r.razonamiento_llm
        FROM novedades_resoluciones nr
        LEFT JOIN funcionarios f ON nr.funcionario_id = f.id
        LEFT JOIN resoluciones r ON nr.resolucion_id = r.id
        WHERE 1=1
    '''
    params = []

    if resolucion:
        query += ' AND r.numero_resolucion LIKE ?'
        params.append(f'%{resolucion}%')

    if cedula:
        query += ' AND f.cedula LIKE ?'
        params.append(f'%{cedula}%')

    if apellido1:
        query += ' AND (f.apellidos LIKE ? OR f.nombre_completo LIKE ?)'
        params.append(f'{apellido1}%')
        params.append(f'%{apellido1}%')

    if apellido2:
        query += ' AND (f.apellidos LIKE ? OR f.nombre_completo LIKE ?)'
        params.append(f'%{apellido2}%')
        params.append(f'%{apellido2}%')

    if anio and anio.isdigit():
        query += ' AND r.anio = ?'
        params.append(int(anio))

    if tipo:
        query += ' AND nr.codigo_novedad = ?'
        params.append(tipo)

    query += ' ORDER BY r.anio DESC, f.nombre_completo LIMIT 500'

    cursor.execute(query, params)
    results = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return jsonify({
        'total': len(results),
        'resultados': results,
        'tipo_documento': 'RESOLUCION'
    })


@app.route('/api/resoluciones/tipos')
def get_tipos_resolucion():
    """Obtener lista de tipos de novedades de resoluciones"""
    conn = get_db()
    cursor = conn.cursor()

    # Verificar si la tabla existe
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='codigos_novedad_resolucion'")
    if not cursor.fetchone():
        conn.close()
        return jsonify([])

    cursor.execute('SELECT codigo, descripcion, tipo_general, articulo_decreto FROM codigos_novedad_resolucion ORDER BY tipo_general, codigo')
    tipos = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return jsonify(tipos)


@app.route('/api/resoluciones/huerfanas')
def get_resoluciones_huerfanas():
    """
    Obtener resoluciones huérfanas (sin novedades o con PENDIENTE_REVISION)
    Parámetros:
        - anio: filtrar por año
        - resolucion: buscar por número de resolución
        - solo_pendientes: solo las que requieren revisión humana (default: false)
    """
    anio = request.args.get('anio', '')
    resolucion = request.args.get('resolucion', '').strip()
    solo_pendientes = request.args.get('solo_pendientes', 'false') == 'true'

    conn = get_db()
    cursor = conn.cursor()

    # Verificar si la tabla existe
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='resoluciones'")
    if not cursor.fetchone():
        conn.close()
        return jsonify({'total': 0, 'huerfanas': [], 'mensaje': 'Tabla de resoluciones no existe'})

    query = '''
        SELECT
            r.id,
            r.numero_resolucion,
            r.anio,
            r.fecha_resolucion_texto,
            r.contenido_texto,
            r.ruta_completa,
            r.archivo_origen,
            r.tipo_extraccion,
            r.autoridad_firma,
            r.requiere_revision_humana,
            r.motivo_revision,
            (SELECT COUNT(*) FROM novedades_resoluciones nr WHERE nr.resolucion_id = r.id) as num_novedades,
            (SELECT nr.codigo_novedad FROM novedades_resoluciones nr WHERE nr.resolucion_id = r.id LIMIT 1) as codigo
        FROM resoluciones r
        WHERE 1=1
    '''
    params = []

    if anio and anio.isdigit():
        query += ' AND r.anio = ?'
        params.append(int(anio))

    if resolucion:
        query += ' AND r.numero_resolucion LIKE ?'
        params.append(f'%{resolucion}%')

    if solo_pendientes:
        query += ' AND r.requiere_revision_humana = 1'
    else:
        query += ''' AND (
            (SELECT COUNT(*) FROM novedades_resoluciones nr WHERE nr.resolucion_id = r.id) = 0
            OR r.requiere_revision_humana = 1
            OR r.id IN (SELECT resolucion_id FROM novedades_resoluciones WHERE codigo_novedad = 'PENDIENTE_REVISION')
        )'''

    query += ' ORDER BY r.anio DESC, r.numero_resolucion LIMIT 500'

    cursor.execute(query, params)
    results = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return jsonify({
        'total': len(results),
        'huerfanas': results
    })


@app.route('/api/resoluciones/<int:resolucion_id>')
def get_resolucion_detail(resolucion_id):
    """Obtener detalles completos de una resolución para revisión"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM resoluciones WHERE id = ?', (resolucion_id,))
    resolucion = cursor.fetchone()

    if not resolucion:
        conn.close()
        return jsonify({'error': 'Resolución no encontrada'}), 404

    # Obtener novedades existentes
    cursor.execute('''
        SELECT nr.*, f.cedula, f.nombre_completo, f.nombres, f.apellidos
        FROM novedades_resoluciones nr
        LEFT JOIN funcionarios f ON nr.funcionario_id = f.id
        WHERE nr.resolucion_id = ?
    ''', (resolucion_id,))
    novedades = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return jsonify({
        'resolucion': dict(resolucion),
        'novedades': novedades,
        'tiene_novedades': len(novedades) > 0
    })


@app.route('/api/corregir/resolucion', methods=['POST'])
def corregir_resolucion():
    """
    Guardar corrección manual de una resolución.
    Crea novedades_resoluciones y funcionarios, guarda en ejemplos_aprendizaje.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos no proporcionados'}), 400

    resolucion_id = data.get('resolucion_id')
    codigo_novedad = data.get('codigo_novedad')
    tipo_novedad = data.get('tipo_novedad')
    funcionarios = data.get('funcionarios', [])
    razonamiento = data.get('razonamiento', '')

    if not resolucion_id or not codigo_novedad:
        return jsonify({'error': 'resolucion_id y codigo_novedad son requeridos'}), 400

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT * FROM resoluciones WHERE id = ?', (resolucion_id,))
        resolucion = cursor.fetchone()
        if not resolucion:
            conn.close()
            return jsonify({'error': 'Resolución no encontrada'}), 404

        # Eliminar novedades anteriores con PENDIENTE_REVISION
        cursor.execute('''
            DELETE FROM novedades_resoluciones
            WHERE resolucion_id = ? AND codigo_novedad = 'PENDIENTE_REVISION'
        ''', (resolucion_id,))

        created_novedades = []
        created_funcionarios = []

        for func_data in funcionarios:
            cedula = func_data.get('cedula', '').replace('.', '').strip()
            nombre_completo = func_data.get('nombre_completo', '')
            nombres = func_data.get('nombres', '')
            apellidos = func_data.get('apellidos', '')
            cargo = func_data.get('cargo', '')
            dependencia = func_data.get('dependencia', '')
            accion = func_data.get('accion', '')
            dias_otorgados = func_data.get('dias_otorgados')
            motivo = func_data.get('motivo', '')
            es_remunerada = func_data.get('es_remunerada')
            fecha_inicio_texto = func_data.get('fecha_inicio_texto', '')
            fecha_fin_texto = func_data.get('fecha_fin_texto', '')

            # Crear o buscar funcionario
            funcionario_id = None
            if cedula:
                cursor.execute('SELECT id FROM funcionarios WHERE cedula = ?', (cedula,))
                existing = cursor.fetchone()
                if existing:
                    funcionario_id = existing[0]
                else:
                    cursor.execute('''
                        INSERT INTO funcionarios (cedula, nombre_completo, nombres, apellidos)
                        VALUES (?, ?, ?, ?)
                    ''', (cedula, nombre_completo, nombres, apellidos))
                    funcionario_id = cursor.lastrowid
                    created_funcionarios.append(funcionario_id)

            # Crear novedad de resolución
            cursor.execute('''
                INSERT INTO novedades_resoluciones (
                    resolucion_id, funcionario_id, codigo_novedad, tipo_novedad,
                    cargo_actual, dependencia, observaciones,
                    dias_otorgados, motivo, es_remunerada,
                    fecha_inicio_texto, fecha_fin_texto, fecha_creacion
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ''', (resolucion_id, funcionario_id, codigo_novedad, tipo_novedad,
                  cargo, dependencia, accion,
                  dias_otorgados, motivo, es_remunerada,
                  fecha_inicio_texto, fecha_fin_texto))
            created_novedades.append(cursor.lastrowid)

        # Si no hay funcionarios, crear novedad sin funcionario
        if not funcionarios:
            cursor.execute('''
                INSERT INTO novedades_resoluciones (
                    resolucion_id, codigo_novedad, tipo_novedad, observaciones, fecha_creacion
                ) VALUES (?, ?, ?, ?, datetime('now'))
            ''', (resolucion_id, codigo_novedad, tipo_novedad, razonamiento))
            created_novedades.append(cursor.lastrowid)

        # Marcar resolución como revisada
        cursor.execute('''
            UPDATE resoluciones SET requiere_revision_humana = 0 WHERE id = ?
        ''', (resolucion_id,))

        # Guardar en ejemplos_aprendizaje para refuerzo
        texto_ejemplo = resolucion['contenido_texto'][:5000] if resolucion['contenido_texto'] else ''
        respuesta_llm = json.dumps({
            'codigo_novedad': codigo_novedad,
            'tipo_novedad': tipo_novedad,
            'funcionarios': funcionarios
        }, ensure_ascii=False)

        cursor.execute('''
            INSERT INTO ejemplos_aprendizaje (
                codigo_novedad, texto_ejemplo, respuesta_llm, razonamiento,
                nombre_archivo, confianza
            ) VALUES (?, ?, ?, ?, ?, 1.0)
        ''', (codigo_novedad, texto_ejemplo, respuesta_llm, razonamiento,
              resolucion['archivo_origen'] if resolucion['archivo_origen'] else ''))

        conn.commit()

        return jsonify({
            'success': True,
            'message': f'Corrección guardada: {len(created_novedades)} novedades, {len(created_funcionarios)} funcionarios nuevos',
            'novedades_creadas': created_novedades,
            'funcionarios_creados': created_funcionarios
        })

    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/validar_correccion/resolucion', methods=['POST'])
def validar_correccion_resolucion():
    """
    Validar corrección de resolución usando el LLM configurado.
    Analiza el texto OCR y extrae funcionarios con campos específicos de resoluciones.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos no proporcionados'}), 400

    texto_ocr = data.get('texto_ocr', '')[:4000]
    codigo_propuesto = data.get('codigo_novedad', '')
    tipo_propuesto = data.get('tipo_novedad', '')
    razonamiento_usuario = data.get('razonamiento', '')

    prompt = f"""Eres un experto en análisis de resoluciones administrativas de la Procuraduría General de la Nación de Colombia.

TEXTO OCR DE LA RESOLUCIÓN (puede tener errores - palabras pegadas):
{texto_ocr}

CORRECCIÓN PROPUESTA POR EL USUARIO:
- Código de novedad: {codigo_propuesto} ({tipo_propuesto})
- Razonamiento: {razonamiento_usuario}

REGLAS CRÍTICAS PARA RESOLUCIONES:

1. ESTRUCTURA DE RESOLUCIONES:
   - Las resoluciones típicamente CONCEDEN, OTORGAN o DECRETAN novedades
   - Pueden contener múltiples funcionarios con la misma novedad
   - El funcionario tiene cédula y se identifica como sujeto de la novedad

2. TIPOS DE NOVEDAD DE RESOLUCIONES:

   VACACIONES (VAC): "Conceder vacaciones a [NOMBRE], cédula [X], [CARGO]"
   - Extraer: dias_otorgados, fecha_inicio, fecha_fin

   LICENCIAS: LR (Remunerada), LNR (No Remunerada), LNRE (Estudios), LMAT (Maternidad),
   LPAT (Paternidad), LENF (Enfermedad), LLUT (Luto), LDEP (Deportiva)
   - Extraer: dias_otorgados, motivo, es_remunerada

   COMISIONES: CSER (Servicio), CEST (Estudios), CESP (Especial)
   - Extraer: motivo, fecha_inicio, fecha_fin

   ENCARGOS: E, ECOM, ELIC, ETEMP, EVAC
   - Extraer: cargo encargado, motivo

   SANCIONES: SUSP, SUSPD, MULTA, D, DESINH, AMONES, SUSPINH
   NOMBRAMIENTOS: N, NORD, NPROV
   RENUNCIAS: R, RCAR
   OTRAS: REV, COJ, NEG, RET, REINC, RECL, PCOM, PLIC, PPOS, TCOM, TENC, TPROV, IVAC, PERM, T

3. SOLO extrae funcionarios con CÉDULA.

Responde ÚNICAMENTE con JSON (sin markdown):
{{
    "codigo_valido": true/false,
    "codigo_sugerido": "código correcto si incorrecto",
    "tipo_sugerido": "descripción del código",
    "confianza": 0.0-1.0,
    "observaciones": "breve análisis",
    "funcionarios_extraidos": [
        {{
            "cedula": "número SIN puntos",
            "nombre_completo": "NOMBRES APELLIDOS",
            "cargo": "cargo del funcionario",
            "dependencia": "dependencia",
            "accion": "descripción de la novedad",
            "dias_otorgados": null,
            "motivo": "motivo de la novedad",
            "es_remunerada": true/false,
            "fecha_inicio_texto": "fecha inicio",
            "fecha_fin_texto": "fecha fin"
        }}
    ],
    "correcciones_ocr": ["errores OCR corregidos"],
    "razonamiento_mejorado": "razonamiento para aprendizaje"
}}"""

    try:
        system_message = "Eres un experto legal en resoluciones administrativas colombianas. Responde ÚNICAMENTE con JSON válido, sin marcadores de código ni texto adicional."
        llm_result = llamar_llm(prompt, system_message, temperature=0.2, max_tokens=1500)
        content = llm_result['content']
        modelo_usado = llm_result['modelo']

        # Parsear JSON
        try:
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            validacion = json.loads(content.strip())
        except json.JSONDecodeError:
            validacion = {
                'codigo_valido': True,
                'observaciones': content[:500],
                'confianza': 0.5
            }

        # Validación de integridad de cédulas
        alertas_cedula = []
        funcionarios_extraidos = validacion.get('funcionarios_extraidos', [])
        if funcionarios_extraidos:
            alertas_cedula = validar_integridad_cedulas(funcionarios_extraidos)
            alertas_warning = [a for a in alertas_cedula if a.get('nivel') == 'warning']
            if alertas_warning:
                advertencia = "\n\n⚠️ ADVERTENCIA DE INTEGRIDAD:\n"
                for alerta in alertas_warning:
                    advertencia += f"- {alerta.get('mensaje', '')}\n"
                    advertencia += f"  Sugerencia: {alerta.get('sugerencia', '')}\n"
                if 'observaciones' in validacion:
                    validacion['observaciones'] += advertencia
                else:
                    validacion['observaciones'] = advertencia

        return jsonify({
            'success': True,
            'validacion': validacion,
            'alertas_cedula': alertas_cedula,
            'modelo': modelo_usado
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/funcionario/<cedula>/completo')
def get_funcionario_completo(cedula):
    """Obtener todas las novedades de un funcionario (decretos + resoluciones)"""
    conn = get_db()
    cursor = conn.cursor()

    # Info del funcionario
    cursor.execute('SELECT * FROM funcionarios WHERE cedula = ?', (cedula,))
    funcionario = cursor.fetchone()

    if not funcionario:
        conn.close()
        return jsonify({'error': 'Funcionario no encontrado'}), 404

    resultado = {
        'funcionario': dict(funcionario),
        'decretos': [],
        'resoluciones': [],
        'total_decretos': 0,
        'total_resoluciones': 0
    }

    # Novedades de decretos
    cursor.execute('''
        SELECT
            n.*,
            d.numero_decreto,
            d.fecha_decreto_texto,
            d.anio,
            d.archivo_origen,
            d.ruta_completa,
            d.razonamiento_llm,
            'DECRETO' as tipo_documento
        FROM novedades n
        LEFT JOIN decretos d ON n.decreto_id = d.id
        WHERE n.funcionario_id = ?
        ORDER BY d.anio DESC, n.id DESC
    ''', (funcionario['id'],))
    resultado['decretos'] = [dict(row) for row in cursor.fetchall()]
    resultado['total_decretos'] = len(resultado['decretos'])

    # Novedades de resoluciones (si existe la tabla)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='novedades_resoluciones'")
    if cursor.fetchone():
        cursor.execute('''
            SELECT
                nr.*,
                r.numero_resolucion,
                r.fecha_resolucion_texto,
                r.anio,
                r.archivo_origen,
                r.ruta_completa,
                r.autoridad_firma,
                r.razonamiento_llm,
                'RESOLUCION' as tipo_documento
            FROM novedades_resoluciones nr
            LEFT JOIN resoluciones r ON nr.resolucion_id = r.id
            WHERE nr.funcionario_id = ?
            ORDER BY r.anio DESC, nr.id DESC
        ''', (funcionario['id'],))
        resultado['resoluciones'] = [dict(row) for row in cursor.fetchall()]
        resultado['total_resoluciones'] = len(resultado['resoluciones'])

    conn.close()

    return jsonify(resultado)


@app.route('/api/buscar/unificado')
def buscar_unificado():
    """
    Búsqueda unificada en decretos y resoluciones
    Parámetros:
        - cedula: número de cédula (opcional)
        - apellido1: primer apellido (opcional)
        - apellido2: segundo apellido (opcional)
        - anio: filtrar por año (opcional)
        - tipo: filtrar por código de novedad (opcional)
        - documento: DECRETO, RESOLUCION o TODOS (default: TODOS)
    """
    cedula = request.args.get('cedula', '').strip()
    apellido1 = request.args.get('apellido1', '').strip()
    apellido2 = request.args.get('apellido2', '').strip()
    anio = request.args.get('anio', '')
    tipo = request.args.get('tipo', '')
    tipo_documento = request.args.get('documento', 'TODOS').upper()

    if not cedula and not apellido1 and not apellido2 and not anio and not tipo:
        return jsonify({'error': 'Debe proporcionar al menos un criterio de búsqueda'}), 400

    conn = get_db()
    cursor = conn.cursor()

    resultados = []

    # Buscar en decretos
    if tipo_documento in ['TODOS', 'DECRETO']:
        query_decretos = '''
            SELECT
                f.cedula,
                f.nombre_completo,
                n.codigo_novedad,
                n.tipo_novedad,
                n.cargo_actual,
                n.dependencia,
                n.fecha_inicio_texto,
                n.fecha_fin_texto,
                n.observaciones,
                d.numero_decreto as numero_documento,
                d.fecha_decreto_texto as fecha_documento,
                d.anio,
                d.archivo_origen,
                d.ruta_completa,
                'DECRETO' as tipo_documento
            FROM novedades n
            LEFT JOIN funcionarios f ON n.funcionario_id = f.id
            LEFT JOIN decretos d ON n.decreto_id = d.id
            WHERE 1=1
        '''
        params = []

        if cedula:
            query_decretos += ' AND f.cedula LIKE ?'
            params.append(f'%{cedula}%')
        if apellido1:
            query_decretos += ' AND (f.apellidos LIKE ? OR f.nombre_completo LIKE ?)'
            params.append(f'{apellido1}%')
            params.append(f'%{apellido1}%')
        if apellido2:
            query_decretos += ' AND (f.apellidos LIKE ? OR f.nombre_completo LIKE ?)'
            params.append(f'%{apellido2}%')
            params.append(f'%{apellido2}%')
        if anio and anio.isdigit():
            query_decretos += ' AND d.anio = ?'
            params.append(int(anio))
        if tipo:
            query_decretos += ' AND n.codigo_novedad = ?'
            params.append(tipo)

        query_decretos += ' ORDER BY d.anio DESC LIMIT 250'
        cursor.execute(query_decretos, params)
        resultados.extend([dict(row) for row in cursor.fetchall()])

    # Buscar en resoluciones
    if tipo_documento in ['TODOS', 'RESOLUCION']:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='resoluciones'")
        if cursor.fetchone():
            query_resoluciones = '''
                SELECT
                    f.cedula,
                    f.nombre_completo,
                    nr.codigo_novedad,
                    nr.tipo_novedad,
                    nr.cargo_actual,
                    nr.dependencia,
                    nr.fecha_inicio_texto,
                    nr.fecha_fin_texto,
                    nr.observaciones,
                    r.numero_resolucion as numero_documento,
                    r.fecha_resolucion_texto as fecha_documento,
                    r.anio,
                    r.archivo_origen,
                    r.ruta_completa,
                    'RESOLUCION' as tipo_documento
                FROM novedades_resoluciones nr
                LEFT JOIN funcionarios f ON nr.funcionario_id = f.id
                LEFT JOIN resoluciones r ON nr.resolucion_id = r.id
                WHERE 1=1
            '''
            params = []

            if cedula:
                query_resoluciones += ' AND f.cedula LIKE ?'
                params.append(f'%{cedula}%')
            if apellido1:
                query_resoluciones += ' AND (f.apellidos LIKE ? OR f.nombre_completo LIKE ?)'
                params.append(f'{apellido1}%')
                params.append(f'%{apellido1}%')
            if apellido2:
                query_resoluciones += ' AND (f.apellidos LIKE ? OR f.nombre_completo LIKE ?)'
                params.append(f'%{apellido2}%')
                params.append(f'%{apellido2}%')
            if anio and anio.isdigit():
                query_resoluciones += ' AND r.anio = ?'
                params.append(int(anio))
            if tipo:
                query_resoluciones += ' AND nr.codigo_novedad = ?'
                params.append(tipo)

            query_resoluciones += ' ORDER BY r.anio DESC LIMIT 250'
            cursor.execute(query_resoluciones, params)
            resultados.extend([dict(row) for row in cursor.fetchall()])

    conn.close()

    # Ordenar resultados combinados por año descendente
    resultados.sort(key=lambda x: (x.get('anio') or 0, x.get('nombre_completo') or ''), reverse=True)

    return jsonify({
        'total': len(resultados),
        'resultados': resultados[:500]  # Limitar a 500 resultados totales
    })


# ==================== HALLAZGOS PARA REVISIÓN ====================

@app.route('/hallazgos')
def hallazgos_page():
    """Página de revisión de hallazgos de integridad"""
    return send_from_directory('static', 'hallazgos.html')


@app.route('/api/hallazgos')
def get_hallazgos():
    """
    Obtener hallazgos pendientes de revisión.
    Parámetros:
        - estado: filtrar por estado (PENDIENTE, REVISADO, DESCARTADO)
        - tipo: filtrar por tipo de hallazgo
        - anio: filtrar por año del decreto
        - limit: límite de resultados (default 100)
    """
    estado = request.args.get('estado', '')
    tipo = request.args.get('tipo', '')
    anio = request.args.get('anio', '')
    limit = int(request.args.get('limit', 100))
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Verificar si la tabla existe
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='hallazgos_revision'")
    if not cursor.fetchone():
        conn.close()
        return jsonify({'total': 0, 'hallazgos': [], 'tipos': [], 'estados': []})
    
    # Query base
    query = '''
        SELECT id, decreto_numero, decreto_anio, tipo_hallazgo,
               cedula_decreto, nombre_decreto, cedula_bd, nombre_bd,
               funcionario_id_bd, descripcion, estado, observaciones,
               fecha_creacion, fecha_revision, usuario_revision
        FROM hallazgos_revision
        WHERE 1=1
    '''
    params = []
    
    if estado:
        query += ' AND estado = ?'
        params.append(estado)
    
    if tipo:
        query += ' AND tipo_hallazgo = ?'
        params.append(tipo)
    
    if anio and anio.isdigit():
        query += ' AND decreto_anio = ?'
        params.append(int(anio))
    
    query += ' ORDER BY fecha_creacion DESC LIMIT ?'
    params.append(limit)
    
    cursor.execute(query, params)
    hallazgos = [dict(row) for row in cursor.fetchall()]
    
    # Tipos y estados para filtros
    cursor.execute('SELECT DISTINCT tipo_hallazgo, COUNT(*) as total FROM hallazgos_revision GROUP BY tipo_hallazgo')
    tipos = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute('SELECT DISTINCT estado, COUNT(*) as total FROM hallazgos_revision GROUP BY estado')
    estados = [dict(row) for row in cursor.fetchall()]
    
    # Totales
    cursor.execute('SELECT COUNT(*) FROM hallazgos_revision')
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM hallazgos_revision WHERE estado = 'PENDIENTE'")
    pendientes = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'total': total,
        'pendientes': pendientes,
        'hallazgos': hallazgos,
        'tipos': tipos,
        'estados': estados
    })


@app.route('/api/hallazgos', methods=['POST'])
def crear_hallazgo():
    """
    Crear un nuevo hallazgo para revisión.
    Body JSON:
        - decreto_numero: número del decreto
        - decreto_anio: año del decreto
        - tipo_hallazgo: CEDULA_OTRO_NOMBRE, NOMBRE_OTRA_CEDULA, etc.
        - cedula_decreto, nombre_decreto: datos según el decreto
        - cedula_bd, nombre_bd: datos en la base de datos
        - funcionario_id_bd: ID del funcionario en BD (opcional)
        - descripcion: descripción detallada
        - observaciones: observaciones adicionales (opcional)
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos no proporcionados'}), 400
    
    required_fields = ['decreto_numero', 'decreto_anio', 'tipo_hallazgo', 'descripcion']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Campo requerido: {field}'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO hallazgos_revision (
                decreto_numero, decreto_anio, tipo_hallazgo,
                cedula_decreto, nombre_decreto, cedula_bd, nombre_bd,
                funcionario_id_bd, descripcion, estado, observaciones
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDIENTE', ?)
        ''', (
            data.get('decreto_numero'),
            data.get('decreto_anio'),
            data.get('tipo_hallazgo'),
            data.get('cedula_decreto', ''),
            data.get('nombre_decreto', ''),
            data.get('cedula_bd', ''),
            data.get('nombre_bd', ''),
            data.get('funcionario_id_bd'),
            data.get('descripcion'),
            data.get('observaciones', '')
        ))
        
        hallazgo_id = cursor.lastrowid
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Hallazgo creado exitosamente',
            'hallazgo_id': hallazgo_id
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/hallazgos/<int:hallazgo_id>', methods=['PUT'])
def actualizar_hallazgo(hallazgo_id):
    """
    Actualizar estado de un hallazgo.
    Body JSON:
        - estado: PENDIENTE, REVISADO, DESCARTADO, CORREGIDO
        - observaciones: observaciones de la revisión
        - usuario_revision: nombre del usuario que revisa
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos no proporcionados'}), 400
    
    estado = data.get('estado', '')
    if estado not in ['PENDIENTE', 'REVISADO', 'DESCARTADO', 'CORREGIDO']:
        return jsonify({'error': 'Estado inválido. Usar: PENDIENTE, REVISADO, DESCARTADO, CORREGIDO'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE hallazgos_revision 
            SET estado = ?,
                observaciones = COALESCE(?, observaciones),
                fecha_revision = datetime('now'),
                usuario_revision = ?
            WHERE id = ?
        ''', (
            estado,
            data.get('observaciones'),
            data.get('usuario_revision', 'Sistema'),
            hallazgo_id
        ))
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'error': 'Hallazgo no encontrado'}), 404
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Hallazgo {hallazgo_id} actualizado a {estado}'
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# ==================== EXPEDIENTE ELECTRÓNICO ====================

# Configuración Azure OpenAI (fallback a credenciales de Azure_OPenAI_SDK.md)
AZURE_OPENAI_ENDPOINT = os.environ.get('AZURE_OPENAI_ENDPOINT', '')
AZURE_OPENAI_KEY = os.environ.get('AZURE_OPENAI_API_KEY', '')
AZURE_SEARCH_ENDPOINT = os.environ.get('AZURE_SEARCH_ENDPOINT', '')
AZURE_SEARCH_KEY = os.environ.get('AZURE_SEARCH_KEY', '')
AZURE_SEARCH_INDEX = os.environ.get('AZURE_SEARCH_INDEX', 'index-2026-v7')


def get_azure_openai_client():
    """Obtiene cliente Azure OpenAI si está configurado"""
    try:
        from openai import AzureOpenAI
        if not AZURE_OPENAI_KEY:
            return None
        return AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_KEY,
            api_version="2025-01-01-preview"
        )
    except ImportError:
        return None


@app.route('/expediente')
def expediente_page():
    """Página del Expediente Electrónico con IA"""
    return send_from_directory('static', 'expediente.html')


@app.route('/api/expediente/buscar')
def buscar_expediente():
    """
    Búsqueda multinivel para Expediente Electrónico.
    Niveles: 1=metadata, 2=fulltext, 3=rag, auto=todos
    """
    query = request.args.get('query', '').strip()
    nivel = request.args.get('nivel', 'auto')
    cedula_filtro = request.args.get('cedula', '').strip()
    anio_filtro = request.args.get('anio', '')
    limit = min(int(request.args.get('limit', 20)), 100)
    
    if not query and not cedula_filtro and not anio_filtro:
        return jsonify({'error': 'Se requiere al menos un criterio de búsqueda'}), 400
    
    resultados = {
        'query': query, 'nivel_solicitado': nivel,
        'niveles_ejecutados': [], 'total_resultados': 0,
        'resultados': [], 'expedientes_relacionados': []
    }
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Nivel 1: Metadata
        if nivel in ['1', 'metadata', 'auto']:
            metadata_results = _buscar_metadata(cursor, query, cedula_filtro, anio_filtro, limit)
            if metadata_results:
                resultados['niveles_ejecutados'].append('metadata')
                for r in metadata_results:
                    r['nivel_busqueda'] = 'metadata'
                    r['relevancia'] = 1.0
                resultados['resultados'].extend(metadata_results)
        
        # Nivel 2: Fulltext
        if nivel in ['2', 'fulltext', 'auto'] and query:
            fulltext_results = _buscar_fulltext(cursor, query, cedula_filtro, anio_filtro, limit)
            if fulltext_results:
                resultados['niveles_ejecutados'].append('fulltext')
                ids_existentes = {r.get('decreto_id') for r in resultados['resultados']}
                for r in fulltext_results:
                    if r.get('decreto_id') not in ids_existentes:
                        r['nivel_busqueda'] = 'fulltext'
                        r['relevancia'] = 0.8
                        resultados['resultados'].append(r)
        
        # Nivel 3: RAG
        if nivel in ['3', 'rag', 'auto'] and query:
            rag_results = _buscar_rag(query, cedula_filtro, anio_filtro, limit)
            if rag_results:
                resultados['niveles_ejecutados'].append('rag')
                resultados['rag_response'] = rag_results
        
        # Expedientes relacionados
        cedulas = {r.get('cedula') for r in resultados['resultados'] if r.get('cedula')}
        if cedulas:
            placeholders = ','.join('?' * len(cedulas))
            cursor.execute(f'''
                SELECT codigo_expediente, asunto, funcionario_responsable, 
                       cedula_funcionario, estado, hash_indice
                FROM expedientes WHERE cedula_funcionario IN ({placeholders})
            ''', list(cedulas))
            resultados['expedientes_relacionados'] = [dict(row) for row in cursor.fetchall()]
        
        resultados['total_resultados'] = len(resultados['resultados'])
    finally:
        conn.close()
    
    return jsonify(resultados)


def _buscar_metadata(cursor, query, cedula, anio, limit):
    """Nivel 1: Búsqueda exacta por metadatos"""
    sql = '''
        SELECT DISTINCT d.id as decreto_id, d.numero_decreto, d.anio,
               d.fecha_decreto_texto, d.ruta_completa, n.codigo_novedad,
               n.tipo_novedad, f.cedula, f.nombre_completo, n.cargo_actual, n.dependencia
        FROM decretos d
        LEFT JOIN novedades n ON d.id = n.decreto_id
        LEFT JOIN funcionarios f ON n.funcionario_id = f.id
        WHERE 1=1
    '''
    params = []
    
    if query:
        query_clean = query.replace('.', '').replace(' ', '')
        if query_clean.isdigit():
            sql += ' AND (f.cedula LIKE ? OR d.numero_decreto LIKE ?)'
            params.extend([f'%{query_clean}%', f'%{query}%'])
        else:
            sql += ' AND f.nombre_completo LIKE ?'
            params.append(f'%{query}%')
    
    if cedula:
        sql += ' AND f.cedula = ?'
        params.append(cedula.replace('.', '').replace(' ', ''))
    if anio and anio.isdigit():
        sql += ' AND d.anio = ?'
        params.append(int(anio))
    
    sql += f' ORDER BY d.anio DESC, d.numero_decreto DESC LIMIT {limit}'
    cursor.execute(sql, params)
    return [dict(row) for row in cursor.fetchall()]


def _buscar_fulltext(cursor, query, cedula, anio, limit):
    """Nivel 2: Búsqueda en contenido OCR o por funcionario si es cédula"""
    query_clean = query.replace('.', '').replace(' ', '') if query else ''
    
    # Si query es una cédula, buscar por nombre del funcionario en el texto
    search_terms = [query]
    if query_clean.isdigit():
        cursor.execute('SELECT nombre_completo FROM funcionarios WHERE cedula = ?', (query_clean,))
        func_row = cursor.fetchone()
        if func_row and func_row[0]:
            # Agregar nombre como término de búsqueda
            search_terms.append(func_row[0])
    
    results = []
    seen_ids = set()
    
    for term in search_terms:
        if not term:
            continue
        sql = '''
            SELECT DISTINCT d.id as decreto_id, d.numero_decreto, d.anio,
                   d.fecha_decreto_texto, d.ruta_completa,
                   substr(d.contenido_texto, 1, 300) as snippet,
                   n.codigo_novedad, n.tipo_novedad, f.cedula, f.nombre_completo
            FROM decretos d
            LEFT JOIN novedades n ON d.id = n.decreto_id
            LEFT JOIN funcionarios f ON n.funcionario_id = f.id
            WHERE (d.contenido_texto LIKE ? OR f.nombre_completo LIKE ?)
        '''
        params = [f'%{term}%', f'%{term}%']
        
        if cedula:
            sql += ' AND f.cedula = ?'
            params.append(cedula.replace('.', '').replace(' ', ''))
        if anio and anio.isdigit():
            sql += ' AND d.anio = ?'
            params.append(int(anio))
        
        sql += f' ORDER BY d.anio DESC LIMIT {limit}'
        cursor.execute(sql, params)
        
        for row in cursor.fetchall():
            row_dict = dict(row)
            if row_dict['decreto_id'] not in seen_ids:
                seen_ids.add(row_dict['decreto_id'])
                results.append(row_dict)
    
    return results[:limit]


def _buscar_rag(query, cedula, anio, limit):
    """Nivel 3: Búsqueda RAG con Azure OpenAI"""
    client = get_azure_openai_client()
    if not client:
        return {'error': 'Azure OpenAI no configurado. Configure AZURE_OPENAI_API_KEY', 'disponible': False}
    
    try:
        # Si query es cédula, enriquecer con nombre del funcionario
        query_clean = query.replace('.', '').replace(' ', '') if query else ''
        enriched_query = query
        
        if query_clean.isdigit():
            import sqlite3
            conn = sqlite3.connect(r"C:\temp\PNG_CERTIFICADO_V3\novedades_pgn.db")
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT nombre_completo FROM funcionarios WHERE cedula = ?', (query_clean,))
            row = c.fetchone()
            conn.close()
            if row and row[0]:
                enriched_query = f"Historia laboral del funcionario {row[0]} (cédula {query})"
        
        system_prompt = "Eres NOVED-IA, asistente de novedades de la PGN. Responde basándote solo en documentos indexados."
        user_query = enriched_query
        if cedula:
            user_query += f" (cédula: {cedula})"
        if anio:
            user_query += f" (año: {anio})"
        
        completion = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            max_tokens=2000,
            temperature=0.3,
            extra_body={
                "data_sources": [{
                    "type": "azure_search",
                    "parameters": {
                        "endpoint": AZURE_SEARCH_ENDPOINT,
                        "index_name": AZURE_SEARCH_INDEX,
                        "semantic_configuration": "default",
                        "query_type": "vector_semantic_hybrid",
                        "in_scope": True, "strictness": 3,
                        "top_n_documents": min(limit, 20),  # Increased to 20 references
                        "authentication": {"type": "api_key", "key": AZURE_SEARCH_KEY},
                        "embedding_dependency": {
                            "type": "deployment_name",
                            "deployment_name": "text-embedding-ada-002"
                        }
                    }
                }]
            }
        )
        return {'disponible': True, 'respuesta': completion.choices[0].message.content, 'modelo': 'gpt-4.1'}
    except Exception as e:
        return {'disponible': True, 'error': f'Error RAG: {str(e)}', 'respuesta': None}


@app.route('/api/expediente/<codigo>')
def get_expediente(codigo):
    """Obtener expediente completo con índice electrónico"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT e.*, t.codigo as serie_codigo, t.nombre as serie_nombre
            FROM expedientes e LEFT JOIN trd_series t ON e.serie_id = t.id
            WHERE e.codigo_expediente = ?
        ''', (codigo,))
        
        exp_row = cursor.fetchone()
        if not exp_row:
            return jsonify({'error': 'Expediente no encontrado'}), 404
        
        expediente = dict(exp_row)
        
        cursor.execute('''
            SELECT ed.*, d.numero_decreto, d.fecha_decreto_texto, d.archivo_origen
            FROM expediente_documentos ed
            LEFT JOIN decretos d ON ed.decreto_id = d.id
            WHERE ed.expediente_id = ? ORDER BY ed.orden
        ''', (expediente['id'],))
        
        documentos = [dict(row) for row in cursor.fetchall()]
        
        # Verificar integridad
        import hashlib
        indice_hash = hashlib.sha256()
        for doc in documentos:
            if doc.get('hash_documento'):
                indice_hash.update(doc['hash_documento'].encode())
        
        hash_calculado = indice_hash.hexdigest()
        
        return jsonify({
            'expediente': expediente,
            'indice_electronico': documentos,
            'total_documentos': len(documentos),
            'verificacion_integridad': {
                'hash_almacenado': expediente.get('hash_indice'),
                'hash_calculado': hash_calculado,
                'integridad_ok': hash_calculado == expediente.get('hash_indice')
            }
        })
    finally:
        conn.close()


@app.route('/api/expediente/lista')
def listar_expedientes():
    """Listar todos los expedientes"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT e.codigo_expediente, e.asunto, e.fecha_apertura, e.estado,
                   e.funcionario_responsable, e.cedula_funcionario, t.nombre as serie,
                   (SELECT COUNT(*) FROM expediente_documentos WHERE expediente_id = e.id) as num_docs
            FROM expedientes e LEFT JOIN trd_series t ON e.serie_id = t.id
            ORDER BY e.fecha_creacion DESC
        ''')
        expedientes = [dict(row) for row in cursor.fetchall()]
        return jsonify({'total': len(expedientes), 'expedientes': expedientes})
    finally:
        conn.close()


@app.route('/api/trd')
def get_trd():
    """Consultar Tabla de Retención Documental"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT * FROM trd_series ORDER BY codigo')
        series = [dict(row) for row in cursor.fetchall()]
        return jsonify({'total': len(series), 'series': series})
    finally:
        conn.close()


@app.route('/api/expediente/rag', methods=['POST'])
def buscar_rag_post():
    """Búsqueda RAG conversacional con Azure OpenAI"""
    data = request.get_json()
    if not data or not data.get('query'):
        return jsonify({'error': 'Query requerido'}), 400
    
    query = data['query']
    history = data.get('history', [])
    limit = data.get('limit', 20)
    
    client = get_azure_openai_client()
    if not client:
        return jsonify({'error': 'Azure OpenAI no configurado. Configure AZURE_OPENAI_API_KEY', 'disponible': False})
    
    try:
        # Build messages with history
        system_prompt = """Eres NOVED-IA, asistente experto en novedades de personal de la PGN (Procuraduría General de la Nación).
Tienes acceso al índice de decretos y resoluciones (index-2026-v7) con más de 57,000 documentos indexados.
Responde basándote ÚNICAMENTE en los documentos encontrados. Cita los números de decreto cuando sea posible.
Si no encuentras información relevante, indícalo claramente."""
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add history (last 6 messages max)
        for msg in history[-6:]:
            if msg.get('role') in ['user', 'assistant']:
                messages.append({"role": msg['role'], "content": msg['content']})
        
        # Add current query
        messages.append({"role": "user", "content": query})
        
        completion = client.chat.completions.create(
            model="gpt-4.1",
            messages=messages,
            max_tokens=3000,
            temperature=0.3,
            extra_body={
                "data_sources": [{
                    "type": "azure_search",
                    "parameters": {
                        "endpoint": AZURE_SEARCH_ENDPOINT,
                        "index_name": AZURE_SEARCH_INDEX,
                        "semantic_configuration": "default",
                        "query_type": "vector_semantic_hybrid",
                        "in_scope": True,
                        "strictness": 3,
                        "top_n_documents": limit,
                        "authentication": {"type": "api_key", "key": AZURE_SEARCH_KEY},
                        "embedding_dependency": {
                            "type": "deployment_name",
                            "deployment_name": "text-embedding-ada-002"
                        }
                    }
                }]
            }
        )
        
        return jsonify({
            'disponible': True, 
            'respuesta': completion.choices[0].message.content, 
            'modelo': 'gpt-4.1',
            'index': AZURE_SEARCH_INDEX
        })
        
    except Exception as e:
        return jsonify({'disponible': True, 'error': f'Error RAG: {str(e)}', 'respuesta': None})


# ==================== CONFIGURACION LLM ====================

@app.route('/configuracion')
def configuracion_page():
    """Página de configuración del sistema LLM"""
    return send_from_directory('static', 'configuracion.html')


@app.route('/api/configuracion', methods=['GET'])
def get_configuracion():
    """Obtener toda la configuración LLM (con API keys mascaradas)"""
    config = get_all_config()
    # Mascarar API keys para seguridad
    for key in ['openai_api_key', 'azure_api_key', 'ollama_cloud_api_key']:
        if key in config and config[key]['valor']:
            val = config[key]['valor']
            if len(val) > 8:
                config[key]['valor_masked'] = '****' + val[-8:]
            else:
                config[key]['valor_masked'] = '****' if val else ''
    return jsonify(config)


@app.route('/api/configuracion', methods=['POST'])
def update_configuracion():
    """Actualizar configuración LLM"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos no proporcionados'}), 400

    updated = []
    for clave, valor in data.items():
        # Ignorar valores mascarados (usuario no cambió la key)
        if valor and isinstance(valor, str) and valor.startswith('****'):
            continue
        set_config(clave, valor)
        updated.append(clave)

    return jsonify({
        'success': True,
        'message': f'Configuración actualizada: {", ".join(updated)}',
        'updated': updated
    })


@app.route('/api/configuracion/test', methods=['POST'])
def test_configuracion():
    """Probar la configuración LLM actual con un prompt simple"""
    try:
        result = llamar_llm(
            prompt='Responde solo con JSON: {"status": "ok", "mensaje": "Conexion exitosa"}',
            system_message='Responde únicamente con JSON válido.',
            temperature=0.1,
            max_tokens=100
        )
        return jsonify({
            'success': True,
            'modelo': result['modelo'],
            'respuesta': result['content'][:500]
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/configuracion/ollama/modelos')
def get_ollama_modelos():
    """Listar modelos disponibles en Ollama local"""
    import requests as http_requests
    ollama_url = get_config('ollama_url', 'http://localhost:11434')
    try:
        resp = http_requests.get(f"{ollama_url.rstrip('/')}/api/tags", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            modelos = [m['name'] for m in data.get('models', [])]
            return jsonify({'success': True, 'modelos': modelos})
        return jsonify({'success': False, 'error': f'Status: {resp.status_code}'}), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Ollama no disponible. Verificar que el servidor está corriendo.'
        }), 500


if __name__ == '__main__':

    print("=" * 60)
    print("API DE CONSULTA DE NOVEDADES PGN")
    print("Decretos y Resoluciones - Decreto Ley 262 de 2000")
    print("=" * 60)
    print(f"Base de datos: {DB_PATH}")
    print(f"Servidor: http://localhost:5000")
    print()
    print("Endpoints disponibles:")
    print("  /                          - Página principal (decretos)")
    print("  /resoluciones              - Página de resoluciones")
    print("  /expediente                - 📁 Expediente Electrónico con IA")
    print("  /api/buscar                - Buscar en decretos")
    print("  /api/resoluciones/buscar   - Buscar en resoluciones")
    print("  /api/buscar/unificado      - Búsqueda combinada")
    print("  /api/expediente/buscar     - 🔍 Búsqueda multinivel (metadata/fulltext/RAG)")
    print("  /api/expediente/<codigo>   - Obtener expediente con índice")
    print("  /api/expediente/lista      - Listar expedientes")
    print("  /api/trd                   - Tabla de Retención Documental")
    print("  /api/stats                 - Estadísticas generales")
    print("  /api/stats/detallado       - Estadísticas detalladas")
    print("  /api/funcionario/<cedula>/completo - Historia completa")
    print("  /configuracion                     - Configuración LLM")
    print("=" * 60)

    # Verificar que existe la BD
    if not os.path.exists(DB_PATH):
        print(f"ERROR: No se encuentra la base de datos: {DB_PATH}")
        exit(1)

    # Inicializar tabla de configuración LLM
    init_configuracion_db()
    print("Configuración LLM inicializada")

    app.run(debug=True, port=5000, host='0.0.0.0')
