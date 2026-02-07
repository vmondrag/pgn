"""
Script para procesar automáticamente los archivos decretos y resoluciones no procesados.
Lee el reporte de verificación y procesa los archivos faltantes.
"""
import os
import json
import subprocess
from pathlib import Path
from typing import List, Dict
from datetime import datetime
import time


class ProcesadorFaltantes:
    def __init__(self, base_dir: str, reporte_path: str):
        self.base_dir = Path(base_dir)
        self.reporte_path = Path(reporte_path)
        self.log_file = self.base_dir / f"procesamiento_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
    def log(self, mensaje: str, print_console: bool = True):
        """Escribe mensaje en log y opcionalmente en consola."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        mensaje_completo = f"[{timestamp}] {mensaje}"
        
        if print_console:
            print(mensaje_completo)
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(mensaje_completo + '\n')
    
    def cargar_reporte(self) -> Dict:
        """Carga el reporte JSON de verificación."""
        if not self.reporte_path.exists():
            raise FileNotFoundError(f"No se encontró el reporte: {self.reporte_path}")
        
        with open(self.reporte_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def proceso_decretos_decretos(self, reporte: Dict) -> Dict[str, int]:
        """Procesa todos los decretos no procesados."""
        self.log("\n" + "="*80)
        self.log("PROCESANDO DECRETOS FALTANTES")
        self.log("="*80)
        
        decretos = reporte.get('decretos', {})
        archivos_no_procesados = decretos.get('archivos', [])
        
        if not archivos_no_procesados:
            self.log("✅ No hay decretos pendientes de procesar")
            return {'total': 0, 'exitosos': 0, 'fallidos': 0}
        
        total = len(archivos_no_procesados)
        
        self.log(f"📊 Total de decretos a procesar: {total}\n")
        
        # Agrupar por directorio de origen y output para procesarlos por lotes
        por_configuracion = {}
        for item in archivos_no_procesados:
            dir_origen = str(Path(item['ruta_completa']).parent)
            output_dir = item['output_dir']
            
            key = (dir_origen, output_dir)
            if key not in por_configuracion:
                por_configuracion[key] = {
                    'año': item['año'],
                    'dir_in': dir_origen,
                    'output_dir': output_dir,
                    'archivos': []
                }
            por_configuracion[key]['archivos'].append(item)
        
        self.log(f"\n📂 Se procesarán {len(por_configuracion)} directorios\n")
        
        exitosos = 0
        fallidos = 0
        
        # Procesar cada directorio
        for idx, (key, config) in enumerate(por_configuracion.items(), 1):
            año = config['año']
            dir_in = config['dir_in']
            output_dir = config['output_dir']
            archivos_dir = config['archivos']
            
            self.log(f"\n[{idx}/{len(por_configuracion)}] Procesando Año {año}")
            self.log(f"   Directorio: {dir_in}")
            self.log(f"   Output: {output_dir}")
            self.log(f"   Archivos faltantes: {len(archivos_dir)}")
            
            # Log de los primeros archivos
            for i, item in enumerate(archivos_dir[:5], 1):
                self.log(f"      {i}. {item['archivo']}")
            if len(archivos_dir) > 5:
                self.log(f"      ... y {len(archivos_dir) - 5} más")
            
            # Construir comando para procesar el directorio completo
            comando = [
                "python",
                "extract_decretos.py",
                "--dir-in",
                dir_in,
                "--llm",
                "gpt-oss:20b-cloud",
                "--output",
                output_dir
            ]
            
            self.log(f"\n   🔄 Ejecutando procesamiento...")
            self.log(f"      Comando: {' '.join(comando)}", print_console=False)
            
            try:
                resultado = subprocess.run(
                    comando,
                    cwd=str(self.base_dir),
                    capture_output=True,
                    text=True,
                    timeout=3600  # 1 hora timeout para directorios grandes
                )
                
                if resultado.returncode == 0:
                    self.log(f"   ✅ Procesamiento completado para año {año}")
                    exitosos += len(archivos_dir)
                else:
                    self.log(f"   ❌ Error procesando año {año}")
                    self.log(f"      Error: {resultado.stderr[:500]}", print_console=False)
                    fallidos += len(archivos_dir)
            
            except subprocess.TimeoutExpired:
                self.log(f"   ⏱️  Timeout procesando año {año}")
                fallidos += len(archivos_dir)
            except Exception as e:
                self.log(f"   ❌ Excepción procesando año {año}: {str(e)}")
                fallidos += len(archivos_dir)
        
        self.log(f"\n{'='*80}")
        self.log(f"RESUMEN DECRETOS:")
        self.log(f"  Total archivos: {total}")
        self.log(f"  ✅ Procesados: {exitosos}")
        self.log(f"  ❌ Fallidos: {fallidos}")
        self.log(f"{'='*80}\n")
        
        return {'total': total, 'exitosos': exitosos, 'fallidos': fallidos}
    
    def procesar_resoluciones(self, reporte: Dict) -> Dict[str, int]:
        """Procesa todas las resoluciones no procesadas."""
        self.log("\n" + "="*80)
        self.log("PROCESANDO RESOLUCIONES FALTANTES")
        self.log("="*80)
        
        resoluciones = reporte.get('resoluciones', {})
        archivos_no_procesados = resoluciones.get('archivos', [])
        
        if not archivos_no_procesados:
            self.log("✅ No hay resoluciones pendientes de procesar")
            return {'total': 0, 'exitosos': 0, 'fallidos': 0}
        
        total = len(archivos_no_procesados)
        exitosos = 0
        fallidos = 0
        
        self.log(f"📊 Total de resoluciones a procesar: {total}\n")
        
        # Agrupar por año
        por_año = {}
        for item in archivos_no_procesados:
            año = item['año']
            if año not in por_año:
                por_año[año] = []
            por_año[año].append(item)
        
        # Procesar por año
        for año in sorted(por_año.keys()):
            archivos_año = por_año[año]
            self.log(f"\n📅 Procesando año {año} ({len(archivos_año)} archivos)")
            self.log("-" * 80)
            
            for idx, item in enumerate(archivos_año, 1):
                self.log(f"\n[{idx}/{len(archivos_año)}] Archivo: {item['archivo']}")
                
                # Procesar archivo
                if self.procesar_archivo(
                    pdf_path=item['ruta_completa'],
                    script="extract_resoluciones.py",
                    output_dir=item['output_dir'],
                    llm="gpt-oss:120b-cloud"
                ):
                    exitosos += 1
                else:
                    fallidos += 1
                
                # Pequeña pausa entre archivos
                time.sleep(0.5)
        
        self.log(f"\n{'='*80}")
        self.log(f"RESUMEN RESOLUCIONES:")
        self.log(f"  Total: {total}")
        self.log(f"  ✅ Exitosos: {exitosos}")
        self.log(f"  ❌ Fallidos: {fallidos}")
        self.log(f"{'='*80}\n")
        
        return {'total': total, 'exitosos': exitosos, 'fallidos': fallidos}
    
    def procesar_todo(self):
        """Procesa todos los archivos pendientes (decretos y resoluciones)."""
        self.log("="*80)
        self.log("INICIANDO PROCESAMIENTO DE ARCHIVOS FALTANTES")
        self.log(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log(f"Log file: {self.log_file}")
        self.log("="*80)
        
        # Cargar reporte
        try:
            reporte = self.cargar_reporte()
            self.log(f"✅ Reporte cargado desde: {self.reporte_path}\n")
        except Exception as e:
            self.log(f"❌ Error al cargar reporte: {e}")
            return
        
        # Procesar decretos
        resultado_decretos = self.procesar_decretos(reporte)
        
        # Procesar resoluciones
        resultado_resoluciones = self.procesar_resoluciones(reporte)
        
        # Resumen final
        self.log("\n" + "="*80)
        self.log("RESUMEN FINAL DEL PROCESAMIENTO")
        self.log("="*80)
        self.log(f"\n📊 DECRETOS:")
        self.log(f"   Total procesado: {resultado_decretos['total']}")
        self.log(f"   ✅ Exitosos: {resultado_decretos['exitosos']}")
        self.log(f"   ❌ Fallidos: {resultado_decretos['fallidos']}")
        
        self.log(f"\n📊 RESOLUCIONES:")
        self.log(f"   Total procesado: {resultado_resoluciones['total']}")
        self.log(f"   ✅ Exitosos: {resultado_resoluciones['exitosos']}")
        self.log(f"   ❌ Fallidos: {resultado_resoluciones['fallidos']}")
        
        total_general = resultado_decretos['total'] + resultado_resoluciones['total']
        exitosos_general = resultado_decretos['exitosos'] + resultado_resoluciones['exitosos']
        fallidos_general = resultado_decretos['fallidos'] + resultado_resoluciones['fallidos']
        
        self.log(f"\n📊 TOTAL GENERAL:")
        self.log(f"   Total procesado: {total_general}")
        self.log(f"   ✅ Exitosos: {exitosos_general} ({(exitosos_general/total_general*100):.1f}%)")
        self.log(f"   ❌ Fallidos: {fallidos_general} ({(fallidos_general/total_general*100):.1f}%)")
        
        self.log(f"\n📁 Log guardado en: {self.log_file}")
        self.log("="*80)


def main():
    """Función principal."""
    base_dir = r"C:\temp\PNG_CERTIFICADO_V3"
    reporte_path = r"C:\temp\PNG_CERTIFICADO_V3\reporte_verificacion.json"
    
    procesador = ProcesadorFaltantes(base_dir, reporte_path)
    procesador.procesar_todo()


if __name__ == "__main__":
    main()
