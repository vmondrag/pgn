"""
Script para crear la base de datos SQLite para novedades de decretos PGN
"""
import sqlite3
import os

DB_PATH = r"C:\temp\PNG_CERTIFICADO_V3\novedades_pgn.db"

def create_database():
    """Crea la base de datos con el esquema para novedades de decretos"""
    
    # Eliminar BD existente si hay
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tabla funcionarios
    cursor.execute('''
        CREATE TABLE funcionarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cedula VARCHAR(20) UNIQUE,
            tipo_identificacion VARCHAR(10) DEFAULT 'CC',
            nombres VARCHAR(100),
            apellidos VARCHAR(100),
            nombre_completo VARCHAR(200),
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabla decretos
    cursor.execute('''
        CREATE TABLE decretos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_decreto VARCHAR(20),
            fecha_decreto DATE,
            fecha_decreto_texto VARCHAR(100),
            anio INTEGER,
            dia_decreto INTEGER,
            mes_decreto INTEGER,
            anio_decreto INTEGER,
            archivo_origen VARCHAR(500) NOT NULL,
            ruta_completa VARCHAR(1000),
            tipo_extraccion VARCHAR(20),
            contenido_texto TEXT,
            tiene_multiples_funcionarios BOOLEAN DEFAULT 0,
            estado_procesamiento VARCHAR(20) DEFAULT 'PROCESADO',
            fecha_procesamiento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabla novedades
    cursor.execute('''
        CREATE TABLE novedades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            decreto_id INTEGER NOT NULL,
            funcionario_id INTEGER,
            codigo_novedad VARCHAR(10),
            tipo_novedad VARCHAR(100),
            descripcion_novedad TEXT,
            cargo_actual VARCHAR(200),
            cargo_nuevo VARCHAR(200),
            codigo_cargo VARCHAR(20),
            grado_cargo VARCHAR(20),
            dependencia VARCHAR(300),
            sede VARCHAR(100),
            fecha_inicio DATE,
            fecha_inicio_texto VARCHAR(100),
            fecha_fin DATE,
            fecha_fin_texto VARCHAR(100),
            es_provisional BOOLEAN DEFAULT 0,
            es_encargo BOOLEAN DEFAULT 0,
            observaciones TEXT,
            confianza_extraccion VARCHAR(20) DEFAULT 'LLM',
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (decreto_id) REFERENCES decretos(id),
            FOREIGN KEY (funcionario_id) REFERENCES funcionarios(id)
        )
    ''')
    
    # Tabla de errores de procesamiento
    cursor.execute('''
        CREATE TABLE errores_procesamiento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            archivo VARCHAR(500) NOT NULL,
            tipo_error VARCHAR(100),
            mensaje_error TEXT,
            fecha_error TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabla para mapeo de códigos de novedad
    cursor.execute('''
        CREATE TABLE codigos_novedad (
            codigo VARCHAR(10) PRIMARY KEY,
            descripcion VARCHAR(200),
            tipo_general VARCHAR(50)
        )
    ''')
    
    # Tabla para aprendizaje continuo del LLM
    cursor.execute('''
        CREATE TABLE ejemplos_aprendizaje (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_novedad VARCHAR(10) NOT NULL,
            texto_ejemplo TEXT NOT NULL,
            respuesta_llm TEXT,
            razonamiento TEXT,
            nombre_archivo VARCHAR(500),
            confianza REAL DEFAULT 1.0,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (codigo_novedad) REFERENCES codigos_novedad(codigo)
        )
    ''')
    
    # Insertar códigos conocidos
    codigos = [
        ('N', 'Nombramiento', 'INGRESO'),
        ('R', 'Renuncia/Retiro', 'RETIRO'),
        ('REU', 'Renuncia Encargo', 'RETIRO'),
        ('E', 'Encargo', 'MOVIMIENTO'),
        ('ASIG', 'Asignación', 'MOVIMIENTO'),
        ('C', 'Comisión', 'MOVIMIENTO'),
        ('RN', 'Revocatoria Nombramiento', 'RETIRO'),
        ('VADH', 'Vacaciones Ad Honorem', 'LICENCIA'),
        ('AC', 'Aceptación Comisión', 'MOVIMIENTO'),
        ('NAADH', 'Nombramiento Ad Honorem', 'INGRESO'),
        ('RADH', 'Renuncia Ad Honorem', 'RETIRO'),
        ('TP', 'Traslado Provisional', 'MOVIMIENTO'),
        ('AD', 'Ad Honorem', 'ESPECIAL'),
        ('RFZ', 'Retiro Forzoso', 'RETIRO'),
        ('TDB', 'Traslado Definitivo', 'MOVIMIENTO'),
        ('REVC', 'Revocatoria Comisión', 'MOVIMIENTO'),
        ('RF', 'Retiro Forzoso', 'RETIRO'),
        ('MD', 'Modificación Decreto', 'ESPECIAL'),
        ('REVE', 'Revocatoria Encargo', 'MOVIMIENTO'),
        ('TRAS', 'Traslado', 'MOVIMIENTO'),
        ('RE', 'Reintegro', 'INGRESO'),
        ('RPV', 'Renuncia Provisional', 'RETIRO'),
        ('INS', 'Insubsistencia', 'RETIRO'),
        ('INSUB', 'Insubsistencia', 'RETIRO'),
        ('REUADH', 'Renuncia Encargo Ad Honorem', 'RETIRO'),
        ('TE', 'Traslado Encargo', 'MOVIMIENTO'),
        ('RFLL', 'Retiro Forzoso Ley Lleras', 'RETIRO'),
    ]
    
    cursor.executemany(
        'INSERT OR IGNORE INTO codigos_novedad (codigo, descripcion, tipo_general) VALUES (?, ?, ?)',
        codigos
    )
    
    # Índices para búsquedas rápidas
    cursor.execute('CREATE INDEX idx_funcionarios_cedula ON funcionarios(cedula)')
    cursor.execute('CREATE INDEX idx_funcionarios_nombre ON funcionarios(nombre_completo)')
    cursor.execute('CREATE INDEX idx_novedades_funcionario ON novedades(funcionario_id)')
    cursor.execute('CREATE INDEX idx_novedades_decreto ON novedades(decreto_id)')
    cursor.execute('CREATE INDEX idx_novedades_codigo ON novedades(codigo_novedad)')
    cursor.execute('CREATE INDEX idx_decretos_numero ON decretos(numero_decreto)')
    cursor.execute('CREATE INDEX idx_decretos_anio ON decretos(anio)')
    
    conn.commit()
    conn.close()
    
    print(f"Base de datos creada exitosamente en: {DB_PATH}")
    return DB_PATH


if __name__ == "__main__":
    create_database()
