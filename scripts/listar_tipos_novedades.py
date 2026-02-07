"""
Script para listar todos los tipos de novedades en la base de datos.
"""
import sqlite3

DB_PATH = r"C:\temp\PNG_CERTIFICADO_V3\novedades_pgn.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("=" * 80)
print("TIPOS DE NOVEDADES EN LA BASE DE DATOS NOVEDADES_PGN.DB")
print("=" * 80)

# Obtener tipos de decretos
cursor.execute("""
    SELECT codigo_novedad, COUNT(*) as total 
    FROM decretos 
    WHERE codigo_novedad IS NOT NULL AND codigo_novedad != ''
    GROUP BY codigo_novedad 
    ORDER BY total DESC
""")

tipos_decretos = cursor.fetchall()

print(f"\n📋 DECRETOS - Total de tipos únicos: {len(tipos_decretos)}\n")
print(f"{'#':>3} {'CÓDIGO':15} {'CANTIDAD':>10} {'DESCRIPCIÓN'}")
print("-" * 80)

# Diccionario con descripciones de códigos
descripciones = {
    'N': 'Nombramiento',
    'R': 'Renuncia',
    'E': 'Encargo',
    'D': 'Destitución',
    'T': 'Traslado',
    'RET': 'Retiro/Jubilación',
    'NORD': 'Nombramiento Ordinario',
    'NPROV': 'Nombramiento Provisional',
    'RCAR': 'Renuncia al Cargo',
    'ETEMP': 'Encargo Temporal',
    'EVAC': 'Encargo por Vacancia',
    'ELIC': 'Encargo por Licencia',
    'ECOM': 'Encargo por Comisión',
    'TENC': 'Terminación de Encargo',
    'TPROV': 'Terminación de Provisionalidad',
    'RECL': 'Reclasificación de Cargo',
    'DESINH': 'Destitución e Inhabilidad',
    'SUSPD': 'Suspensión Disciplinaria',
    'SUSPINH': 'Suspensión e Inhabilidad',
    'MULTA': 'Multa Disciplinaria',
    'AMONES': 'Amonestación Escrita',
}

for i, (codigo, total) in enumerate(tipos_decretos, 1):
    descripcion = descripciones.get(codigo, '-')
    print(f"{i:3d} {codigo:15} {total:>10,} {descripcion}")

# Calcular totales
total_decretos = sum(total for _, total in tipos_decretos)
print("-" * 80)
print(f"{'TOTAL':18} {total_decretos:>10,}")

# Obtener tipos de resoluciones si existen
cursor.execute("""
    SELECT name FROM sqlite_master 
    WHERE type='table' AND name='resoluciones'
""")

if cursor.fetchone():
    cursor.execute("""
        SELECT codigo_novedad, COUNT(*) as total 
        FROM resoluciones 
        WHERE codigo_novedad IS NOT NULL AND codigo_novedad != ''
        GROUP BY codigo_novedad 
        ORDER BY total DESC
    """)
    
    tipos_resoluciones = cursor.fetchall()
    
    if tipos_resoluciones:
        print(f"\n\n📋 RESOLUCIONES - Total de tipos únicos: {len(tipos_resoluciones)}\n")
        print(f"{'#':>3} {'CÓDIGO':15} {'CANTIDAD':>10} {'DESCRIPCIÓN'}")
        print("-" * 80)
        
        descripciones_res = {
            'LNR': 'Licencia No Remunerada',
            'LNRE': 'Licencia No Remunerada para Estudios',
            'LR': 'Licencia Remunerada',
            'LLUT': 'Licencia por Luto',
            'LMAT': 'Licencia por Maternidad',
            'LPAT': 'Licencia por Paternidad',
            'LENF': 'Licencia por Enfermedad',
            'LDEP': 'Licencia Deportiva',
            'CESP': 'Comisión Especial',
            'CEST': 'Comisión de Estudios',
            'CSER': 'Comisión de Servicio',
            'RCESP': 'Renuncia a Comisión Especial',
            'TCOM': 'Terminación de Comisión',
            'REINC': 'Reincorporación al Cargo',
            'PPOS': 'Prórroga para Posesión',
            'PCOM': 'Prórroga de Comisión',
            'PLIC': 'Prórroga de Licencia',
            'VAC': 'Vacaciones',
            'IVAC': 'Interrupción de Vacaciones',
            'PERM': 'Permiso Remunerado',
            'COJ': 'Cumplimiento Orden Judicial',
            'NEG': 'Negación de Solicitud',
            'REV': 'Revocatoria/Modificación',
            'SUSP': 'Suspensión del Cargo',
            'SUSPI': 'Suspensión por Inhabilidad Sobreviniente',
        }
        
        for i, (codigo, total) in enumerate(tipos_resoluciones, 1):
            descripcion = descripciones_res.get(codigo, descripciones.get(codigo, '-'))
            print(f"{i:3d} {codigo:15} {total:>10,} {descripcion}")
        
        total_resoluciones = sum(total for _, total in tipos_resoluciones)
        print("-" * 80)
        print(f"{'TOTAL':18} {total_resoluciones:>10,}")

print("\n" + "=" * 80)
print("RESUMEN GENERAL")
print("=" * 80)
print(f"\nTipos de novedad en DECRETOS: {len(tipos_decretos)}")
print(f"Total registros en DECRETOS: {total_decretos:,}")

conn.close()

print("\n✓ Consulta completada")
