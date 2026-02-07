"""
Script para analizar estructura de bases de datos y certificaciones
para crear el plan de proyecto del Agente IA de Certificaciones
"""
import sqlite3
import os
from pathlib import Path

# Rutas
CERT_DIR = Path(r"C:\temp\PNG_CERTIFICADO_V3\Certificaciones")
MANUAL_V8_DB = Path(r"C:\temp\PNG_CERTIFICADO_V3\Manuales_Funciones\cargos_manual2024_v8.db")
MANUAL_419_DB = Path(r"C:\temp\PNG_CERTIFICADO_V3\Manuales_Funciones\Manual funciones 419-2023.db")
NOVEDADES_DB = Path(r"C:\temp\PNG_CERTIFICADO_V3\novedades_pgn.db")

def analyze_db_structure(db_path, name):
    """Analiza la estructura de una base de datos SQLite"""
    print(f"\n{'='*60}")
    print(f"BASE DE DATOS: {name}")
    print(f"Archivo: {db_path}")
    print(f"{'='*60}")
    
    if not db_path.exists():
        print("  [NO EXISTE]")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Obtener tablas
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"\nTablas ({len(tables)}):")
    
    for table in tables:
        # Contar registros
        cursor.execute(f"SELECT COUNT(*) FROM '{table}'")
        count = cursor.fetchone()[0]
        
        # Obtener columnas
        cursor.execute(f"PRAGMA table_info('{table}')")
        columns = [row[1] for row in cursor.fetchall()]
        
        print(f"\n  📋 {table} ({count} registros)")
        print(f"     Columnas: {', '.join(columns[:8])}")
        if len(columns) > 8:
            print(f"              ...y {len(columns)-8} más")
    
    conn.close()

def count_certifications_by_year():
    """Cuenta certificaciones por año"""
    print("\n" + "="*60)
    print("CERTIFICACIONES POR AÑO")
    print("="*60)
    
    years = sorted([d for d in os.listdir(CERT_DIR) if d.isdigit()])
    total = 0
    
    print(f"\n{'Año':<8} | {'Archivos':>10}")
    print("-"*25)
    
    for year in years:
        year_dir = CERT_DIR / year
        count = sum(1 for f in year_dir.rglob("*") if f.is_file())
        total += count
        print(f"{year:<8} | {count:>10}")
    
    print("-"*25)
    print(f"{'TOTAL':<8} | {total:>10}")
    
    return total

def get_sample_filenames(year, n=10):
    """Obtiene n nombres de archivo de muestra de un año"""
    year_dir = CERT_DIR / str(year)
    if not year_dir.exists():
        return []
    
    files = list(year_dir.rglob("*.docx"))[:n]
    if not files:
        files = list(year_dir.rglob("*"))[:n]
    
    return [f.name for f in files]

def analyze_filename_patterns():
    """Analiza patrones en nombres de archivos"""
    print("\n" + "="*60)
    print("PATRONES EN NOMBRES DE ARCHIVOS (10 muestras/año)")
    print("="*60)
    
    years_to_sample = ['2019', '2020', '2021', '2022', '2023', '2024']
    
    for year in years_to_sample:
        samples = get_sample_filenames(year, 10)
        if samples:
            print(f"\n📅 {year}:")
            for name in samples[:5]:
                print(f"   • {name[:60]}...")

def main():
    print("ANÁLISIS PARA PLAN DE PROYECTO - AGENTE IA CERTIFICACIONES")
    print("="*70)
    
    # 1. Contar certificaciones
    total_certs = count_certifications_by_year()
    
    # 2. Analizar patrones de nombres
    analyze_filename_patterns()
    
    # 3. Analizar estructura de BDs
    analyze_db_structure(MANUAL_V8_DB, "Manual de Funciones 2024 V8")
    analyze_db_structure(MANUAL_419_DB, "Manual de Funciones Res. 419-2023")
    analyze_db_structure(NOVEDADES_DB, "Novedades PGN")
    
    print("\n" + "="*60)
    print("ANÁLISIS COMPLETADO")
    print("="*60)

if __name__ == "__main__":
    main()
