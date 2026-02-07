"""
Script para consolidar todos los archivos MD de Novedades_OUT en un solo directorio.
Detecta duplicados y los renombra agregando el año + R.md para diferenciarlos.

Uso:
    python consolidar_md.py
    python consolidar_md.py --dry-run  # Solo muestra qué haría sin copiar
"""

import os
import shutil
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Configuración
BASE_PATH = Path(r"C:\temp\PNG_CERTIFICADO_V3\Novedades_OUT")
OUTPUT_DIR = BASE_PATH / "output_FULL_MD"
LOG_FILE = BASE_PATH / f"consolidacion_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"


def find_all_md_files():
    """Encuentra todos los archivos MD en los directorios output_XXXX_hybrid/md"""
    files_by_name = defaultdict(list)  # nombre_archivo -> [(año, ruta_completa), ...]

    # Buscar directorios que coincidan con el patrón
    for subdir in BASE_PATH.iterdir():
        if subdir.is_dir() and subdir.name.startswith("output_") and "_hybrid" in subdir.name:
            md_dir = subdir / "md"
            if md_dir.exists():
                # Extraer año del nombre del directorio
                try:
                    year = subdir.name.split("_")[1]
                except IndexError:
                    year = "UNKNOWN"

                # Listar archivos MD
                for md_file in md_dir.glob("*.md"):
                    files_by_name[md_file.name].append((year, md_file))

    return files_by_name


def consolidate_files(dry_run=False):
    """Consolida archivos MD en un solo directorio"""

    log_lines = []
    log_lines.append(f"=" * 70)
    log_lines.append(f"CONSOLIDACIÓN DE ARCHIVOS MD - {datetime.now().isoformat()}")
    log_lines.append(f"=" * 70)
    log_lines.append("")

    # Crear directorio de salida
    if not dry_run:
        OUTPUT_DIR.mkdir(exist_ok=True)

    log_lines.append(f"Directorio destino: {OUTPUT_DIR}")
    log_lines.append(f"Modo: {'DRY-RUN (simulación)' if dry_run else 'EJECUCIÓN REAL'}")
    log_lines.append("")

    # Encontrar todos los archivos
    files_by_name = find_all_md_files()

    total_files = sum(len(v) for v in files_by_name.values())
    unique_names = len(files_by_name)
    duplicates_count = sum(1 for v in files_by_name.values() if len(v) > 1)

    log_lines.append(f"Total archivos encontrados: {total_files}")
    log_lines.append(f"Nombres únicos: {unique_names}")
    log_lines.append(f"Nombres con duplicados: {duplicates_count}")
    log_lines.append("")

    # Procesar archivos
    copied = 0
    renamed = 0
    errors = []
    duplicates_detail = []

    log_lines.append("-" * 70)
    log_lines.append("PROCESAMIENTO DE ARCHIVOS")
    log_lines.append("-" * 70)

    for filename, file_list in sorted(files_by_name.items()):
        if len(file_list) == 1:
            # Archivo único - copiar directamente
            year, src_path = file_list[0]
            dst_path = OUTPUT_DIR / filename

            try:
                if not dry_run:
                    shutil.copy2(src_path, dst_path)
                copied += 1
            except Exception as e:
                errors.append(f"ERROR copiando {src_path}: {e}")

        else:
            # Archivo duplicado - registrar y renombrar
            duplicates_detail.append(f"\n[DUPLICADO] {filename}")
            duplicates_detail.append(f"  Encontrado en {len(file_list)} ubicaciones:")

            for i, (year, src_path) in enumerate(sorted(file_list, key=lambda x: x[0])):
                duplicates_detail.append(f"    - {year}: {src_path}")

                if i == 0:
                    # Primera ocurrencia: copiar con nombre original
                    dst_path = OUTPUT_DIR / filename
                    dst_name = filename
                else:
                    # Duplicados: agregar año + R al nombre
                    name_part = filename.rsplit('.', 1)[0]
                    new_name = f"{name_part}_{year}R.md"
                    dst_path = OUTPUT_DIR / new_name
                    dst_name = new_name
                    renamed += 1

                duplicates_detail.append(f"      -> Destino: {dst_name}")

                try:
                    if not dry_run:
                        shutil.copy2(src_path, dst_path)
                    copied += 1
                except Exception as e:
                    errors.append(f"ERROR copiando {src_path} -> {dst_path}: {e}")

    # Resumen
    log_lines.append("")
    log_lines.append("=" * 70)
    log_lines.append("RESUMEN")
    log_lines.append("=" * 70)
    log_lines.append(f"Archivos copiados: {copied}")
    log_lines.append(f"Archivos renombrados (duplicados): {renamed}")
    log_lines.append(f"Errores: {len(errors)}")
    log_lines.append("")

    # Detalle de duplicados
    if duplicates_detail:
        log_lines.append("=" * 70)
        log_lines.append("DETALLE DE DUPLICADOS")
        log_lines.append("=" * 70)
        log_lines.extend(duplicates_detail)
        log_lines.append("")

    # Errores
    if errors:
        log_lines.append("=" * 70)
        log_lines.append("ERRORES")
        log_lines.append("=" * 70)
        log_lines.extend(errors)
        log_lines.append("")

    # Guardar log
    log_content = "\n".join(log_lines)

    if not dry_run:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            f.write(log_content)
        print(f"\nLog guardado en: {LOG_FILE}")

    # Mostrar en consola
    print(log_content)

    return {
        'total_files': total_files,
        'copied': copied,
        'renamed': renamed,
        'errors': len(errors),
        'duplicates': duplicates_count
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Consolidar archivos MD de Novedades_OUT")
    parser.add_argument('--dry-run', action='store_true',
                        help='Simular sin copiar archivos')

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("CONSOLIDADOR DE ARCHIVOS MD - NOVEDADES PGN")
    print("=" * 70 + "\n")

    if args.dry_run:
        print("*** MODO DRY-RUN: No se copiarán archivos ***\n")

    result = consolidate_files(dry_run=args.dry_run)

    print("\n" + "=" * 70)
    print("FINALIZADO")
    print("=" * 70)
    print(f"  Total procesados: {result['total_files']}")
    print(f"  Copiados: {result['copied']}")
    print(f"  Renombrados: {result['renamed']}")
    print(f"  Duplicados detectados: {result['duplicates']}")
    print(f"  Errores: {result['errors']}")

    if not args.dry_run:
        print(f"\nArchivos consolidados en: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
