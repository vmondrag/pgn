import sqlite3

conn = sqlite3.connect('novedades_pgn.db')
cursor = conn.cursor()

# Listar todas las tablas
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print("TABLAS EN LA BASE DE DATOS:")
print("=" * 50)
for table in tables:
    print(f"  - {table[0]}")
    
    # Mostrar esquema de cada tabla
    cursor.execute(f"PRAGMA table_info({table[0]})")
    columns = cursor.fetchall()
    print(f"    Columnas: {', '.join([c[1] for c in columns[:10]])}")
    if len(columns) > 10:
        print(f"    ... y {len(columns) - 10} más")
    
    # Contar registros
    cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
    count = cursor.fetchone()[0]
    print(f"    Registros: {count:,}\n")

conn.close()
