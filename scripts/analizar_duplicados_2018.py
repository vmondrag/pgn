"""
Script para analizar archivos duplicados del 2018 y mostrar ejemplos.
Compara archivos con patrón (1).pdf vs archivo original.
"""
import os
from pathlib import Path

DECRETOS_2018 = Path(r"C:\temp\PNG_CERTIFICADO_V3\Decretos\2018")

# Buscar archivos duplicados
duplicados = []
archivos_con_1 = list(DECRETOS_2018.glob("*(1).pdf"))

print("=" * 100)
print("ANÁLISIS DE ARCHIVOS DUPLICADOS DEL 2018")
print("=" * 100)
print(f"\nTotal de archivos con (1): {len(archivos_con_1)}\n")

for archivo_dup in archivos_con_1[:20]:  # Primeros 20
    # Obtener nombre del original (sin el " (1)")
    nombre_original = archivo_dup.name.replace(" (1)", "")
    archivo_original = DECRETOS_2018 / nombre_original
    
    # Verificar si existe el original
    if archivo_original.exists():
        tamano_dup = archivo_dup.stat().st_size
        tamano_orig = archivo_original.stat().st_size
        
        son_iguales = tamano_dup == tamano_orig
        diferencia = abs(tamano_dup - tamano_orig)
        
        duplicados.append({
            'duplicado': archivo_dup.name,
            'original': archivo_original.name,
            'tamano_dup': tamano_dup,
            'tamano_orig': tamano_orig,
            'iguales': son_iguales,
            'diferencia': diferencia
        })

print(f"{'#':>3} {'DUPLICADO':50} {'ORIGINAL':50} {'IGUAL':6} {'DIF (bytes)'}")
print("-" * 100)

for i, dup in enumerate(duplicados, 1):
    igual_str = "✓ SÍ" if dup['iguales'] else "✗ NO"
    print(f"{i:3d} {dup['duplicado']:50} {dup['original']:50} {igual_str:6} {dup['diferencia']:>12,}")

print("-" * 100)
print(f"\nResumen:")
print(f"  Total analizados: {len(duplicados)}")
print(f"  Tamaño idéntico: {sum(1 for d in duplicados if d['iguales'])}")
print(f"  Tamaño diferente: {sum(1 for d in duplicados if not d['iguales'])}")

# Estadísticas completas
print(f"\n{'=' * 100}")
print("ESTADÍSTICAS COMPLETAS")
print("=" * 100)

todos_duplicados = 0
iguales_completo = 0
diferentes_completo = 0

for archivo_dup in archivos_con_1:
    nombre_original = archivo_dup.name.replace(" (1)", "")
    archivo_original = DECRETOS_2018 / nombre_original
    
    if archivo_original.exists():
        todos_duplicados += 1
        if archivo_dup.stat().st_size == archivo_original.stat().st_size:
            iguales_completo += 1
        else:
            diferentes_completo += 1

print(f"\nTotal de archivos con (1) que tienen original: {todos_duplicados}")
print(f"  - Tamaño idéntico: {iguales_completo} ({iguales_completo/max(todos_duplicados,1)*100:.1f}%)")
print(f"  - Tamaño diferente: {diferentes_completo} ({diferentes_completo/max(todos_duplicados,1)*100:.1f}%)")

print(f"\n✓ Análisis completado")
