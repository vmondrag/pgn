"""
Reprocesamiento de Decretos Huérfanos
=====================================
Este script reprocesa los decretos que quedaron como huérfanos (sin novedades)
usando el prompt mejorado del LLM (Ollama local o Azure OpenAI).

Uso:
    python reprocess_orphans.py --anio 2014 --limit 50
    python reprocess_orphans.py --all --limit 100
    python reprocess_orphans.py --llm_azure --anio 2014 --limit 50
"""
import os
import re
import json
import sqlite3
import requests
from datetime import datetime
from typing import Dict, Optional, List

# Importar OpenAI SDK (opcional para Azure)
try:
    from openai import AzureOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# Configuración
DB_PATH = r"C:\temp\PNG_CERTIFICADO_V3\novedades_pgn.db"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gpt-oss:20b-cloud"

# Configuración Azure OpenAI
AZURE_ENDPOINT = "https://iacertificaciones.cognitiveservices.azure.com/"
AZURE_API_KEY = os.environ.get("AZURE_API_KEY", "")
AZURE_API_VERSION = "2024-12-01-preview"
AZURE_MODEL = "gpt-5-mini"
USE_AZURE = False  # Se activa con --llm_azure


def get_orphan_decretos(conn: sqlite3.Connection, anio: int = None, limit: int = 50) -> List[Dict]:
    """Obtiene decretos huérfanos (sin novedades)"""
    cursor = conn.cursor()
    
    query = '''
        SELECT d.id, d.numero_decreto, d.anio, d.contenido_texto, d.archivo_origen
        FROM decretos d
        WHERE NOT EXISTS (SELECT 1 FROM novedades n WHERE n.decreto_id = d.id)
    '''
    params = []
    
    if anio:
        query += ' AND d.anio = ?'
        params.append(anio)
    
    query += ' ORDER BY d.anio DESC, d.numero_decreto LIMIT ?'
    params.append(limit)
    
    cursor.execute(query, params)
    
    return [
        {
            'id': row[0],
            'numero_decreto': row[1],
            'anio': row[2],
            'contenido_texto': row[3],
            'archivo_origen': row[4]
        }
        for row in cursor.fetchall()
    ]


def extract_with_llm_improved(text: str, numero: str, anio: int) -> Dict:
    """Usa LLM con prompt V3 mejorado para extraer datos"""
    
    prompt = f"""Eres un experto legal en decretos de la Procuraduria General de la Nacion de Colombia.

=== INFORMACION DEL DECRETO ===
- Numero: {numero}
- Anio: {anio}

=== TEXTO OCR (puede tener errores) ===
{text[:5000]}

=== ERRORES OCR COMUNES ===
- "GENERALDELANACION" = "GENERAL DE LA NACION"
- "25MAR2014" = "25 MAR 2014"
- "27AG02009" = "27 AGO 2009"
- "No.43.168.876" = cedula 43168876
- "Codigo50FGrado06" = "Codigo 5OF Grado 06"

=== TIPOS DE DECRETO ===

1. NOMBRAMIENTO (N): "Nombrar en Provisionalidad"
2. ENCARGO (E): "Encargar, a [NOMBRE], [CARGO_ACTUAL], del cargo de [CARGO_ENCARGADO]"
   → cargo_actual = cargo que YA tiene
   → cargo = CARGO_ENCARGADO (el temporal)
3. RENUNCIA (R): "Aceptar la renuncia"
4. ASIGNACION (ASIG): "Asignar funciones" (sin persona reemplazada)
5. PRORROGA (PROR): "Prorrogar el encargo/provisionalidad"
6. MODIFICACION DECRETO (MD): "Revocar/Aclarar el Decreto No.X" (sin funcionarios)
7. COMISION (C): "Comisionar"
8. AD HONOREM (NAADH): "auxiliar juridico ad-honorem"
9. REVOCACION NOMBRAMIENTO (RN): "Revocar el nombramiento de [NOMBRE]"
10. INSUBSISTENCIA (INSUB): "Declarar insubsistente"

=== REGLA: DOS PERSONAS ===
- PERSONA CON CEDULA → funcionario (VA en array)
- PERSONA SIN CEDULA (despues de "en el cargo de") → persona_reemplazada

=== RESPUESTA JSON ===
{{
    "razonamiento": "PASO 1: Corregi OCR. PASO 2: Palabra clave indica [TIPO]. PASO 3: Funcionario con cedula. PASO 4: Persona reemplazada sin cedula.",
    "codigo_novedad": "N/E/R/ASIG/PROR/MD/C/NAADH/RN/INSUB",
    "tipo_novedad": "Nombramiento/Encargo/Renuncia/Asignacion/Prorroga/Modificacion",
    "funcionarios": [
        {{
            "cedula": "numero SIN puntos",
            "nombre_completo": "NOMBRE APELLIDO",
            "cargo_actual": "solo en encargos",
            "cargo": "cargo nuevo o encargado",
            "dependencia": "dependencia destino"
        }}
    ],
    "persona_reemplazada": "nombre sin cedula",
    "es_modificacion_decreto": false,
    "resumen": "Decreto {numero}-{anio}: [Tipo] de [NOMBRE]"
}}

JSON:"""

    # Llamar al LLM (Azure OpenAI o Ollama local)
    resp_text = None
    
    if USE_AZURE:
        if not HAS_OPENAI:
            print("ERROR: SDK OpenAI no instalado")
            return {'codigo_novedad': 'PENDIENTE_REVISION', 'funcionarios': [], 'error': 'SDK OpenAI no instalado'}
        
        try:
            client = AzureOpenAI(
                api_version=AZURE_API_VERSION,
                azure_endpoint=AZURE_ENDPOINT,
                api_key=AZURE_API_KEY,
            )
            
            response = client.chat.completions.create(
                model=AZURE_MODEL,
                messages=[
                    {"role": "system", "content": "Eres un experto en analisis de decretos de la PGN Colombia."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=2000
            )
            resp_text = response.choices[0].message.content
        except Exception as e:
            print(f"Error Azure OpenAI: {e}")
    else:
        try:
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 2000}
            }
            response = requests.post(OLLAMA_URL, json=payload, timeout=120)
            if response.status_code == 200:
                resp_text = response.json().get('response', '')
        except Exception as e:
            print(f"Error Ollama: {e}")
    
    if resp_text:
        match = re.search(r'\{[\s\S]*\}', resp_text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    
    return {
        'codigo_novedad': 'PENDIENTE_REVISION',
        'funcionarios': [],
        'error': 'No se pudo extraer con LLM'
    }


def update_decreto_with_novedades(conn: sqlite3.Connection, decreto: Dict, extracted: Dict) -> bool:
    """Actualiza el decreto con las novedades extraidas"""
    cursor = conn.cursor()
    decreto_id = decreto['id']
    
    try:
        funcionarios_list = extracted.get('funcionarios', [])
        
        if funcionarios_list:
            for func in funcionarios_list:
                cedula = func.get('cedula')
                cedula_clean = re.sub(r'[^\d]', '', str(cedula)) if cedula else None
                
                # Buscar o crear funcionario
                func_id = None
                if cedula_clean:
                    cursor.execute('SELECT id FROM funcionarios WHERE cedula = ?', (cedula_clean,))
                    row = cursor.fetchone()
                    if row:
                        func_id = row[0]
                    else:
                        cursor.execute('''
                            INSERT INTO funcionarios (cedula, nombre_completo)
                            VALUES (?, ?)
                        ''', (cedula_clean, func.get('nombre_completo')))
                        func_id = cursor.lastrowid
                
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
            # Sin funcionarios - crear novedad placeholder
            cursor.execute('''
                INSERT INTO novedades (
                    decreto_id, funcionario_id, codigo_novedad, tipo_novedad,
                    observaciones, fecha_creacion
                ) VALUES (?, NULL, ?, ?, ?, ?)
            ''', (
                decreto_id,
                extracted.get('codigo_novedad', 'PENDIENTE_REVISION'),
                extracted.get('tipo_novedad'),
                extracted.get('resumen') or 'Reprocesado - revisar manualmente',
                datetime.now().isoformat()
            ))
        
        # Actualizar razonamiento del decreto
        cursor.execute('''
            UPDATE decretos SET razonamiento_llm = ? WHERE id = ?
        ''', (extracted.get('razonamiento'), decreto_id))
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"Error guardando: {e}")
        conn.rollback()
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Reprocesar decretos huerfanos')
    parser.add_argument('--anio', type=int, help='Filtrar por anio')
    parser.add_argument('--limit', type=int, default=10000, help='Limite de decretos (default: todos)')
    parser.add_argument('--all', action='store_true', help='Procesar todos los anios')
    parser.add_argument('--llm', default='gpt-oss:20b-cloud', help='Modelo LLM Ollama')
    parser.add_argument('--llm_azure', action='store_true', help='Usar Azure OpenAI (gpt-5-mini) en lugar de Ollama')
    parser.add_argument('--dry-run', action='store_true', help='Solo mostrar, no guardar')
    args = parser.parse_args()
    
    global OLLAMA_MODEL, USE_AZURE
    OLLAMA_MODEL = args.llm
    USE_AZURE = args.llm_azure
    
    # Verificar dependencias para Azure
    if USE_AZURE and not HAS_OPENAI:
        print("ERROR: Para usar Azure OpenAI, instale el SDK: pip install openai")
        return
    
    print("=" * 60)
    print("REPROCESAMIENTO DE DECRETOS HUERFANOS")
    print("=" * 60)
    print(f"Base de datos: {DB_PATH}")
    if USE_AZURE:
        print(f"LLM: Azure OpenAI ({AZURE_MODEL})")
    else:
        print(f"LLM: Ollama local ({OLLAMA_MODEL})")
    print(f"Limite: {args.limit}")
    print(f"Anio: {args.anio if args.anio else 'Todos'}")
    print(f"Dry run: {args.dry_run}")
    print()
    
    conn = sqlite3.connect(DB_PATH)
    
    # Obtener huerfanos
    orphans = get_orphan_decretos(conn, args.anio, args.limit)
    print(f"Huerfanos encontrados: {len(orphans)}")
    print()
    
    if not orphans:
        print("No hay huerfanos para procesar.")
        conn.close()
        return
    
    # Procesar
    success = 0
    failed = 0
    
    for i, decreto in enumerate(orphans):
        print(f"[{i+1}/{len(orphans)}] Decreto {decreto['numero_decreto']}-{decreto['anio']}...", end=" ", flush=True)
        
        if not decreto['contenido_texto'] or len(decreto['contenido_texto']) < 50:
            print("SKIP (sin texto)")
            continue
        
        # Extraer con LLM
        extracted = extract_with_llm_improved(
            decreto['contenido_texto'],
            decreto['numero_decreto'],
            decreto['anio']
        )
        
        codigo = extracted.get('codigo_novedad', '?')
        funcs = extracted.get('funcionarios', [])
        
        if args.dry_run:
            print(f"[DRY] {codigo} - {len(funcs)} funcionarios")
            if funcs:
                for f in funcs:
                    print(f"       -> {f.get('nombre_completo', 'N/A')} ({f.get('cedula', 'N/A')})")
        else:
            # Guardar
            if update_decreto_with_novedades(conn, decreto, extracted):
                print(f"OK ({codigo}, {len(funcs)} func)")
                success += 1
            else:
                print("ERROR")
                failed += 1
    
    conn.close()
    
    print()
    print("=" * 60)
    print("RESULTADO")
    print("=" * 60)
    print(f"Procesados: {len(orphans)}")
    print(f"Exitosos: {success}")
    print(f"Fallidos: {failed}")


if __name__ == "__main__":
    main()
