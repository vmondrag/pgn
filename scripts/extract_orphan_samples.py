import sqlite3
import json

conn = sqlite3.connect('novedades_pgn.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Obtener 20 huérfanos diversos (diferentes años y tipos)
cursor.execute('''
    SELECT d.id, d.numero_decreto, d.anio, d.contenido_texto, d.archivo_origen
    FROM decretos d
    WHERE NOT EXISTS (SELECT 1 FROM novedades n WHERE n.decreto_id = d.id)
    AND d.contenido_texto IS NOT NULL 
    AND LENGTH(d.contenido_texto) > 100
    ORDER BY RANDOM()
    LIMIT 25
''')

decretos = cursor.fetchall()

print("=" * 80)
print(f"MUESTRA DE {len(decretos)} DECRETOS HUÉRFANOS PARA ANÁLISIS")
print("=" * 80)

# Guardar en JSON para análisis
samples = []

for i, d in enumerate(decretos):
    texto = d['contenido_texto'][:800] if d['contenido_texto'] else ''
    
    print(f"\n{'='*60}")
    print(f"DECRETO #{i+1}: {d['numero_decreto']}-{d['anio']} (ID: {d['id']})")
    print(f"Archivo: {d['archivo_origen']}")
    print("-" * 60)
    print(texto[:600])
    print("...")
    
    samples.append({
        'id': d['id'],
        'numero': d['numero_decreto'],
        'anio': d['anio'],
        'archivo': d['archivo_origen'],
        'texto_ocr': texto
    })

# Guardar JSON
with open('huerfanos_sample.json', 'w', encoding='utf-8') as f:
    json.dump(samples, f, indent=2, ensure_ascii=False)

print(f"\n\n{'='*80}")
print(f"Guardado: huerfanos_sample.json ({len(samples)} decretos)")
print("=" * 80)

# Estadísticas por año
cursor.execute('''
    SELECT anio, COUNT(*) as total FROM decretos d
    WHERE NOT EXISTS (SELECT 1 FROM novedades n WHERE n.decreto_id = d.id)
    GROUP BY anio ORDER BY anio
''')
print("\nDistribución de huérfanos por año:")
for row in cursor.fetchall():
    print(f"  {row['anio']}: {row['total']}")

conn.close()
