import sqlite3

conn = sqlite3.connect('novedades_pgn.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Buscar decreto
cursor.execute("SELECT * FROM decretos WHERE numero_decreto = '1021' AND anio = 2014")
decreto = cursor.fetchone()

if decreto:
    print("=" * 70)
    print("DECRETO 1021-2014")
    print("=" * 70)
    print(f"ID: {decreto['id']}")
    print(f"Numero: {decreto['numero_decreto']}")
    print(f"Anio: {decreto['anio']}")
    print(f"Fecha: {decreto['fecha_decreto_texto']}")
    print(f"Archivo: {decreto['archivo_origen']}")
    print(f"Estado: {decreto['estado_procesamiento']}")
    print(f"Tipo extraccion: {decreto['tipo_extraccion']}")
    print()
    print("TEXTO OCR:")
    print("-" * 70)
    texto = decreto['contenido_texto'] if decreto['contenido_texto'] else '(sin texto)'
    print(texto[:1200])
    print()
    
    # Novedades
    cursor.execute("""
        SELECT n.*, f.cedula, f.nombre_completo 
        FROM novedades n 
        LEFT JOIN funcionarios f ON n.funcionario_id = f.id 
        WHERE n.decreto_id = ?
    """, (decreto['id'],))
    novedades = cursor.fetchall()
    
    print("NOVEDADES:")
    print("-" * 70)
    if novedades:
        for n in novedades:
            print(f"  Novedad ID: {n['id']}")
            print(f"  Codigo: {n['codigo_novedad']} - {n['tipo_novedad']}")
            print(f"  Cedula: {n['cedula']}")
            print(f"  Nombre: {n['nombre_completo']}")
            print(f"  Cargo: {n['cargo_actual']}")
            print(f"  Dependencia: {n['dependencia']}")
            print(f"  Observaciones: {n['observaciones']}")
            print()
    else:
        print("  ** SIN NOVEDADES (HUERFANO) **")
else:
    print("Decreto 1021-2014 no encontrado")

conn.close()
