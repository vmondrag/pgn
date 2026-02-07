import sqlite3

conn = sqlite3.connect('novedades_pgn.db')
cursor = conn.cursor()

# Analizar decretos 1004-2014, 1028-2014, 2785-2014
decretos_ejemplo = ['1004', '1028', '2785']

for num in decretos_ejemplo:
    print("=" * 80)
    print(f"DECRETO {num}-2014")
    print("=" * 80)
    
    # Obtener contenido OCR
    cursor.execute("""
        SELECT id, numero_decreto, contenido_texto, tipo_extraccion
        FROM decretos 
        WHERE archivo_origen LIKE ? AND anio = 2014
    """, (f'%{num}%',))
    
    decreto = cursor.fetchone()
    if decreto:
        print(f"ID: {decreto[0]}")
        print(f"Numero: {decreto[1]}")
        print(f"Metodo Extraccion: {decreto[3]}")
        print(f"\nTexto OCR (primeros 800 chars):")
        print("-" * 40)
        if decreto[2]:
            print(decreto[2][:800])
        else:
            print("(sin texto)")
        print("-" * 40)
        
        # Ver novedades
        cursor.execute("""
            SELECT n.codigo_novedad, f.cedula, f.nombre_completo
            FROM novedades n
            LEFT JOIN funcionarios f ON n.funcionario_id = f.id
            WHERE n.decreto_id = ?
        """, (decreto[0],))
        novedades = cursor.fetchall()
        if novedades:
            print(f"\nNovedades registradas: {len(novedades)}")
            for n in novedades:
                print(f"  - {n[0]}: {n[2]} (CC: {n[1]})")
        else:
            print("\nNovedades: NINGUNA (HUERFANO)")
    else:
        print("No encontrado")
    print()

# Estadisticas de huerfanos pendientes
print("=" * 80)
print("ESTADISTICAS DE HUERFANOS")
print("=" * 80)

cursor.execute("""
    SELECT COUNT(*) FROM decretos d
    WHERE NOT EXISTS (SELECT 1 FROM novedades n WHERE n.decreto_id = d.id)
    OR d.id IN (SELECT decreto_id FROM novedades WHERE codigo_novedad = 'PENDIENTE_REVISION')
""")
print(f"Total huerfanos: {cursor.fetchone()[0]}")

cursor.execute("""
    SELECT anio, COUNT(*) as total 
    FROM decretos d
    WHERE NOT EXISTS (SELECT 1 FROM novedades n WHERE n.decreto_id = d.id)
    GROUP BY anio
    ORDER BY anio
""")
print("\nHuerfanos por anio (sin novedades):")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]}")

conn.close()
