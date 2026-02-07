"""
Script para reprocesar archivos que tuvieron errores.
Extrae los archivos con error de la BD e intenta procesarlos nuevamente.
"""
import sqlite3
import os
import sys

# Agregar directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extract_decretos import (
    DB_PATH, extract_pdf_text, extract_novedad_with_llm,
    get_or_create_funcionario, save_decreto, save_novedad, save_error
)

def get_error_files():
    """Obtiene la lista de archivos con error"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT archivo FROM errores_procesamiento ORDER BY archivo')
    files = [row[0] for row in cursor.fetchall()]
    conn.close()
    return files

def clear_previous_errors():
    """Limpia errores anteriores antes de reprocesar"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Contar errores actuales
    cursor.execute('SELECT COUNT(*) FROM errores_procesamiento')
    count = cursor.fetchone()[0]
    
    # Limpiar errores
    cursor.execute('DELETE FROM errores_procesamiento')
    conn.commit()
    conn.close()
    
    return count

def reprocess_file(filepath: str) -> dict:
    """Reprocesa un archivo individual y retorna el resultado"""
    result = {
        'archivo': os.path.basename(filepath),
        'ruta': filepath,
        'exito': False,
        'funcionarios_extraidos': 0,
        'error': None
    }
    
    if not os.path.exists(filepath):
        result['error'] = f"Archivo no existe: {filepath}"
        return result
    
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # 1. Extraer texto
        text, method = extract_pdf_text(filepath)
        
        if not text or method.startswith('ERROR'):
            result['error'] = f"Error extracción: {method}"
            save_error(conn, filepath, 'EXTRACCION', method)
            conn.close()
            return result
        
        filename = os.path.basename(filepath)
        
        # 2. Analizar con LLM
        extracted = extract_novedad_with_llm(text, filename)
        
        # 3. Verificar si el decreto ya existe
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM decretos WHERE ruta_completa = ?', (filepath,))
        existing = cursor.fetchone()
        
        if existing:
            # Ya existe, actualizar
            decreto_id = existing[0]
            # Eliminar novedades anteriores para este decreto
            cursor.execute('DELETE FROM novedades WHERE decreto_id = ?', (decreto_id,))
            conn.commit()
        else:
            # Nuevo decreto
            decreto_id = save_decreto(conn, extracted, filepath, text, method)
        
        # 4. Procesar funcionarios y novedades
        funcionarios = extracted.get('funcionarios', [])
        novedad = extracted.get('novedad', {})
        
        result['funcionarios_extraidos'] = len(funcionarios)
        
        if funcionarios:
            for func_data in funcionarios:
                func_id = get_or_create_funcionario(conn, func_data)
                if func_id:
                    save_novedad(conn, decreto_id, func_id, novedad, func_data)
        else:
            save_novedad(conn, decreto_id, None, novedad, None)
        
        result['exito'] = True
        
    except Exception as e:
        result['error'] = str(e)
        save_error(conn, filepath, 'EXCEPCION', str(e))
    
    conn.close()
    return result

def main():
    print("=" * 70)
    print("REPROCESAMIENTO DE ARCHIVOS CON ERRORES")
    print("=" * 70)
    
    # Obtener archivos con error
    error_files = get_error_files()
    print(f"\nArchivos con errores anteriores: {len(error_files)}")
    
    if not error_files:
        print("No hay archivos con errores para reprocesar.")
        return
    
    # Limpiar errores anteriores
    cleared = clear_previous_errors()
    print(f"Errores anteriores limpiados: {cleared}")
    
    # Reprocesar cada archivo
    print("\n" + "-" * 70)
    print("REPROCESANDO ARCHIVOS...")
    print("-" * 70)
    
    exitosos = 0
    fallidos = 0
    resultados = []
    
    for i, filepath in enumerate(error_files, 1):
        nombre = os.path.basename(filepath)
        print(f"\n[{i}/{len(error_files)}] {nombre[:60]}...")
        
        result = reprocess_file(filepath)
        resultados.append(result)
        
        if result['exito']:
            exitosos += 1
            print(f"   ✓ ÉXITO - {result['funcionarios_extraidos']} funcionario(s) extraídos")
        else:
            fallidos += 1
            print(f"   ✗ ERROR: {result['error'][:60]}...")
    
    # Resumen final
    print("\n" + "=" * 70)
    print("RESUMEN DE REPROCESAMIENTO")
    print("=" * 70)
    print(f"Total archivos procesados: {len(error_files)}")
    print(f"Exitosos: {exitosos} ({100*exitosos/len(error_files):.1f}%)")
    print(f"Fallidos: {fallidos} ({100*fallidos/len(error_files):.1f}%)")
    
    # Mostrar archivos fallidos
    if fallidos > 0:
        print("\n" + "-" * 70)
        print("ARCHIVOS QUE AÚN FALLAN:")
        print("-" * 70)
        for r in resultados:
            if not r['exito']:
                print(f"\n  Archivo: {r['archivo']}")
                print(f"  Error: {r['error']}")
    
    # Verificar nuevos errores en BD
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT tipo_error, COUNT(*) FROM errores_procesamiento GROUP BY tipo_error')
    new_errors = cursor.fetchall()
    conn.close()
    
    if new_errors:
        print("\n" + "-" * 70)
        print("NUEVOS ERRORES EN BD:")
        print("-" * 70)
        for tipo, count in new_errors:
            print(f"  {tipo}: {count}")

if __name__ == '__main__':
    main()
