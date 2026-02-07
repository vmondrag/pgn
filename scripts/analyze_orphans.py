import sqlite3

conn = sqlite3.connect('novedades_pgn.db')
cursor = conn.cursor()

# Analizar muestra de huerfanos para identificar patrones
print("=" * 80)
print("MUESTRA DE DECRETOS HUERFANOS (sin novedades)")
print("=" * 80)

cursor.execute("""
    SELECT d.id, d.numero_decreto, d.anio, d.contenido_texto, d.tipo_extraccion
    FROM decretos d
    WHERE NOT EXISTS (SELECT 1 FROM novedades n WHERE n.decreto_id = d.id)
    ORDER BY d.anio DESC
    LIMIT 10
""")

for decreto in cursor.fetchall():
    print(f"\n{'='*60}")
    print(f"ID: {decreto[0]} | Decreto: {decreto[1]}-{decreto[2]} | Extraccion: {decreto[4]}")
    print("-" * 60)
    texto = decreto[3] if decreto[3] else "(SIN TEXTO)"
    print(texto[:500])
    print("...")

# Categorizar huerfanos
print("\n" + "=" * 80)
print("CATEGORIAS DE HUERFANOS")
print("=" * 80)

# Huerfanos con texto OCR vs sin texto
cursor.execute("""
    SELECT 
        CASE WHEN contenido_texto IS NULL OR contenido_texto = '' THEN 'SIN_TEXTO' ELSE 'CON_TEXTO' END as tipo,
        COUNT(*) 
    FROM decretos d
    WHERE NOT EXISTS (SELECT 1 FROM novedades n WHERE n.decreto_id = d.id)
    GROUP BY tipo
""")
print("\nPor tipo de contenido:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]}")

# Huerfanos por metodo de extraccion
cursor.execute("""
    SELECT tipo_extraccion, COUNT(*) 
    FROM decretos d
    WHERE NOT EXISTS (SELECT 1 FROM novedades n WHERE n.decreto_id = d.id)
    GROUP BY tipo_extraccion
""")
print("\nPor metodo de extraccion:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]}")

# Palabras clave en huerfanos con texto
cursor.execute("""
    SELECT contenido_texto FROM decretos d
    WHERE NOT EXISTS (SELECT 1 FROM novedades n WHERE n.decreto_id = d.id)
    AND contenido_texto IS NOT NULL AND contenido_texto != ''
    LIMIT 50
""")

keywords = {
    'Nombrar': 0, 'Encargar': 0, 'Aceptar': 0, 'Revocar': 0, 
    'Trasladar': 0, 'Comision': 0, 'Renuncia': 0, 'Insubsistencia': 0,
    'provisional': 0, 'encargo': 0, 'fallecimiento': 0
}
total_con_texto = 0
for row in cursor.fetchall():
    total_con_texto += 1
    texto = row[0].upper()
    for k in keywords:
        if k.upper() in texto:
            keywords[k] += 1

print(f"\nPalabras clave en {total_con_texto} huerfanos con texto:")
for k, v in sorted(keywords.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")

conn.close()
