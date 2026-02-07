import sqlite3

# Conectar a la base de datos
conn = sqlite3.connect('novedades_pgn.db')
cursor = conn.cursor()

# Consultar errores - usando solo columnas que existen
query = """
    SELECT id, archivo_origen, extraction_method, numero_decreto, 
           fecha_decreto, anio_decreto
    FROM decretos 
    WHERE extraction_method LIKE '%ERROR%' 
       OR extraction_method = 'ERROR_OCR' 
       OR extraction_method = 'ERROR_NO_FITZ'
       OR extraction_method LIKE 'ERROR:%'
    ORDER BY id
"""

cursor.execute(query)
errores = cursor.fetchall()

print(f"Total de errores encontrados: {len(errores)}\n")
print("=" * 100)
print("LISTA DE ERRORES DE PROCESAMIENTO")
print("=" * 100)

for i, error in enumerate(errores, 1):
    id_decreto, archivo, metodo, num_decreto, fecha, anio = error
    
    # Extraer solo el nombre del archivo
    archivo_nombre = archivo.split('\\')[-1] if archivo else 'N/A'
    
    print(f"\n{i}. ID: {id_decreto}")
    print(f"   Archivo: {archivo_nombre}")
    print(f"   Ruta: {archivo}")
    print(f"   Tipo de Error: {metodo}")
    print(f"   Número Decreto: {num_decreto if num_decreto else 'N/A'}")
    print(f"   Fecha: {fecha if fecha else 'N/A'}")
    print(f"   Año: {anio if anio else 'N/A'}")
    print("-" * 100)

# Resumen por tipo de error
print("\n" + "=" * 100)
print("RESUMEN POR TIPO DE ERROR")
print("=" * 100)

cursor.execute("""
    SELECT extraction_method, COUNT(*) as total
    FROM decretos 
    WHERE extraction_method LIKE '%ERROR%' 
       OR extraction_method = 'ERROR_OCR' 
       OR extraction_method = 'ERROR_NO_FITZ'
       OR extraction_method LIKE 'ERROR:%'
    GROUP BY extraction_method
    ORDER BY total DESC
""")

resumen = cursor.fetchall()
for tipo, total in resumen:
    print(f"  {tipo}: {total} archivos")

conn.close()
