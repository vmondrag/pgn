"""
Prueba de Azure OpenAI con decretos huérfanos
Sin registrar en base de datos
"""
import os
import sqlite3
import json
import re
from openai import AzureOpenAI

# Configuración Azure
AZURE_ENDPOINT = "https://iacertificaciones.cognitiveservices.azure.com/"
AZURE_API_KEY = os.environ.get("AZURE_API_KEY", "")
AZURE_API_VERSION = "2024-12-01-preview"
AZURE_MODEL = "gpt-5-mini"

DB_PATH = r"C:\temp\PNG_CERTIFICADO_V3\novedades_pgn.db"


def test_azure_openai(texto_ocr: str, numero: str, anio: int):
    """Prueba Azure OpenAI con un decreto"""
    
    prompt = f"""Eres un experto legal en decretos de la Procuraduria General de la Nacion de Colombia.

=== DECRETO ===
Numero: {numero}
Anio: {anio}

=== TEXTO OCR ===
{texto_ocr[:3000]}

=== INSTRUCCIONES ===
1. Identifica errores OCR (palabras pegadas)
2. Determina el tipo de novedad (N=Nombramiento, E=Encargo, R=Renuncia, ASIG=Asignacion, PROR=Prorroga, MD=Modificacion)
3. Extrae funcionarios con cedula
4. Persona sin cedula = reemplazada (no es funcionario)

Responde SOLO con JSON:
{{
    "razonamiento": "explicacion paso a paso",
    "codigo_novedad": "N/E/R/ASIG/PROR/MD",
    "tipo_novedad": "descripcion",
    "funcionarios": [{{"cedula": "...", "nombre_completo": "...", "cargo": "..."}}],
    "persona_reemplazada": "nombre si aplica",
    "resumen": "breve descripcion"
}}"""

    try:
        client = AzureOpenAI(
            api_version=AZURE_API_VERSION,
            azure_endpoint=AZURE_ENDPOINT,
            api_key=AZURE_API_KEY,
        )
        
        response = client.chat.completions.create(
            model=AZURE_MODEL,
            messages=[
                {"role": "system", "content": "Eres un experto en analisis de decretos de la PGN Colombia."},
                {"role": "user", "content": prompt}
            ],
            max_completion_tokens=1500
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        return f"ERROR: {e}"


def main():
    print("=" * 70)
    print("PRUEBA AZURE OPENAI - GPT-5-MINI")
    print("=" * 70)
    print(f"Endpoint: {AZURE_ENDPOINT}")
    print(f"Modelo: {AZURE_MODEL}")
    print()
    
    # Obtener 2 decretos huérfanos aleatorios
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT d.numero_decreto, d.anio, d.contenido_texto, d.archivo_origen
        FROM decretos d
        WHERE NOT EXISTS (SELECT 1 FROM novedades n WHERE n.decreto_id = d.id)
        AND d.contenido_texto IS NOT NULL 
        AND LENGTH(d.contenido_texto) > 200
        ORDER BY RANDOM()
        LIMIT 2
    ''')
    
    decretos = cursor.fetchall()
    conn.close()
    
    print(f"Decretos seleccionados: {len(decretos)}")
    print()
    
    for i, (numero, anio, texto, archivo) in enumerate(decretos):
        print("=" * 70)
        print(f"DECRETO #{i+1}: {numero}-{anio}")
        print(f"Archivo: {archivo}")
        print("-" * 70)
        print("TEXTO OCR (primeros 400 chars):")
        print(texto[:400] if texto else "(sin texto)")
        print()
        print("-" * 70)
        print("RESPUESTA AZURE OPENAI:")
        print("-" * 70)
        
        respuesta = test_azure_openai(texto, numero, anio)
        
        # Intentar parsear JSON
        try:
            match = re.search(r'\{[\s\S]*\}', respuesta)
            if match:
                data = json.loads(match.group())
                print(f"Codigo: {data.get('codigo_novedad')}")
                print(f"Tipo: {data.get('tipo_novedad')}")
                print(f"Razonamiento: {data.get('razonamiento', '')[:200]}...")
                print(f"Funcionarios: {len(data.get('funcionarios', []))}")
                for f in data.get('funcionarios', []):
                    print(f"  - {f.get('nombre_completo')} (CC: {f.get('cedula')})")
                print(f"Persona reemplazada: {data.get('persona_reemplazada')}")
                print(f"Resumen: {data.get('resumen')}")
            else:
                print(respuesta)
        except:
            print(respuesta)
        
        print()


if __name__ == "__main__":
    main()
