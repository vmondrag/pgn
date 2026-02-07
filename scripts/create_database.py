"""
Script para crear la base de datos SQLite para certificaciones PGN
"""
import sqlite3
import os

DB_PATH = r"C:\temp\PNG_CERTIFICADO_V3\certificaciones_pgn.db"

def create_database():
    """Crea la base de datos con el esquema definido"""
    
    # Eliminar BD existente si hay
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tabla funcionarios
    cursor.execute('''
        CREATE TABLE funcionarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cedula VARCHAR(20) UNIQUE NOT NULL,
            tratamiento VARCHAR(10),
            nombres VARCHAR(100),
            apellidos VARCHAR(100),
            nombre_completo VARCHAR(200) NOT NULL,
            lugar_expedicion_cc VARCHAR(50),
            direccion VARCHAR(200),
            telefono VARCHAR(50),
            estado VARCHAR(20) DEFAULT 'ACTIVO',
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabla cargos
    cursor.execute('''
        CREATE TABLE cargos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            funcionario_id INTEGER NOT NULL,
            cargo VARCHAR(200),
            codigo VARCHAR(20),
            grado VARCHAR(20),
            dependencia VARCHAR(200),
            sede VARCHAR(100),
            fecha_inicio DATE,
            fecha_fin DATE,
            fecha_inicio_texto VARCHAR(100),
            fecha_fin_texto VARCHAR(100),
            tipo_vinculacion VARCHAR(50),
            es_encargo BOOLEAN DEFAULT 0,
            certificacion_id INTEGER,
            confianza_extraccion VARCHAR(20) DEFAULT 'ALTA',
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (funcionario_id) REFERENCES funcionarios(id),
            FOREIGN KEY (certificacion_id) REFERENCES certificaciones(id)
        )
    ''')
    
    # Tabla certificaciones
    cursor.execute('''
        CREATE TABLE certificaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            funcionario_id INTEGER,
            archivo_origen VARCHAR(500) NOT NULL,
            ruta_completa VARCHAR(1000),
            anio_carpeta VARCHAR(10),
            tipo_certificacion VARCHAR(20),
            fecha_expedicion DATE,
            fecha_expedicion_texto VARCHAR(100),
            ciudad_expedicion VARCHAR(50) DEFAULT 'Bogotá D.C.',
            solicitante VARCHAR(300),
            destino VARCHAR(500),
            firmante VARCHAR(100),
            elaboro VARCHAR(100),
            reviso VARCHAR(100),
            numero_hr VARCHAR(20),
            tiene_licencias_no_remuneradas BOOLEAN,
            licencias_descripcion TEXT,
            anexa_funciones BOOLEAN DEFAULT 0,
            notas TEXT,
            contenido_original TEXT,
            estado_procesamiento VARCHAR(20) DEFAULT 'PROCESADO',
            metodo_extraccion VARCHAR(50),
            fecha_procesamiento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (funcionario_id) REFERENCES funcionarios(id)
        )
    ''')
    
    # Tabla para campos extraídos por LLM
    cursor.execute('''
        CREATE TABLE extracciones_llm (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            certificacion_id INTEGER NOT NULL,
            campo VARCHAR(100) NOT NULL,
            valor_extraido TEXT,
            confianza REAL,
            razonamiento TEXT,
            fecha_extraccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (certificacion_id) REFERENCES certificaciones(id)
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
    
    # Índices para búsquedas rápidas
    cursor.execute('CREATE INDEX idx_funcionarios_cedula ON funcionarios(cedula)')
    cursor.execute('CREATE INDEX idx_cargos_funcionario ON cargos(funcionario_id)')
    cursor.execute('CREATE INDEX idx_certificaciones_funcionario ON certificaciones(funcionario_id)')
    cursor.execute('CREATE INDEX idx_certificaciones_anio ON certificaciones(anio_carpeta)')
    
    conn.commit()
    conn.close()
    
    print(f"Base de datos creada exitosamente en: {DB_PATH}")
    return DB_PATH


if __name__ == "__main__":
    create_database()
