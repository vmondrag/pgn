import sqlite3

conn = sqlite3.connect('novedades_pgn.db')
cursor = conn.cursor()

# Consultar tipos de novedades
cursor.execute("""
    SELECT e.codigo_novedad, c.descripcion, c.tipo_general, COUNT(*) as ejemplos
    FROM ejemplos_aprendizaje e
    LEFT JOIN codigos_novedad c ON e.codigo_novedad = c.codigo
    WHERE e.codigo_novedad IS NOT NULL
    GROUP BY e.codigo_novedad
    ORDER BY ejemplos DESC
""")

tipos = cursor.fetchall()

# Generar markdown
md_lines = [
    "# Lista Completa de Tipos de Novedades",
    "",
    f"**Total de tipos únicos:** {len(tipos)}",
    f"**Total de ejemplos de aprendizaje:** {sum(t[3] for t in tipos):,}",
    "",
    "| # | Código | Ejemplos | Tipo General | Descripción |",
    "|---|--------|----------|--------------|-------------|",
]

for i, (codigo, desc, tipo, ejemplos) in enumerate(tipos, 1):
    desc_text = desc or "Sin descripción"
    tipo_text = tipo or "N/A"
    md_lines.append(f"| {i} | **{codigo}** | {ejemplos:,} | {tipo_text} | {desc_text} |")

md_lines.extend([
    "",
    f"**Total:** {sum(t[3] for t in tipos):,} ejemplos",
])

# Guardar archivo
with open('lista_completa_tipos_novedades.md', 'w', encoding='utf-8') as f:
    f.write('\n'.join(md_lines))

print(f"✓ Archivo creado: lista_completa_tipos_novedades.md")
print(f"✓ Total tipos: {len(tipos)}")

conn.close()
