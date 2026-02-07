"""
Analiza el log de verificación para entender los patrones de error.
"""
import re
from collections import defaultdict

# Leer el log
with open('log_verificacion_pdf_salida_bd.md', 'r', encoding='utf-8') as f:
    contenido = f.read()

# Extraer información
inconsistencias = re.findall(r'### \d+\. (.+?)\.pdf', contenido)
anios = re.findall(r'\*\*Año:\*\* (\d+)', contenido)
problemas_bd_sin_output = contenido.count('Está en BD pero NO tiene output')
problemas_sin_ambos = contenido.count('NO tiene output NI está en BD')
problemas_output_sin_bd = contenido.count('Tiene output pero NO está en BD')

print("=" * 80)
print("ANÁLISIS DEL LOG DE VERIFICACIÓN")
print("=" * 80)

print(f"\nTotal de inconsistencias: {len(inconsistencias)}")
print(f"\nTipos de problemas:")
print(f"  - BD sin output: {problemas_bd_sin_output}")
print(f"  - Sin output ni BD: {problemas_sin_ambos}")
print(f"  - Output sin BD: {problemas_output_sin_bd}")

# Contar por año
anios_count = defaultdict(int)
for anio in anios:
    anios_count[anio] += 1

print(f"\nInconsistencias por año:")
for anio in sorted(anios_count.keys()):
    print(f"  {anio}: {anios_count[anio]}")

# Analizar patrones de nombres
archivos_duplicados = [inc for inc in inconsistencias if '(1)' in inc]
archivos_no_fisico = [inc for inc in inconsistencias if 'NO FISICO' in inc]

print(f"\nPatrones detectados:")
print(f"  - Archivos duplicados (1): {len(archivos_duplicados)}")
print(f"  - Archivos NO FISICO: {len(archivos_no_fisico)}")

# Ejemplos del 2018
ejemplos_2018 = [inc for i, inc in enumerate(inconsistencias) if anios[i] == '2018']
print(f"\nEjemplos del 2018 (primeros 10):")
for ej in ejemplos_2018[:10]:
    print(f"  - {ej}.pdf")
