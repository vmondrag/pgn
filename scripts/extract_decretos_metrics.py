"""
Extracción de Decretos con Métricas Detalladas
Genera archivos MD, GraphRAG JSON y tabla de métricas
"""
import os
import re
import json
import sqlite3
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Importar funciones del script principal
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extract_decretos import (
    extract_pdf_text, extract_novedad_with_llm, 
    get_codigos_catalogo, extract_year_from_path,
    parse_filename_decree_info, HAS_FITZ, query_ollama
)

# Configuración
DB_PATH = r"C:\temp\PNG_CERTIFICADO_V3\novedades_pgn.db"
DEFAULT_DIR = r"C:\temp\PNG_CERTIFICADO_V3\Decretos\2009"
OUTPUT_DIR = r"C:\temp\PNG_CERTIFICADO_V3\output_2009"


def ensure_dir(path: str):
    """Crea directorio si no existe"""
    if not os.path.exists(path):
        os.makedirs(path)


def generate_markdown(decree_name: str, filepath: str, text: str, 
                      method: str, extracted: Dict, metrics: Dict) -> str:
    """Genera contenido Markdown para un decreto"""
    md = []
    md.append(f"# {decree_name}\n")
    md.append(f"**Archivo:** `{filepath}`\n")
    md.append(f"**Procesado:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    md.append("\n## Métricas de Extracción\n")
    md.append(f"| Campo | Valor |")
    md.append(f"|-------|-------|")
    md.append(f"| Método | {method} |")
    md.append(f"| Caracteres | {metrics.get('chars', 0):,} |")
    md.append(f"| Funcionarios | {metrics.get('num_funcionarios', 0)} |")
    md.append(f"| Código Novedad | {metrics.get('codigo', 'N/A')} |")
    md.append(f"| Número Decreto | {metrics.get('numero_decreto', 'N/A')} |")
    md.append(f"| Año | {metrics.get('anio', 'N/A')} |")
    
    md.append("\n## Razonamiento del LLM\n")
    razonamiento = extracted.get('razonamiento', 'No disponible')
    md.append(f"> {razonamiento}\n")
    
    md.append("\n## Datos Extraídos (JSON)\n")
    md.append("```json")
    # Limitar tamaño del JSON para legibilidad
    extracted_clean = {k: v for k, v in extracted.items() if k != 'contenido_texto'}
    md.append(json.dumps(extracted_clean, indent=2, ensure_ascii=False, default=str)[:3000])
    md.append("```\n")
    
    md.append("\n## Funcionarios Detectados\n")
    funcionarios = extracted.get('funcionarios', [])
    if funcionarios:
        md.append("| Cédula | Nombre | Cargo | Acción |")
        md.append("|--------|--------|-------|--------|")
        for func in funcionarios[:10]:  # Máximo 10
            cedula = func.get('cedula', 'N/A')
            nombre = func.get('nombre_completo', func.get('nombres', 'N/A'))[:40]
            cargo = (func.get('cargo', 'N/A') or 'N/A')[:30]
            accion = (func.get('accion_especifica', 'N/A') or 'N/A')[:20]
            md.append(f"| {cedula} | {nombre} | {cargo} | {accion} |")
    else:
        md.append("*No se detectaron funcionarios*\n")
    
    md.append("\n## Texto Extraído (primeros 2000 chars)\n")
    md.append("```text")
    md.append(text[:2000])
    md.append("```\n")
    
    return "\n".join(md)


def generate_graphrag_json(decree_name: str, filepath: str, 
                           extracted: Dict, metrics: Dict) -> Dict:
    """Genera estructura JSON para GraphRAG"""
    entities = []
    relationships = []
    
    # Entidad del decreto
    decreto_id = f"decreto_{metrics.get('numero_decreto', 'unknown')}_{metrics.get('anio', 'unknown')}"
    entities.append({
        "id": decreto_id,
        "type": "DECRETO",
        "name": decree_name,
        "properties": {
            "numero": metrics.get('numero_decreto'),
            "anio": metrics.get('anio'),
            "fecha": extracted.get('fecha_decreto'),
            "tipo_documento": extracted.get('tipo_documento', 'DECRETO'),
            "codigo_novedad": metrics.get('codigo'),
            "archivo": filepath
        }
    })
    
    # Entidades de funcionarios
    funcionarios = extracted.get('funcionarios', [])
    for i, func in enumerate(funcionarios):
        cedula = func.get('cedula', f'unknown_{i}')
        func_id = f"funcionario_{cedula}"
        
        entities.append({
            "id": func_id,
            "type": "FUNCIONARIO",
            "name": func.get('nombre_completo', func.get('nombres', 'Desconocido')),
            "properties": {
                "cedula": cedula,
                "nombres": func.get('nombres'),
                "apellidos": func.get('apellidos'),
                "cargo": func.get('cargo'),
                "dependencia": func.get('dependencia'),
                "sede": func.get('sede')
            }
        })
        
        # Relación funcionario -> decreto
        accion = func.get('accion_especifica', metrics.get('codigo', 'NOVEDAD'))
        relationships.append({
            "source": func_id,
            "target": decreto_id,
            "type": accion.upper().replace(' ', '_') if accion else 'MENCIONADO_EN',
            "properties": {
                "fecha_inicio": func.get('fecha_efectos'),
                "fecha_fin": func.get('fecha_hasta'),
                "tipo_vinculacion": func.get('tipo_vinculacion'),
                "articulo": func.get('articulo_aplicable')
            }
        })
    
    return {
        "document": decree_name,
        "source_file": filepath,
        "extraction_date": datetime.now().isoformat(),
        "entities": entities,
        "relationships": relationships,
        "metadata": {
            "extraction_method": metrics.get('method'),
            "text_length": metrics.get('chars'),
            "llm_reasoning": extracted.get('razonamiento', '')
        }
    }


def process_decree_with_metrics(filepath: str, conn: sqlite3.Connection) -> Dict:
    """Procesa un decreto y retorna métricas detalladas"""
    filename = os.path.basename(filepath)
    decree_name = filename.replace('.pdf', '').replace('.PDF', '')
    
    result = {
        'filename': filename,
        'filepath': filepath,
        'decree_name': decree_name,
        'success': False,
        'metrics': {},
        'extracted': {},
        'text': '',
        'error': None
    }
    
    try:
        # 1. Extraer texto
        text, method = extract_pdf_text(filepath)
        
        if not text or method.startswith('ERROR'):
            result['error'] = f"Extracción fallida: {method}"
            result['metrics']['method'] = method
            return result
        
        result['text'] = text
        result['metrics']['method'] = method
        result['metrics']['chars'] = len(text)
        
        # 2. Analizar con LLM
        extracted = extract_novedad_with_llm(text, filename, conn)
        result['extracted'] = extracted
        
        # 3. Extraer métricas
        funcionarios = extracted.get('funcionarios', [])
        novedad = extracted.get('novedad', extracted.get('novedad_general', {}))
        
        result['metrics']['num_funcionarios'] = len(funcionarios)
        result['metrics']['codigo'] = novedad.get('codigo', extracted.get('codigo_novedad_determinado', 'N/A'))
        result['metrics']['numero_decreto'] = extracted.get('numero_decreto', 'N/A')
        result['metrics']['anio'] = extracted.get('anio_decreto') or extract_year_from_path(filepath)
        result['metrics']['razonamiento'] = extracted.get('razonamiento', '')[:200]
        result['metrics']['tiene_cedulas'] = any(f.get('cedula') for f in funcionarios)
        result['metrics']['tiene_cargos'] = any(f.get('cargo') for f in funcionarios)
        
        result['success'] = True
        
    except Exception as e:
        result['error'] = str(e)
    
    return result


def generate_metrics_table(results: List[Dict], output_path: str):
    """Genera tabla Markdown con métricas de todos los decretos"""
    md = []
    md.append("# Métricas de Extracción - Decretos 2009\n")
    md.append(f"**Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    md.append(f"**Total archivos:** {len(results)}\n")
    
    # Estadísticas resumen
    ok_count = sum(1 for r in results if r['success'])
    error_count = len(results) - ok_count
    nativo_count = sum(1 for r in results if r['metrics'].get('method') == 'NATIVO')
    ocr_count = sum(1 for r in results if r['metrics'].get('method') == 'OCR')
    
    md.append("\n## Resumen\n")
    md.append(f"| Métrica | Valor |")
    md.append(f"|---------|-------|")
    md.append(f"| Exitosos | {ok_count} ({ok_count/len(results)*100:.1f}%) |")
    md.append(f"| Con errores | {error_count} |")
    md.append(f"| Extracción Nativa | {nativo_count} |")
    md.append(f"| Extracción OCR | {ocr_count} |")
    
    # Códigos de novedad
    codigos = {}
    for r in results:
        if r['success']:
            codigo = r['metrics'].get('codigo', 'N/A')
            codigos[codigo] = codigos.get(codigo, 0) + 1
    
    md.append("\n## Distribución por Código de Novedad\n")
    md.append(f"| Código | Cantidad |")
    md.append(f"|--------|----------|")
    for codigo, count in sorted(codigos.items(), key=lambda x: -x[1]):
        md.append(f"| {codigo} | {count} |")
    
    # Tabla detallada
    md.append("\n## Detalle por Archivo\n")
    md.append("| # | Archivo | Método | Chars | Funcs | Cédulas | Cargos | Código | Decreto# | Razonamiento |")
    md.append("|---|---------|--------|-------|-------|---------|--------|--------|----------|--------------|")
    
    for i, r in enumerate(results, 1):
        m = r['metrics']
        status = "✅" if r['success'] else "❌"
        method = m.get('method', 'ERROR')[:6]
        chars = f"{m.get('chars', 0):,}"
        funcs = m.get('num_funcionarios', 0)
        cedulas = "✓" if m.get('tiene_cedulas') else "✗"
        cargos = "✓" if m.get('tiene_cargos') else "✗"
        codigo = m.get('codigo', 'N/A')[:10]
        decreto = m.get('numero_decreto', 'N/A')
        razon = (m.get('razonamiento', '') or '')[:50].replace('|', ' ').replace('\n', ' ')
        
        filename = r['filename'][:30]
        md.append(f"| {i} | {status} {filename} | {method} | {chars} | {funcs} | {cedulas} | {cargos} | {codigo} | {decreto} | {razon}... |")
    
    # Casos problemáticos
    problemas = [r for r in results if not r['success'] or r['metrics'].get('codigo') == 'PENDIENTE_REVISION']
    if problemas:
        md.append("\n## Casos Problemáticos (requieren revisión)\n")
        for r in problemas[:20]:
            md.append(f"- **{r['filename']}**: {r.get('error') or 'Código PENDIENTE_REVISION'}")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md))
    
    print(f"Tabla de métricas generada: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Extracción de decretos con métricas')
    parser.add_argument('--dir-in', type=str, default=DEFAULT_DIR, help='Directorio de entrada')
    parser.add_argument('--output-dir', type=str, default=OUTPUT_DIR, help='Directorio de salida')
    parser.add_argument('--limit', type=int, default=100, help='Límite de archivos')
    parser.add_argument('--skip-md', action='store_true', help='No generar archivos MD individuales')
    parser.add_argument('--skip-json', action='store_true', help='No generar archivos GraphRAG JSON')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("EXTRACCIÓN DE DECRETOS CON MÉTRICAS")
    print("=" * 60)
    print(f"Directorio entrada: {args.dir_in}")
    print(f"Directorio salida: {args.output_dir}")
    print(f"Límite: {args.limit}")
    print()
    
    # Crear directorio de salida
    ensure_dir(args.output_dir)
    ensure_dir(os.path.join(args.output_dir, 'md'))
    ensure_dir(os.path.join(args.output_dir, 'graphrag'))
    
    # Buscar PDFs
    pdf_files = []
    for f in sorted(os.listdir(args.dir_in)):
        if f.lower().endswith('.pdf'):
            pdf_files.append(os.path.join(args.dir_in, f))
    
    print(f"Encontrados: {len(pdf_files)} archivos PDF")
    
    if args.limit and args.limit < len(pdf_files):
        pdf_files = pdf_files[:args.limit]
        print(f"Limitado a: {args.limit} archivos")
    
    # Conectar BD (solo lectura del catálogo)
    conn = sqlite3.connect(DB_PATH)
    
    # Procesar
    results = []
    for i, filepath in enumerate(pdf_files):
        filename = os.path.basename(filepath)
        print(f"[{i+1}/{len(pdf_files)}] Procesando: {filename[:50]}...", end=" ")
        
        result = process_decree_with_metrics(filepath, conn)
        results.append(result)
        
        if result['success']:
            print(f"OK ({result['metrics'].get('method')}, {result['metrics'].get('codigo')})")
            
            # Generar MD individual
            if not args.skip_md:
                md_content = generate_markdown(
                    result['decree_name'], filepath,
                    result['text'], result['metrics']['method'],
                    result['extracted'], result['metrics']
                )
                md_path = os.path.join(args.output_dir, 'md', f"{result['decree_name']}.md")
                with open(md_path, 'w', encoding='utf-8') as f:
                    f.write(md_content)
            
            # Generar GraphRAG JSON
            if not args.skip_json:
                graphrag = generate_graphrag_json(
                    result['decree_name'], filepath,
                    result['extracted'], result['metrics']
                )
                json_path = os.path.join(args.output_dir, 'graphrag', f"{result['decree_name']}.graphrag.json")
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(graphrag, f, indent=2, ensure_ascii=False, default=str)
        else:
            print(f"ERROR: {result.get('error', 'Unknown')[:50]}")
    
    conn.close()
    
    # Generar tabla de métricas
    metrics_path = os.path.join(args.output_dir, 'extraction_metrics_2009.md')
    generate_metrics_table(results, metrics_path)
    
    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    ok = sum(1 for r in results if r['success'])
    print(f"Total procesados: {len(results)}")
    print(f"Exitosos: {ok} ({ok/len(results)*100:.1f}%)")
    print(f"Con errores: {len(results) - ok}")
    print(f"\nArchivos generados en: {args.output_dir}")
    print(f"  - MD individuales: {args.output_dir}/md/")
    print(f"  - GraphRAG JSON: {args.output_dir}/graphrag/")
    print(f"  - Tabla métricas: {metrics_path}")


if __name__ == "__main__":
    main()
