"""
Script para procesar automaticamente los archivos decretos y resoluciones no procesados.
Lee el reporte de verificacion y nota que se debe procesar.

Dado que los scripts extract_decretos.py y extract_resoluciones.py procesan directorios completos
y saltaran automaticamente archivos ya procesados, simplemente se ejecutan los comandos
para los directorios que tienen archivos faltantes.
"""
import os
import json
from pathlib import Path
from typing import Dict
from datetime import datetime


def main():
    """Funcion principal."""
    base_dir = Path(r"C:\temp\PNG_CERTIFICADO_V3")
    reporte_path = base_dir / "reporte_verificacion.json"
    
    print("=" * 80)
    print("ANALISIS DE ARCHIVOS FALTANTES")
    print("=" * 80)
    print(f"\nFecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Cargar reporte
    if not reporte_path.exists():
        print(f"[ERROR] No se encontro el reporte: {reporte_path}")
        return
    
    with open(reporte_path, 'r', encoding='utf-8') as f:
        reporte = json.load(f)
    
    print(f"[OK] Reporte cargado desde: {reporte_path}\n")
    
    # Analizar decretos
    decretos = reporte.get('decretos', {})
    archivos_decretos = decretos.get('archivos', [])
    
    print("=" * 80)
    print("DECRETOS NO PROCESADOS")
    print("=" * 80)
    print(f"\nTotal de archivos: {len(archivos_decretos)}\n")
    
    if archivos_decretos:
        # Agrupar por directorio
        por_dir = {}
        for item in archivos_decretos:
            dir_in = str(Path(item['ruta_completa']).parent)
            output_dir = item['output_dir']
            anio = item['año']
            
            key = (dir_in, output_dir, anio)
            if key not in por_dir:
                por_dir[key] = []
            por_dir[key].append(item)
        
        print(f"Directorios con archivos faltantes: {len(por_dir)}\n")
        
        for idx, (key, archivos) in enumerate(sorted(por_dir.items(), key=lambda x: x[0][2]), 1):
            dir_in, output_dir, anio = key
            print(f"\n[{idx}] Anio {anio} - {len(archivos)} archivos faltantes")
            print(f"    Comando para procesar:")
            print(f'    python extract_decretos.py --dir-in "{dir_in}" --llm gpt-oss:20b-cloud --output "{output_dir}"')
            print(f"    ")
            print(f"    Ejemplos de archivos faltantes:")
            for i, item in enumerate(archivos[:3], 1):
                print(f"       {i}. {item['archivo']}")
            if len(archivos) > 3:
                print(f"       ... y {len(archivos) - 3} mas")
    else:
        print("[OK] Todos los decretos han sido procesados correctamente\n")
    
    # Analizar resoluciones
    resoluciones = reporte.get('resoluciones', {})
    archivos_resoluciones = resoluciones.get('archivos', [])
    
    print("\n" + "=" * 80)
    print("RESOLUCIONES NO PROCESADAS")
    print("=" * 80)
    print(f"\nTotal de archivos: {len(archivos_resoluciones)}\n")
    
    if archivos_resoluciones:
        # Agrupar por directorio
        por_dir_res = {}
        for item in archivos_resoluciones:
            dir_in = str(Path(item['ruta_completa']).parent)
            output_dir = item['output_dir']
            anio = item['año']
            
            key = (dir_in, output_dir, anio)
            if key not in por_dir_res:
                por_dir_res[key] = []
            por_dir_res[key].append(item)
        
        print(f"Directorios con archivos faltantes: {len(por_dir_res)}\n")
        
        for idx, (key, archivos) in enumerate(sorted(por_dir_res.items(), key=lambda x: x[0][2]), 1):
            dir_in, output_dir, anio = key
            print(f"\n[{idx}] Anio {anio} - {len(archivos)} archivos faltantes")
            print(f"    Comando para procesar:")
            print(f'    python extract_resoluciones.py --dir-in "{dir_in}" --llm gpt-oss:120b-cloud --output "{output_dir}"')
            print(f"    ")
            print(f"    Archivos faltantes:")
            for i, item in enumerate(archivos, 1):
                print(f"       {i}. {item['archivo']}")
    else:
        print("[OK] Todas las resoluciones han sido procesadas correctamente\n")
    
    # Resumen final
    print("\n" + "=" * 80)
    print("RESUMEN")
    print("=" * 80)
    print(f"\nTotal de archivos sin procesar:")
    print(f"   Decretos: {len(archivos_decretos)}")
    print(f"   Resoluciones: {len(archivos_resoluciones)}")
    print(f"   TOTAL: {len(archivos_decretos) + len(archivos_resoluciones)}")
    
    print("\n[NOTA IMPORTANTE]")
    print("   Los scripts extract_decretos.py y extract_resoluciones.py ya tienen")
    print("   logica para saltar archivos ya procesados. Simplemente ejecute los")
    print("   comandos listados arriba y solo se procesaran los archivos faltantes.")
    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
