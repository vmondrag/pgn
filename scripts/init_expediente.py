"""
Script para inicializar el esquema del Expediente Electrónico
y crear datos de prueba en novedades_pgn.db
"""
import sqlite3
import hashlib
import json
from datetime import datetime

DB_PATH = r"C:\temp\PNG_CERTIFICADO_V3\novedades_pgn.db"


def init_expediente_schema(conn):
    """Crear tablas para Expediente Electrónico"""
    cursor = conn.cursor()
    
    # TRD: Tabla de Retención Documental (Simulada)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trd_series (
            id INTEGER PRIMARY KEY,
            codigo TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            tipo_documental TEXT,
            nivel_acceso TEXT DEFAULT 'publico',
            tiempo_retencion_archivo_gestion INTEGER,
            tiempo_retencion_archivo_central INTEGER,
            disposicion_final TEXT
        )
    ''')
    
    # Expedientes Electrónicos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expedientes (
            id INTEGER PRIMARY KEY,
            codigo_expediente TEXT UNIQUE NOT NULL,
            serie_id INTEGER REFERENCES trd_series(id),
            asunto TEXT NOT NULL,
            fecha_apertura TEXT,
            fecha_cierre TEXT,
            estado TEXT DEFAULT 'abierto',
            funcionario_responsable TEXT,
            cedula_funcionario TEXT,
            nivel_acceso TEXT DEFAULT 'publico',
            hash_indice TEXT,
            metadatos_json TEXT,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Índice Electrónico
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expediente_documentos (
            id INTEGER PRIMARY KEY,
            expediente_id INTEGER REFERENCES expedientes(id),
            decreto_id INTEGER REFERENCES decretos(id),
            orden INTEGER NOT NULL,
            tipologia_documental TEXT,
            fecha_documento TEXT,
            hash_documento TEXT,
            ruta_archivo TEXT,
            ruta_extraccion_md TEXT,
            metadatos_json TEXT,
            fecha_incorporacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Crear índices
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_exp_codigo ON expedientes(codigo_expediente)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_exp_cedula ON expedientes(cedula_funcionario)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_expdoc_exp ON expediente_documentos(expediente_id)')
    
    conn.commit()
    print("✓ Tablas de Expediente Electrónico creadas")


def init_trd_data(conn):
    """Insertar series TRD de ejemplo"""
    cursor = conn.cursor()
    
    series = [
        ("100.10.01", "Decretos de Nombramiento", "Decreto", "publico", 2, 10, "conservar"),
        ("100.10.02", "Decretos de Encargo", "Decreto", "publico", 2, 5, "seleccionar"),
        ("100.10.03", "Decretos de Renuncia", "Decreto", "publico", 2, 10, "conservar"),
        ("100.10.04", "Decretos de Comisión", "Decreto", "publico", 2, 5, "seleccionar"),
        ("100.10.05", "Decretos de Traslado", "Decreto", "publico", 2, 5, "seleccionar"),
        ("100.10.06", "Decretos de Insubsistencia", "Decreto", "clasificado", 2, 20, "conservar"),
        ("100.20.01", "Resoluciones Administrativas", "Resolución", "publico", 2, 5, "seleccionar"),
        ("200.10.01", "Historia Laboral Funcionario", "Mixto", "clasificado", 80, 0, "conservar"),
    ]
    
    for serie in series:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO trd_series 
                (codigo, nombre, tipo_documental, nivel_acceso, 
                 tiempo_retencion_archivo_gestion, tiempo_retencion_archivo_central, 
                 disposicion_final)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', serie)
        except sqlite3.IntegrityError:
            pass
    
    conn.commit()
    print("✓ TRD de ejemplo insertada")


def crear_expediente_prueba(conn):
    """Crear un expediente electrónico de prueba"""
    cursor = conn.cursor()
    
    # Buscar un funcionario con múltiples decretos
    cursor.execute('''
        SELECT f.cedula, f.nombre_completo, COUNT(*) as num_decretos
        FROM funcionarios f
        JOIN novedades n ON f.id = n.funcionario_id
        WHERE f.cedula IS NOT NULL AND f.cedula != ''
        GROUP BY f.cedula
        ORDER BY num_decretos DESC
        LIMIT 1
    ''')
    
    result = cursor.fetchone()
    if not result:
        print("✗ No se encontraron funcionarios con decretos")
        return
    
    cedula, nombre, num_decretos = result
    print(f"  Funcionario: {nombre} (CC {cedula}) - {num_decretos} decretos")
    
    # Obtener serie TRD de historia laboral
    cursor.execute("SELECT id FROM trd_series WHERE codigo = '200.10.01'")
    serie_row = cursor.fetchone()
    serie_id = serie_row[0] if serie_row else None
    
    # Crear expediente
    codigo_expediente = f"EXP-HL-{cedula}"
    fecha_apertura = datetime.now().strftime("%Y-%m-%d")
    
    cursor.execute('''
        INSERT OR REPLACE INTO expedientes 
        (codigo_expediente, serie_id, asunto, fecha_apertura, estado, 
         funcionario_responsable, cedula_funcionario, nivel_acceso, metadatos_json)
        VALUES (?, ?, ?, ?, 'abierto', ?, ?, 'clasificado', ?)
    ''', (
        codigo_expediente,
        serie_id,
        f"Historia Laboral - {nombre}",
        fecha_apertura,
        nombre,
        cedula,
        json.dumps({"creado_por": "script_init", "tipo": "prueba"})
    ))
    
    expediente_id = cursor.lastrowid
    
    # Obtener decretos del funcionario
    cursor.execute('''
        SELECT DISTINCT d.id, d.numero_decreto, d.anio, d.fecha_decreto_texto,
               d.ruta_completa, n.codigo_novedad, n.tipo_novedad
        FROM decretos d
        JOIN novedades n ON d.id = n.decreto_id
        JOIN funcionarios f ON n.funcionario_id = f.id
        WHERE f.cedula = ?
        ORDER BY d.anio, d.numero_decreto
    ''', (cedula,))
    
    decretos = cursor.fetchall()
    
    # Agregar documentos al índice electrónico
    indice_hash = hashlib.sha256()
    for orden, decreto in enumerate(decretos, 1):
        decreto_id, num, anio, fecha, ruta, cod_nov, tipo_nov = decreto
        
        # Hash del documento (simulado con ruta)
        hash_doc = hashlib.md5((ruta or str(decreto_id)).encode()).hexdigest()
        indice_hash.update(hash_doc.encode())
        
        # Buscar archivo MD correspondiente
        ruta_md = None
        if ruta:
            import os
            base = os.path.basename(ruta).replace('.pdf', '.md')
            ruta_md = f"C:\\temp\\PNG_CERTIFICADO_V3\\Novedades_OUT\\output_FULL_MD\\{base}"
        
        cursor.execute('''
            INSERT INTO expediente_documentos
            (expediente_id, decreto_id, orden, tipologia_documental, 
             fecha_documento, hash_documento, ruta_archivo, ruta_extraccion_md, metadatos_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            expediente_id,
            decreto_id,
            orden,
            f"Decreto {tipo_nov}",
            fecha,
            hash_doc,
            ruta,
            ruta_md,
            json.dumps({"codigo_novedad": cod_nov, "tipo_novedad": tipo_nov})
        ))
    
    # Actualizar hash del índice
    cursor.execute('''
        UPDATE expedientes SET hash_indice = ? WHERE id = ?
    ''', (indice_hash.hexdigest(), expediente_id))
    
    conn.commit()
    print(f"✓ Expediente creado: {codigo_expediente} con {len(decretos)} documentos")
    print(f"  Hash de integridad: {indice_hash.hexdigest()[:16]}...")


def main():
    print("=" * 60)
    print("INICIALIZACIÓN EXPEDIENTE ELECTRÓNICO")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    
    try:
        init_expediente_schema(conn)
        init_trd_data(conn)
        crear_expediente_prueba(conn)
        
        print("=" * 60)
        print("✓ Inicialización completada exitosamente")
        print("=" * 60)
        
    except Exception as e:
        print(f"✗ Error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
