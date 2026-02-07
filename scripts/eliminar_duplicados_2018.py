"""
Script para ELIMINAR archivos duplicados del 2018 con sufijo (1).pdf
IMPORTANTE: Este script eliminará archivos permanentemente.

Características de seguridad:
- Verifica que existe el archivo original
- Compara tamaños antes de eliminar
- Genera log de archivos eliminados
- Opción de modo DRY-RUN para prueba
"""
import os
import shutil
from pathlib import Path
from datetime import datetime

DECRETOS_2018 = Path(r"C:\temp\PNG_CERTIFICADO_V3\Decretos\2018")
LOG_FILE = Path(r"C:\temp\PNG_CERTIFICADO_V3\log_eliminacion_duplicados_2018.md")
BACKUP_DIR = Path(r"C:\temp\PNG_CERTIFICADO_V3\_backup_duplicados_2018")

# Configuración
DRY_RUN = False  # Cambiar a False para eliminar realmente
CREATE_BACKUP = False  # Cambiar a True si quieres backup antes de eliminar

def eliminar_duplicados():
    """Elimina archivos duplicados con (1).pdf"""
    
    print("=" * 100)
    print("ELIMINACIÓN DE ARCHIVOS DUPLICADOS 2018")
    print("=" * 100)
    
    if DRY_RUN:
        print("\n⚠️  MODO DRY-RUN: No se eliminarán archivos realmente")
    else:
        print("\n🔴 MODO REAL: Los archivos serán ELIMINADOS")
    
    if CREATE_BACKUP and not DRY_RUN:
        print(f"📦 Backup habilitado: {BACKUP_DIR}")
        BACKUP_DIR.mkdir(exist_ok=True)
    
    # Buscar archivos duplicados
    archivos_con_1 = sorted(DECRETOS_2018.glob("*(1).pdf"))
    
    print(f"\nTotal de archivos con (1): {len(archivos_con_1)}")
    print("\nProcesando...\n")
    
    eliminados = []
    omitidos = []
    errores = []
    
    for i, archivo_dup in enumerate(archivos_con_1, 1):
        # Obtener nombre del original
        nombre_original = archivo_dup.name.replace(" (1)", "")
        archivo_original = DECRETOS_2018 / nombre_original
        
        # Verificar si existe el original
        if not archivo_original.exists():
            omitidos.append({
                'archivo': archivo_dup.name,
                'razon': 'Original no existe'
            })
            print(f"[{i}/{len(archivos_con_1)}] ⚠️  OMITIDO: {archivo_dup.name} - Original no existe")
            continue
        
        # Comparar tamaños
        tamano_dup = archivo_dup.stat().st_size
        tamano_orig = archivo_original.stat().st_size
        
        if tamano_dup != tamano_orig:
            omitidos.append({
                'archivo': archivo_dup.name,
                'razon': f'Tamaños diferentes: {tamano_dup} vs {tamano_orig}'
            })
            print(f"[{i}/{len(archivos_con_1)}] ⚠️  OMITIDO: {archivo_dup.name} - Tamaños diferentes")
            continue
        
        # Crear backup si está habilitado
        if CREATE_BACKUP and not DRY_RUN:
            shutil.copy2(archivo_dup, BACKUP_DIR / archivo_dup.name)
        
        # Eliminar archivo
        if not DRY_RUN:
            try:
                archivo_dup.unlink()
                eliminados.append({
                    'archivo': archivo_dup.name,
                    'original': archivo_original.name,
                    'tamano': tamano_dup
                })
                if i % 50 == 0:  # Mostrar progreso cada 50
                    print(f"[{i}/{len(archivos_con_1)}] ✓ Eliminados: {len(eliminados)}")
            except Exception as e:
                errores.append({
                    'archivo': archivo_dup.name,
                    'error': str(e)
                })
                print(f"[{i}/{len(archivos_con_1)}] ❌ ERROR: {archivo_dup.name} - {e}")
        else:
            eliminados.append({
                'archivo': archivo_dup.name,
                'original': archivo_original.name,
                'tamano': tamano_dup
            })
            if i % 50 == 0:
                print(f"[{i}/{len(archivos_con_1)}] ✓ Procesados: {len(eliminados)} (DRY-RUN)")
    
    # Resultados
    print("\n" + "=" * 100)
    print("RESULTADOS")
    print("=" * 100)
    print(f"\nTotal procesados: {len(archivos_con_1)}")
    print(f"  ✓ Eliminados: {len(eliminados)}")
    print(f"  ⚠️  Omitidos: {len(omitidos)}")
    print(f"  ❌ Errores: {len(errores)}")
    
    if CREATE_BACKUP and not DRY_RUN:
        print(f"\n📦 Backup creado en: {BACKUP_DIR}")
    
    # Generar log
    generar_log(eliminados, omitidos, errores)
    
    print(f"\n📄 Log generado: {LOG_FILE}")
    print("\n" + "=" * 100)
    
    return len(eliminados), len(omitidos), len(errores)


def generar_log(eliminados, omitidos, errores):
    """Genera log detallado de la operación."""
    
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write("# Log de Eliminación de Archivos Duplicados 2018\n\n")
        f.write(f"**Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Directorio:** {DECRETOS_2018}\n")
        f.write(f"**Modo:** {'DRY-RUN (simulación)' if DRY_RUN else 'REAL (eliminación)'}\n\n")
        
        f.write("---\n\n")
        
        # Estadísticas
        f.write("## Estadísticas\n\n")
        f.write(f"| Categoría | Cantidad |\n")
        f.write(f"|-----------|----------|\n")
        f.write(f"| Eliminados | {len(eliminados)} |\n")
        f.write(f"| Omitidos | {len(omitidos)} |\n")
        f.write(f"| Errores | {len(errores)} |\n")
        f.write(f"| **Total** | **{len(eliminados) + len(omitidos) + len(errores)}** |\n\n")
        
        # Archivos eliminados
        if eliminados:
            f.write("## ✓ Archivos Eliminados\n\n")
            f.write(f"Total: {len(eliminados)}\n\n")
            f.write("| # | Archivo Eliminado | Archivo Original | Tamaño (bytes) |\n")
            f.write("|---|-------------------|------------------|----------------|\n")
            for i, e in enumerate(eliminados[:100], 1):  # Primeros 100
                f.write(f"| {i} | {e['archivo']} | {e['original']} | {e['tamano']:,} |\n")
            if len(eliminados) > 100:
                f.write(f"\n*... y {len(eliminados) - 100} más*\n")
            f.write("\n")
        
        # Archivos omitidos
        if omitidos:
            f.write("## ⚠️ Archivos Omitidos\n\n")
            f.write(f"Total: {len(omitidos)}\n\n")
            for i, o in enumerate(omitidos, 1):
                f.write(f"{i}. **{o['archivo']}**\n")
                f.write(f"   - Razón: {o['razon']}\n\n")
        
        # Errores
        if errores:
            f.write("## ❌ Errores\n\n")
            f.write(f"Total: {len(errores)}\n\n")
            for i, e in enumerate(errores, 1):
                f.write(f"{i}. **{e['archivo']}**\n")
                f.write(f"   - Error: {e['error']}\n\n")


if __name__ == "__main__":
    import sys
    
    # Verificar confirmación
    if not DRY_RUN:
        print("\n" + "=" * 100)
        print("⚠️  ADVERTENCIA: Este script ELIMINARÁ archivos permanentemente")
        print("=" * 100)
        print(f"\nDirectorio: {DECRETOS_2018}")
        print(f"Patrón: *(1).pdf")
        print(f"\n¿Estás seguro de que deseas continuar? (escribe 'SI' para confirmar)")
        
        # Si se ejecuta desde línea de comandos
        if '--confirm' not in sys.argv:
            confirmacion = input("\nConfirmación: ")
            if confirmacion != "SI":
                print("\n❌ Operación cancelada")
                sys.exit(0)
    
    eliminados, omitidos, errores = eliminar_duplicados()
    
    print(f"\n✓ Proceso completado")
    print(f"   Eliminados: {eliminados}")
    print(f"   Omitidos: {omitidos}")
    print(f"   Errores: {errores}")
