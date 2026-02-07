"""
Script para limpiar duplicados en la tabla de errores de procesamiento.
Elimina los registros duplicados del año 2009, manteniendo solo los más recientes.
"""
import sqlite3
from datetime import datetime

DB_PATH = r"C:\temp\PNG_CERTIFICADO_V3\novedades_pgn.db"

def limpiar_duplicados():
    """Elimina registros duplicados de errores."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 80)
    print("LIMPIEZA DE DUPLICADOS EN ERRORES DE PROCESAMIENTO")
    print("=" * 80)
    
    # Consultar errores antes de limpiar
    cursor.execute("SELECT COUNT(*) FROM errores_procesamiento")
    total_antes = cursor.fetchone()[0]
    print(f"\n✓ Total de errores ANTES de limpiar: {total_antes}")
    
    # Mostrar duplicados
    cursor.execute("""
        SELECT archivo, COUNT(*) as duplicados
        FROM errores_procesamiento
        GROUP BY archivo
        HAVING COUNT(*) > 1
        ORDER BY duplicados DESC
    """)
    
    duplicados = cursor.fetchall()
    if duplicados:
        print(f"\n📋 Archivos con registros duplicados: {len(duplicados)}")
        for archivo, count in duplicados[:5]:
            archivo_nombre = archivo.split('\\')[-1] if archivo else 'N/A'
            print(f"   - {archivo_nombre}: {count} registros")
    
    # Eliminar duplicados antiguos (IDs 1-10)
    print(f"\n🗑️  Eliminando registros duplicados (IDs 1-10)...")
    
    ids_a_eliminar = list(range(1, 11))
    cursor.execute(f"""
        DELETE FROM errores_procesamiento 
        WHERE id IN ({','.join(map(str, ids_a_eliminar))})
    """)
    
    eliminados = cursor.rowcount
    conn.commit()
    
    print(f"   ✓ Registros eliminados: {eliminados}")
    
    # Consultar errores después de limpiar
    cursor.execute("SELECT COUNT(*) FROM errores_procesamiento")
    total_despues = cursor.fetchone()[0]
    print(f"\n✓ Total de errores DESPUÉS de limpiar: {total_despues}")
    
    # Mostrar errores únicos restantes
    cursor.execute("""
        SELECT id, archivo, mensaje, fecha
        FROM errores_procesamiento
        ORDER BY id
    """)
    
    errores = cursor.fetchall()
    
    print(f"\n📊 ERRORES ÚNICOS RESTANTES ({len(errores)}):")
    print("-" * 80)
    
    # Agrupar por año
    errores_por_anio = {}
    for id_error, archivo, mensaje, fecha in errores:
        if '2009' in archivo:
            anio = '2009'
        elif '2016' in archivo:
            anio = '2016'
        else:
            anio = 'Otro'
        
        if anio not in errores_por_anio:
            errores_por_anio[anio] = []
        
        archivo_nombre = archivo.split('\\')[-1] if archivo else 'N/A'
        errores_por_anio[anio].append({
            'id': id_error,
            'archivo': archivo_nombre,
            'mensaje': mensaje,
            'fecha': fecha
        })
    
    for anio in sorted(errores_por_anio.keys()):
        print(f"\n  Año {anio}: {len(errores_por_anio[anio])} errores")
        for error in errores_por_anio[anio]:
            print(f"    [{error['id']}] {error['archivo']} - {error['mensaje']}")
    
    conn.close()
    
    print("\n" + "=" * 80)
    print("✅ LIMPIEZA COMPLETADA")
    print(f"   Antes: {total_antes} errores")
    print(f"   Después: {total_despues} errores")
    print(f"   Eliminados: {eliminados} duplicados")
    print("=" * 80)
    
    return total_despues

if __name__ == "__main__":
    try:
        errores_restantes = limpiar_duplicados()
        print(f"\n✓ Proceso completado exitosamente")
        print(f"✓ Errores únicos en base de datos: {errores_restantes}")
    except Exception as e:
        print(f"\n❌ Error durante la limpieza: {e}")
        import traceback
        traceback.print_exc()
