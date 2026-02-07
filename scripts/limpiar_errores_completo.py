"""
Script mejorado para limpiar TODOS los duplicados y errores obsoletos.
Elimina registros de archivos que YA fueron procesados exitosamente.
"""
import sqlite3
from pathlib import Path

DB_PATH = r"C:\temp\PNG_CERTIFICADO_V3\novedades_pgn.db"
OUTPUT_DIR = Path(r"C:\temp\PNG_CERTIFICADO_V3")

def verificar_archivo_procesado(archivo):
    """Verifica si un archivo ya tiene output .graphrag.json"""
    base_name = Path(archivo).stem  # Sin extensión
    
    # Determinar directorio de output según el año
    if '2009' in archivo:
        output_dir = OUTPUT_DIR / "output_2009_hybrid" / "graphrag"
    elif '2016' in archivo:
        output_dir = OUTPUT_DIR / "output_2016_hybrid" / "graphrag"
    else:
        return False
    
    # Buscar archivo .graphrag.json
    archivo_json = output_dir / f"{base_name}.graphrag.json"
    return archivo_json.exists()


def limpiar_errores_obsoletos():
    """Elimina errores de archivos ya procesados y duplicados."""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 80)
    print("LIMPIEZA COMPLETA DE ERRORES OBSOLETOS")
    print("=" * 80)
    
    # Consultar todos los errores
    cursor.execute("""
        SELECT id, archivo, tipo_error, mensaje_error, fecha_error
        FROM errores_procesamiento
        ORDER BY id
    """)
    
    errores = cursor.fetchall()
    total_antes = len(errores)
    
    print(f"\nTotal de errores en BD: {total_antes}\n")
    
    ids_a_eliminar = []
    archivos_procesados = []
    archivos_persistentes = []
    
    # Analizar cada error
    print("Analizando errores...")
    print("-" * 80)
    
    for id_error, archivo, tipo, mensaje, fecha in errores:
        archivo_nombre = archivo.split('\\')[-1] if archivo else 'N/A'
        
        # Verificar si el archivo ya está procesado
        esta_procesado = verificar_archivo_procesado(archivo)
        
        if esta_procesado:
            ids_a_eliminar.append(id_error)
            archivos_procesados.append(archivo_nombre)
            print(f"  [{id_error}] ✓ {archivo_nombre} - YA PROCESADO -> ELIMINAR")
        else:
            archivos_persistentes.append({
                'id': id_error,
                'archivo': archivo_nombre,
                'mensaje': mensaje,
                'fecha': fecha
            })
            print(f"  [{id_error}] ✗ {archivo_nombre} - AÚN CON ERROR -> MANTENER")
    
    print("\n" + "=" * 80)
    print("RESUMEN DE LIMPIEZA")
    print("=" * 80)
    
    print(f"\nErrores a eliminar (archivos ya procesados): {len(ids_a_eliminar)}")
    print(f"Errores a mantener (archivos aún con problema): {len(archivos_persistentes)}")
    
    if ids_a_eliminar:
        print(f"\nEliminando errores obsoletos...")
        
        # Eliminar en bloques de 100 IDs
        for i in range(0, len(ids_a_eliminar), 100):
            bloque = ids_a_eliminar[i:i+100]
            placeholders = ','.join('?' * len(bloque))
            cursor.execute(f"DELETE FROM errores_procesamiento WHERE id IN ({placeholders})", bloque)
        
        conn.commit()
        eliminados = cursor.rowcount
        print(f"  ✓ Registros eliminados: {eliminados}")
    
    # Verificar total final
    cursor.execute("SELECT COUNT(*) FROM errores_procesamiento")
    total_despues = cursor.fetchone()[0]
    
    print(f"\n{'=' * 80}")
    print(f"Errores ANTES: {total_antes}")
    print(f"Errores DESPUÉS: {total_despues}")
    print(f"Errores eliminados: {len(ids_a_eliminar)}")
    print(f"{'=' * 80}")
    
    if archivos_persistentes:
        print(f"\n⚠️  ERRORES PERSISTENTES ({len(archivos_persistentes)}):")
        print("-" * 80)
        for err in archivos_persistentes:
            print(f"  [{err['id']}] {err['archivo']}")
            print(f"      Error: {err['mensaje']}")
            print(f"      Fecha: {err['fecha']}")
    
    conn.close()
    
    return total_despues, archivos_persistentes


if __name__ == "__main__":
    try:
        total_final, persistentes = limpiar_errores_obsoletos()
        
        print(f"\n{'=' * 80}")
        print("✅ LIMPIEZA COMPLETADA")
        print(f"{'=' * 80}")
        print(f"\nErrores finales en BD: {total_final}")
        print(f"Archivos únicos con error: {len(persistentes)}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
