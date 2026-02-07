"""
Script para verificar que todos los archivos PDF de decretos y resoluciones
fueron procesados correctamente.
"""
import os
import json
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime

class VerificadorProcesamiento:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.decretos_no_procesados = []
        self.resoluciones_no_procesadas = []
        
    def obtener_pdfs_directorio(self, directorio: Path) -> List[Path]:
        """Obtiene todos los archivos PDF de un directorio."""
        if not directorio.exists():
            print(f"⚠️  Directorio no existe: {directorio}")
            return []
        
        pdfs = []
        for archivo in directorio.rglob("*.pdf"):
            if archivo.is_file():
                pdfs.append(archivo)
        return pdfs
    
    def obtener_archivos_procesados(self, output_dir: Path) -> set:
        """
        Obtiene el conjunto de nombres base de archivos procesados.
        Busca archivos .graphrag.json en el subdirectorio graphrag.
        """
        if not output_dir.exists():
            print(f"⚠️  Directorio de salida no existe: {output_dir}")
            return set()
        
        procesados = set()
        
        # Verificar en el subdirectorio graphrag
        graphrag_dir = output_dir / "graphrag"
        if graphrag_dir.exists() and graphrag_dir.is_dir():
            # Buscar archivos .graphrag.json
            for json_file in graphrag_dir.glob("*.graphrag.json"):
                if json_file.is_file():
                    # El nombre base es el nombre del archivo sin la extensión .graphrag.json
                    nombre_base = json_file.name.replace(".graphrag.json", "")
                    procesados.add(nombre_base)
        
        # También verificar otros posibles formatos de salida
        for json_file in output_dir.rglob("*.json"):
            if json_file.is_file() and not json_file.parent.name == "graphrag":
                nombre_base = json_file.stem
                # Limpiar sufijos comunes
                if nombre_base.endswith("_metadata"):
                    nombre_base = nombre_base[:-9]
                elif nombre_base.endswith("_extracted"):
                    nombre_base = nombre_base[:-10]
                elif nombre_base.endswith("_novedad"):
                    nombre_base = nombre_base[:-8]
                procesados.add(nombre_base)
        
        return procesados
    
    def verificar_decretos(self) -> Dict:
        """Verifica el procesamiento de decretos desde 2009 hasta 2025."""
        print("=" * 80)
        print("VERIFICACIÓN DE DECRETOS (2009-2025)")
        print("=" * 80)
        
        resultados = {
            'años_verificados': [],
            'no_procesados': [],
            'total_pdfs': 0,
            'total_procesados': 0,
            'total_no_procesados': 0
        }
        
        for año in range(2009, 2026):
            print(f"\n📅 Verificando año {año}...")
            
            # Directorio de entrada
            dir_decretos = self.base_dir / "Decretos" / str(año)
            # Directorio de salida
            output_dir = self.base_dir / f"output_{año}_hybrid"
            
            # Obtener PDFs del directorio
            pdfs = self.obtener_pdfs_directorio(dir_decretos)
            total_pdfs = len(pdfs)
            
            # Obtener archivos procesados
            procesados = self.obtener_archivos_procesados(output_dir)
            
            # Verificar cuáles no fueron procesados
            no_procesados = []
            for pdf in pdfs:
                nombre_sin_ext = pdf.stem
                # Verificar si el archivo está en procesados
                if nombre_sin_ext not in procesados:
                    no_procesados.append({
                        'archivo': pdf.name,
                        'ruta_completa': str(pdf),
                        'año': año,
                        'output_dir': str(output_dir)
                    })
            
            # Actualizar resultados
            resultados['años_verificados'].append(año)
            resultados['total_pdfs'] += total_pdfs
            resultados['total_procesados'] += (total_pdfs - len(no_procesados))
            resultados['total_no_procesados'] += len(no_procesados)
            resultados['no_procesados'].extend(no_procesados)
            
            print(f"   📄 Total PDFs: {total_pdfs}")
            print(f"   ✅ Procesados: {total_pdfs - len(no_procesados)}")
            print(f"   ❌ No procesados: {len(no_procesados)}")
            
            if no_procesados:
                print(f"   ⚠️  Archivos faltantes:")
                for item in no_procesados[:5]:  # Mostrar solo los primeros 5
                    print(f"      - {item['archivo']}")
                if len(no_procesados) > 5:
                    print(f"      ... y {len(no_procesados) - 5} más")
        
        self.decretos_no_procesados = resultados['no_procesados']
        return resultados
    
    def verificar_resoluciones(self) -> Dict:
        """Verifica el procesamiento de resoluciones 2023-2025."""
        print("\n" + "=" * 80)
        print("VERIFICACIÓN DE RESOLUCIONES (2023-2025)")
        print("=" * 80)
        
        resultados = {
            'años_verificados': [],
            'no_procesados': [],
            'total_pdfs': 0,
            'total_procesados': 0,
            'total_no_procesados': 0
        }
        
        # Configuración de directorios de resoluciones
        config_resoluciones = [
            {
                'año': 2023,
                'dir_in': self.base_dir / "Decretos" / "RESOLUCIONES -2023",
                'output_dir': self.base_dir / "output_res_2023"
            },
            {
                'año': 2024,
                'dir_in': self.base_dir / "Decretos" / "RESOLUCIONES 2024",
                'output_dir': self.base_dir / "output_res_2024"
            },
            {
                'año': 2025,
                'dir_in': self.base_dir / "Decretos" / "RESOLUCIONES 2025",
                'output_dir': self.base_dir / "output_res_2025"
            }
        ]
        
        for config in config_resoluciones:
            año = config['año']
            dir_in = config['dir_in']
            output_dir = config['output_dir']
            
            print(f"\n📅 Verificando resoluciones {año}...")
            
            # Obtener PDFs del directorio
            pdfs = self.obtener_pdfs_directorio(dir_in)
            total_pdfs = len(pdfs)
            
            # Obtener archivos procesados
            procesados = self.obtener_archivos_procesados(output_dir)
            
            # Verificar cuáles no fueron procesados
            no_procesados = []
            for pdf in pdfs:
                nombre_sin_ext = pdf.stem
                if nombre_sin_ext not in procesados:
                    no_procesados.append({
                        'archivo': pdf.name,
                        'ruta_completa': str(pdf),
                        'año': año,
                        'output_dir': str(output_dir)
                    })
            
            # Actualizar resultados
            resultados['años_verificados'].append(año)
            resultados['total_pdfs'] += total_pdfs
            resultados['total_procesados'] += (total_pdfs - len(no_procesados))
            resultados['total_no_procesados'] += len(no_procesados)
            resultados['no_procesados'].extend(no_procesados)
            
            print(f"   📄 Total PDFs: {total_pdfs}")
            print(f"   ✅ Procesados: {total_pdfs - len(no_procesados)}")
            print(f"   ❌ No procesados: {len(no_procesados)}")
            
            if no_procesados:
                print(f"   ⚠️  Archivos faltantes:")
                for item in no_procesados[:5]:
                    print(f"      - {item['archivo']}")
                if len(no_procesados) > 5:
                    print(f"      ... y {len(no_procesados) - 5} más")
        
        self.resoluciones_no_procesadas = resultados['no_procesados']
        return resultados
    
    def generar_log_decretos(self, output_file: str = "LOG_decretos.txt"):
        """Genera el archivo de log con decretos no procesados."""
        log_path = self.base_dir / output_file
        
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("LOG DE DECRETOS NO PROCESADOS\n")
            f.write(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            
            if not self.decretos_no_procesados:
                f.write("✅ Todos los decretos han sido procesados correctamente.\n")
            else:
                f.write(f"Total de archivos no procesados: {len(self.decretos_no_procesados)}\n\n")
                
                # Agrupar por año
                por_año = {}
                for item in self.decretos_no_procesados:
                    año = item['año']
                    if año not in por_año:
                        por_año[año] = []
                    por_año[año].append(item)
                
                for año in sorted(por_año.keys()):
                    f.write(f"\n{'=' * 80}\n")
                    f.write(f"AÑO {año} - {len(por_año[año])} archivos no procesados\n")
                    f.write(f"{'=' * 80}\n")
                    
                    for item in por_año[año]:
                        f.write(f"\nArchivo: {item['archivo']}\n")
                        f.write(f"Ruta: {item['ruta_completa']}\n")
                        f.write(f"Output: {item['output_dir']}\n")
                        f.write(f"Comando para procesar:\n")
                        f.write(f"  python extract_decretos.py --dir-in \"{Path(item['ruta_completa']).parent}\" ")
                        f.write(f"--llm gpt-oss:20b-cloud --output \"{item['output_dir']}\"\n")
                        f.write(f"{'-' * 80}\n")
        
        print(f"\n✅ Log generado: {log_path}")
        return log_path
    
    def generar_log_resoluciones(self, output_file: str = "LOG_resoluciones.txt"):
        """Genera el archivo de log con resoluciones no procesadas."""
        log_path = self.base_dir / output_file
        
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("LOG DE RESOLUCIONES NO PROCESADAS\n")
            f.write(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            
            if not self.resoluciones_no_procesadas:
                f.write("✅ Todas las resoluciones han sido procesadas correctamente.\n")
            else:
                f.write(f"Total de archivos no procesados: {len(self.resoluciones_no_procesadas)}\n\n")
                
                # Agrupar por año
                por_año = {}
                for item in self.resoluciones_no_procesadas:
                    año = item['año']
                    if año not in por_año:
                        por_año[año] = []
                    por_año[año].append(item)
                
                for año in sorted(por_año.keys()):
                    f.write(f"\n{'=' * 80}\n")
                    f.write(f"AÑO {año} - {len(por_año[año])} archivos no procesados\n")
                    f.write(f"{'=' * 80}\n")
                    
                    for item in por_año[año]:
                        f.write(f"\nArchivo: {item['archivo']}\n")
                        f.write(f"Ruta: {item['ruta_completa']}\n")
                        f.write(f"Output: {item['output_dir']}\n")
                        f.write(f"Comando para procesar:\n")
                        f.write(f"  python extract_resoluciones.py --dir-in \"{Path(item['ruta_completa']).parent}\" ")
                        f.write(f"--llm gpt-oss:120b-cloud --output \"{item['output_dir']}\"\n")
                        f.write(f"{'-' * 80}\n")
        
        print(f"\n✅ Log generado: {log_path}")
        return log_path
    
    def generar_reporte_json(self):
        """Genera un reporte en formato JSON con todos los resultados."""
        reporte = {
            'fecha_verificacion': datetime.now().isoformat(),
            'decretos': {
                'total_no_procesados': len(self.decretos_no_procesados),
                'archivos': self.decretos_no_procesados
            },
            'resoluciones': {
                'total_no_procesados': len(self.resoluciones_no_procesadas),
                'archivos': self.resoluciones_no_procesadas
            }
        }
        
        reporte_path = self.base_dir / "reporte_verificacion.json"
        with open(reporte_path, 'w', encoding='utf-8') as f:
            json.dump(reporte, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Reporte JSON generado: {reporte_path}")
        return reporte_path


def main():
    """Función principal."""
    base_dir = r"C:\temp\PNG_CERTIFICADO_V3"
    
    print("\n" + "🔍 INICIANDO VERIFICACIÓN DE PROCESAMIENTO " + "\n")
    
    verificador = VerificadorProcesamiento(base_dir)
    
    # Verificar decretos
    resultados_decretos = verificador.verificar_decretos()
    
    # Verificar resoluciones
    resultados_resoluciones = verificador.verificar_resoluciones()
    
    # Generar logs
    print("\n" + "=" * 80)
    print("GENERANDO LOGS")
    print("=" * 80)
    
    log_decretos = verificador.generar_log_decretos()
    log_resoluciones = verificador.generar_log_resoluciones()
    reporte_json = verificador.generar_reporte_json()
    
    # Resumen final
    print("\n" + "=" * 80)
    print("RESUMEN FINAL")
    print("=" * 80)
    print(f"\n📊 DECRETOS:")
    print(f"   Total PDFs: {resultados_decretos['total_pdfs']}")
    print(f"   ✅ Procesados: {resultados_decretos['total_procesados']}")
    print(f"   ❌ No procesados: {resultados_decretos['total_no_procesados']}")
    
    print(f"\n📊 RESOLUCIONES:")
    print(f"   Total PDFs: {resultados_resoluciones['total_pdfs']}")
    print(f"   ✅ Procesados: {resultados_resoluciones['total_procesados']}")
    print(f"   ❌ No procesados: {resultados_resoluciones['total_no_procesados']}")
    
    print(f"\n📁 Archivos generados:")
    print(f"   - {log_decretos}")
    print(f"   - {log_resoluciones}")
    print(f"   - {reporte_json}")
    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
