"""
Analiza las 430 inconsistencias restantes después de eliminar duplicados.
"""
import re
from collections import defaultdict

# Leer el log
with open('log_verificacion_pdf_salida_bd.md', 'r', encoding='utf-8') as f:
    contenido = f.read()

# Extraer inconsistencias
inconsistencias = re.findall(r'### \d+\. (.+?)\.pdf', contenido)
anios = re.findall(r'\*\*Año:\*\* (\d+)', contenido)
problemas_bd_sin_output = contenido.count('Está en BD pero NO tiene output')
problemas_sin_ambos = contenido.count('NO tiene output NI está en BD')

print("=" * 100)
print("ANÁLISIS DE 430 INCONSISTENCIAS RESTANTES")
print("=" * 100)

print(f"\nTotal de inconsistencias: {len(inconsistencias)}")
print(f"\nTipos de problemas:")
print(f"  - BD sin output: {problemas_bd_sin_output}")
print(f"  - Sin output ni BD: {problemas_sin_ambos}")

# Contar por año
anios_count = defaultdict(int)
for anio in anios:
    anios_count[anio] += 1

print(f"\nInconsistencias por año:")
for anio in sorted(anios_count.keys()):
    print(f"  {anio}: {anios_count[anio]}")

# Analizar patrones de nombres
archivos_duplicados_restantes = [inc for inc in inconsistencias if '(1)' in inc]
archivos_no_fisico = [inc for inc in inconsistencias if 'NO FISICO' in inc]
archivos_normales = [inc for inc in inconsistencias if '(1)' not in inc and 'NO FISICO' not in inc]

print(f"\nPatrones detectados:")
print(f"  - Archivos con (1): {len(archivos_duplicados_restantes)}")
print(f"  - Archivos NO FISICO: {len(archivos_no_fisico)}")
print(f"  - Archivos normales: {len(archivos_normales)}")

# Ejemplos de archivos normales del 2018
if anios_count.get('2018', 0) > 0:
    ejemplos_2018 = [(inc, anio) for inc, anio in zip(inconsistencias, anios) if anio == '2018'][:20]
    print(f"\nEjemplos del 2018 (primeros 20):")
    for ej, _ in ejemplos_2018:
        tiene_duplicado = '(1)' in ej
        print(f"  - {ej}.pdf {'[DUPLICADO]' if tiene_duplicado else ''}")

print("\n" + "=" * 100)
print("CONCLUSIÓN")
print("=" * 100)

if problemas_bd_sin_output > 400:
    print("\n✓ La mayoría de inconsistencias son archivos procesados en BD sin output")
    print("✓ Solución recomendada: Regenerar archivos .graphrag.json desde BD")
else:
    print("\n⚠️  Patrón mixto de problemas - requiere análisis detallado")

print(f"\n✓ Análisis completado")
