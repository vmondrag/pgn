"""
Script para listar todos los tipos de novedades y guardar en archivo.
"""
import sqlite3

DB_PATH = r"C:\temp\PNG_CERTIFICADO_V3\novedades_pgn.db"
OUTPUT_FILE = r"C:\temp\PNG_CERTIFICADO_V3\lista_tipos_novedades.txt"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

output = []
output.append("=" * 100)
output.append("LISTA COMPLETA DE TIPOS DE NOVEDADES")
output.append("Fuente: Base de Datos novedades_pgn.db - Tabla ejemplos_aprendizaje")
output.append("=" * 100)
output.append("")

# Obtener tipos con descripciones
cursor.execute("""
    SELECT e.codigo_novedad, 
           c.descripcion,
           c.tipo_general,
           COUNT(*) as ejemplos,
           AVG(CAST(e.confianza AS FLOAT)) as confianza_prom
    FROM ejemplos_aprendizaje e
    LEFT JOIN codigos_novedad c ON e.codigo_novedad = c.codigo
    WHERE e.codigo_novedad IS NOT NULL AND e.codigo_novedad != ''
    GROUP BY e.codigo_novedad, c.descripcion, c.tipo_general
    ORDER BY ejemplos DESC
""")

tipos = cursor.fetchall()

output.append(f"Total de tipos únicos: {len(tipos)}")
output.append(f"Total de ejemplos de aprendizaje: {sum(t[3] for t in tipos):,}")
output.append("")
output.append(f"{'#':>4} {'CÓDIGO':15} {'EJEMPLOS':>10} {'CONF%':>8} {'TIPO':20} DESCRIPCIÓN")
output.append("-" * 120)

for i, (codigo, desc, tipo, ejemplos, conf) in enumerate(tipos, 1):
    conf_pct = f"{conf*100:.1f}%" if conf else "N/A"
    desc_text = desc or "Sin descripción"
    tipo_text = tipo or "N/A"
    output.append(f"{i:4d} {codigo:15} {ejemplos:>10,} {conf_pct:>8} {tipo_text:20} {desc_text}")

output.append("-" * 120)
output.append(f"{'TOTAL':21} {sum(t[3] for t in tipos):>10,}")
output.append("")
output.append("=" * 100)

# Escribir a archivo
with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))

# También imprimir en consola
for line in output:
    print(line)

conn.close()

print(f"\n✓ Lista guardada en: {OUTPUT_FILE}")
