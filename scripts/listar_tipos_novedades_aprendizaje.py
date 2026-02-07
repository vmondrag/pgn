"""
Script para listar todos los tipos de novedades desde la tabla de ejemplos de aprendizaje.
"""
import sqlite3

DB_PATH = r"C:\temp\PNG_CERTIFICADO_V3\novedades_pgn.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("=" * 100)
print("TIPOS DE NOVEDADES - BASE DE APRENDIZAJE LLM")
print("=" * 100)

# Obtener tipos de novedades de la tabla de ejemplos
cursor.execute("""
    SELECT codigo_novedad, COUNT(*) as total_ejemplos,
           AVG(CAST(confianza AS FLOAT)) as confianza_promedio
    FROM ejemplos_aprendizaje 
    WHERE codigo_novedad IS NOT NULL AND codigo_novedad != ''
    GROUP BY codigo_novedad 
    ORDER BY total_ejemplos DESC
""")

tipos = cursor.fetchall()

print(f"\n📊 Total de tipos únicos de novedad: {len(tipos)}")
print(f"📝 Total de ejemplos de aprendizaje: {sum(t[1] for t in tipos):,}\n")

print(f"{'#':>4} {'CÓDIGO':15} {'EJEMPLOS':>12} {'CONFIANZA':>12}")
print("-" * 100)

for i, (codigo, ejemplos, confianza) in enumerate(tipos, 1):
    confianza_pct = f"{confianza*100:.1f}%" if confianza else "N/A"
    print(f"{i:4d} {codigo:15} {ejemplos:>12,} {confianza_pct:>12}")

# Total
total_ejemplos = sum(ejemplos for _, ejemplos, _ in tipos)
print("-" * 100)
print(f"{'TOTAL':19} {total_ejemplos:>12,}")

# Obtener descripciones desde la tabla codigos_novedad si existe
print(f"\n\n{'=' * 100}")
print("TIPOS DE NOVEDADES CON DESCRIPCIÓN")
print("=" * 100)

cursor.execute("""
    SELECT e.codigo_novedad, 
           c.descripcion,
           c.tipo_general,
           COUNT(*) as ejemplos
    FROM ejemplos_aprendizaje e
    LEFT JOIN codigos_novedad c ON e.codigo_novedad = c.codigo
    WHERE e.codigo_novedad IS NOT NULL AND e.codigo_novedad != ''
    GROUP BY e.codigo_novedad, c.descripcion, c.tipo_general
    ORDER BY ejemplos DESC
""")

tipos_con_desc = cursor.fetchall()

if tipos_con_desc:
    print(f"\n{'CÓDIGO':15} {'EJEMPLOS':>10} {'TIPO':20} DESCRIPCIÓN")
    print("-" * 100)
    
    for codigo, desc, tipo, ejemplos in tipos_con_desc:
        desc_short = (desc[:40] + '...') if len(desc or '') > 40 else (desc or 'Sin descripción')
        tipo_short = (tipo or 'N/A')[:20]
        print(f"{codigo:15} {ejemplos:>10,} {tipo_short:20} {desc_short}")

conn.close()

print(f"\n{'=' * 100}")
print("✓ Consulta completada")
print("=" * 100)
