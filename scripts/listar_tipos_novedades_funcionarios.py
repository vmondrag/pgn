"""
Script para listar todos los tipos de novedades desde la tabla funcionarios.
"""
import sqlite3

DB_PATH = r"C:\temp\PNG_CERTIFICADO_V3\novedades_pgn.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("=" * 100)
print("TIPOS DE NOVEDADES EN LA BASE DE DATOS (desde tabla funcionarios)")
print("=" * 100)

# Obtener tipos de novedades de funcionarios
cursor.execute("""
    SELECT codigo_novedad, descripcion_novedad, COUNT(*) as total 
    FROM funcionarios 
    WHERE codigo_novedad IS NOT NULL AND codigo_novedad != ''
    GROUP BY codigo_novedad, descripcion_novedad
    ORDER BY total DESC
""")

tipos = cursor.fetchall()

print(f"\n📋 Total de tipos únicos de novedad: {len(tipos)}\n")
print(f"{'#':>4} {'CÓDIGO':15} {'CANTIDAD':>12} DESCRIPCIÓN")
print("-" * 100)

for i, (codigo, descripcion, total) in enumerate(tipos, 1):
    desc_short = (descripcion[:60] + '...') if len(descripcion or '') > 60 else (descripcion or '-')
    print(f"{i:4d} {codigo:15} {total:>12,} {desc_short}")

# Calcular total
total_novedades = sum(total for _, _, total in tipos)
print("-" * 100)
print(f"{'TOTAL DE REGISTROS':33} {total_novedades:>12,}")

# Resumen por categorías principales
print(f"\n\n{'=' * 100}")
print("RESUMEN POR CATEGORÍA")
print("=" * 100)

categorias = {}
for codigo, desc, total in tipos:
    # Categorizar por primera letra o patrón
    if codigo.startswith('N'):
        cat = 'NOMBRAMIENTOS'
    elif codigo.startswith('R') and not codigo.startswith('RE'):
        cat = 'RENUNCIAS'
    elif codigo.startswith('E'):
        cat = 'ENCARGOS'
    elif codigo.startswith('D'):
        cat = 'DESTITUCIONES/DISCIPLINARIAS'
    elif codigo.startswith('T'):
        cat = 'TRASLADOS/TERMINACIONES'
    elif codigo.startswith('L'):
        cat = 'LICENCIAS'
    elif codigo.startswith('C'):
        cat = 'COMISIONES'
    elif codigo.startswith('P'):
        cat = 'PRÓRROGAS/PERMISOS'
    elif codigo.startswith('V') or codigo.startswith('I'):
        cat = 'VACACIONES'
    elif codigo.startswith('S'):
        cat = 'SUSPENSIONES'
    elif codigo == 'RET':
        cat = 'RETIROS'
    else:
        cat = 'OTROS'
    
    if cat not in categorias:
        categorias[cat] = []
    categorias[cat].append((codigo, total))

# Mostrar resumen
for categoria in sorted(categorias.keys()):
    total_cat = sum(t for _, t in categorias[categoria])
    print(f"\n{categoria}:")
    print(f"  Códigos: {len(categorias[categoria])}")
    print(f"  Total registros: {total_cat:,}")
    print(f"  Tipos: {', '.join([c for c, _ in categorias[categoria][:10]])}")
    if len(categorias[categoria]) > 10:
        print(f"  ... y {len(categorias[categoria]) - 10} más")

conn.close()

print(f"\n{'=' * 100}")
print("✓ Consulta completada")
print("=" * 100)
