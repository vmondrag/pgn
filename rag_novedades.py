"""
RAG Híbrido para Novedades PGN
Combina búsqueda semántica (embeddings Azure OpenAI) con consultas estructuradas (SQLite)

Configuración requerida en .env:
    AZURE_OPENAI_ENDPOINT=https://tu-recurso.openai.azure.com/
    AZURE_OPENAI_KEY=tu-api-key
    AZURE_EMBEDDING_DEPLOYMENT=text-embedding-ada-002
    AZURE_CHAT_DEPLOYMENT=gpt-4o-mini
    AZURE_API_VERSION=2024-02-15-preview
"""

import os
import json
import sqlite3
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

# Cargar variables de entorno
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ChromaDB para vector store local
try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    print("ADVERTENCIA: ChromaDB no instalado. Ejecutar: pip install chromadb")

# Azure OpenAI
try:
    from openai import AzureOpenAI
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    print("ADVERTENCIA: openai no instalado. Ejecutar: pip install openai>=1.0.0")


@dataclass
class DocumentChunk:
    """Representa un fragmento de documento para indexar"""
    id: str
    content: str
    metadata: Dict
    source_file: str
    chunk_type: str  # 'razonamiento', 'ocr', 'resumen', 'json'


@dataclass
class SearchResult:
    """Resultado de búsqueda híbrida"""
    content: str
    score: float
    source: str
    metadata: Dict
    search_type: str  # 'semantic' o 'structured'


class RAGNovedades:
    """
    Sistema RAG híbrido para consultas de novedades PGN.
    Combina:
    - Búsqueda semántica: embeddings de razonamientos LLM y textos OCR
    - Búsqueda estructurada: consultas SQL en SQLite
    """

    def __init__(
        self,
        db_path: str = r"C:\temp\PNG_CERTIFICADO_V3\novedades_pgn.db",
        md_base_path: str = r"C:\temp\PNG_CERTIFICADO_V3\Novedades_OUT",
        chroma_persist_dir: str = r"C:\temp\PNG_CERTIFICADO_V3\chroma_db",
        collection_name: str = "novedades_pgn"
    ):
        self.db_path = db_path
        self.md_base_path = Path(md_base_path)
        self.chroma_persist_dir = chroma_persist_dir
        self.collection_name = collection_name

        # Configuración Azure OpenAI
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.azure_key = os.getenv("AZURE_OPENAI_KEY")
        self.embedding_deployment = os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
        self.chat_deployment = os.getenv("AZURE_CHAT_DEPLOYMENT", "gpt-4o-mini")
        self.api_version = os.getenv("AZURE_API_VERSION", "2024-02-15-preview")

        # Fallback a OpenAI directo si no hay Azure configurado
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.use_azure = bool(self.azure_endpoint and self.azure_key)

        # Inicializar clientes
        self._init_clients()
        self._init_chroma()

    def _init_clients(self):
        """Inicializar cliente de OpenAI (Azure o directo)"""
        if self.use_azure and AZURE_AVAILABLE:
            self.client = AzureOpenAI(
                azure_endpoint=self.azure_endpoint,
                api_key=self.azure_key,
                api_version=self.api_version
            )
            print(f"✓ Usando Azure OpenAI: {self.azure_endpoint}")
        elif self.openai_key and AZURE_AVAILABLE:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.openai_key)
            self.use_azure = False
            print("✓ Usando OpenAI directo (fallback)")
        else:
            self.client = None
            print("✗ No hay cliente de OpenAI configurado")

    def _init_chroma(self):
        """Inicializar ChromaDB"""
        if not CHROMA_AVAILABLE:
            self.chroma_client = None
            self.collection = None
            return

        # Crear directorio si no existe
        os.makedirs(self.chroma_persist_dir, exist_ok=True)

        self.chroma_client = chromadb.PersistentClient(
            path=self.chroma_persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )

        # Obtener o crear colección
        self.collection = self.chroma_client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "Novedades PGN - Decretos y Resoluciones"}
        )

        count = self.collection.count()
        print(f"✓ ChromaDB inicializado: {count} documentos indexados")

    def get_db(self) -> sqlite3.Connection:
        """Conexión a SQLite"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ==================== EMBEDDINGS ====================

    def get_embedding(self, text: str) -> List[float]:
        """Obtener embedding de un texto"""
        if not self.client:
            raise RuntimeError("Cliente OpenAI no configurado")

        # Truncar texto si es muy largo (límite ~8000 tokens)
        text = text[:30000] if len(text) > 30000 else text

        if self.use_azure:
            response = self.client.embeddings.create(
                input=text,
                model=self.embedding_deployment
            )
        else:
            response = self.client.embeddings.create(
                input=text,
                model="text-embedding-3-small"
            )

        return response.data[0].embedding

    def get_embeddings_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """Obtener embeddings en lote"""
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            # Truncar cada texto
            batch = [t[:30000] if len(t) > 30000 else t for t in batch]

            if self.use_azure:
                response = self.client.embeddings.create(
                    input=batch,
                    model=self.embedding_deployment
                )
            else:
                response = self.client.embeddings.create(
                    input=batch,
                    model="text-embedding-3-small"
                )

            all_embeddings.extend([e.embedding for e in response.data])

            if (i + batch_size) % 1000 == 0:
                print(f"  Procesados {i + batch_size} embeddings...")

        return all_embeddings

    # ==================== INDEXACIÓN ====================

    def parse_md_file(self, md_path: Path) -> List[DocumentChunk]:
        """Parsear un archivo MD y extraer chunks indexables"""
        chunks = []

        try:
            content = md_path.read_text(encoding='utf-8')
        except Exception as e:
            print(f"Error leyendo {md_path}: {e}")
            return chunks

        # Extraer metadata del nombre del archivo
        filename = md_path.stem
        file_id = hashlib.md5(str(md_path).encode()).hexdigest()[:12]

        # Extraer año del path
        year = None
        for part in md_path.parts:
            if part.startswith("output_") and "_hybrid" in part:
                try:
                    year = int(part.split("_")[1])
                except:
                    pass

        # Metadata base
        base_metadata = {
            "filename": filename,
            "year": year,
            "file_path": str(md_path)
        }

        # 1. Extraer Razonamiento LLM
        if "## Razonamiento LLM" in content:
            start = content.find("## Razonamiento LLM")
            end = content.find("\n## ", start + 20)
            razonamiento = content[start:end if end > 0 else start + 2000]
            razonamiento = razonamiento.replace("## Razonamiento LLM", "").strip()
            razonamiento = razonamiento.strip("> \n")

            if razonamiento and len(razonamiento) > 50:
                chunks.append(DocumentChunk(
                    id=f"{file_id}_razonamiento",
                    content=razonamiento,
                    metadata={**base_metadata, "chunk_type": "razonamiento"},
                    source_file=str(md_path),
                    chunk_type="razonamiento"
                ))

        # 2. Extraer JSON estructurado
        if "```json" in content:
            try:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
                json_data = json.loads(json_str)

                # Crear texto indexable del JSON
                json_text = f"""
                Decreto {json_data.get('numero_decreto', 'N/A')}-{json_data.get('anio', 'N/A')}
                Tipo: {json_data.get('tipo_novedad', 'N/A')} ({json_data.get('codigo_novedad', 'N/A')})
                Fecha: {json_data.get('fecha_texto', 'N/A')}
                Resumen: {json_data.get('resumen', 'N/A')}
                """

                # Agregar funcionarios
                for func in json_data.get('funcionarios', []):
                    json_text += f"""
                    Funcionario: {func.get('nombre_completo', 'N/A')}
                    Cédula: {func.get('cedula', 'N/A')}
                    Cargo: {func.get('cargo', 'N/A')}
                    Dependencia: {func.get('dependencia', 'N/A')}
                    """

                chunks.append(DocumentChunk(
                    id=f"{file_id}_json",
                    content=json_text.strip(),
                    metadata={
                        **base_metadata,
                        "chunk_type": "json",
                        "numero_decreto": json_data.get('numero_decreto'),
                        "codigo_novedad": json_data.get('codigo_novedad'),
                        "tipo_novedad": json_data.get('tipo_novedad')
                    },
                    source_file=str(md_path),
                    chunk_type="json"
                ))
            except json.JSONDecodeError:
                pass

        # 3. Extraer Texto OCR (si es corto, útil para búsqueda)
        if "## Texto OCR" in content:
            start = content.find("```text", content.find("## Texto OCR"))
            if start > 0:
                start += 7
                end = content.find("```", start)
                ocr_text = content[start:end].strip()

                # Solo indexar si tiene contenido sustancial pero no es demasiado largo
                if 100 < len(ocr_text) < 5000:
                    chunks.append(DocumentChunk(
                        id=f"{file_id}_ocr",
                        content=ocr_text,
                        metadata={**base_metadata, "chunk_type": "ocr"},
                        source_file=str(md_path),
                        chunk_type="ocr"
                    ))

        # 4. Extraer Resumen
        if "## Resumen" in content:
            start = content.find("## Resumen") + 10
            end = content.find("\n## ", start)
            resumen = content[start:end if end > 0 else start + 500].strip()

            if resumen and len(resumen) > 20:
                chunks.append(DocumentChunk(
                    id=f"{file_id}_resumen",
                    content=resumen,
                    metadata={**base_metadata, "chunk_type": "resumen"},
                    source_file=str(md_path),
                    chunk_type="resumen"
                ))

        return chunks

    def index_all_documents(self, force_reindex: bool = False):
        """Indexar todos los documentos MD en ChromaDB"""
        if not CHROMA_AVAILABLE or not self.collection:
            print("ChromaDB no disponible")
            return

        if not self.client:
            print("Cliente OpenAI no configurado - no se pueden generar embeddings")
            return

        # Verificar si ya hay documentos indexados
        current_count = self.collection.count()
        if current_count > 0 and not force_reindex:
            print(f"Ya hay {current_count} documentos indexados. Usar force_reindex=True para reindexar.")
            return

        if force_reindex and current_count > 0:
            print(f"Eliminando {current_count} documentos existentes...")
            # Eliminar colección y recrear
            self.chroma_client.delete_collection(self.collection_name)
            self.collection = self.chroma_client.create_collection(
                name=self.collection_name,
                metadata={"description": "Novedades PGN - Decretos y Resoluciones"}
            )

        # Encontrar todos los archivos MD
        md_files = list(self.md_base_path.rglob("*/md/*.md"))
        print(f"Encontrados {len(md_files)} archivos MD para indexar")

        # Procesar en lotes
        batch_size = 100
        all_chunks = []

        print("Parseando archivos MD...")
        for i, md_path in enumerate(md_files):
            chunks = self.parse_md_file(md_path)
            all_chunks.extend(chunks)

            if (i + 1) % 1000 == 0:
                print(f"  Parseados {i + 1}/{len(md_files)} archivos ({len(all_chunks)} chunks)")

        print(f"Total chunks a indexar: {len(all_chunks)}")

        # Generar embeddings e insertar en ChromaDB
        print("Generando embeddings...")
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i:i + batch_size]

            texts = [c.content for c in batch]
            ids = [c.id for c in batch]
            metadatas = [c.metadata for c in batch]

            try:
                embeddings = self.get_embeddings_batch(texts, batch_size=batch_size)

                self.collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    documents=texts,
                    metadatas=metadatas
                )

                if (i + batch_size) % 1000 == 0:
                    print(f"  Indexados {i + batch_size}/{len(all_chunks)} chunks")

            except Exception as e:
                print(f"Error indexando batch {i}: {e}")
                continue

        final_count = self.collection.count()
        print(f"✓ Indexación completada: {final_count} documentos en ChromaDB")

    # ==================== BÚSQUEDA ====================

    def semantic_search(
        self,
        query: str,
        n_results: int = 10,
        filter_metadata: Optional[Dict] = None
    ) -> List[SearchResult]:
        """Búsqueda semántica usando embeddings"""
        if not self.collection or self.collection.count() == 0:
            return []

        if not self.client:
            print("Cliente OpenAI no configurado")
            return []

        # Obtener embedding de la consulta
        query_embedding = self.get_embedding(query)

        # Buscar en ChromaDB
        where_filter = filter_metadata if filter_metadata else None

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )

        search_results = []
        for i in range(len(results['ids'][0])):
            # Convertir distancia a score (ChromaDB usa distancia L2)
            distance = results['distances'][0][i] if results['distances'] else 0
            score = 1 / (1 + distance)  # Convertir a score 0-1

            search_results.append(SearchResult(
                content=results['documents'][0][i],
                score=score,
                source=results['metadatas'][0][i].get('file_path', 'unknown'),
                metadata=results['metadatas'][0][i],
                search_type='semantic'
            ))

        return search_results

    def structured_search(
        self,
        cedula: Optional[str] = None,
        nombre: Optional[str] = None,
        codigo_novedad: Optional[str] = None,
        anio: Optional[int] = None,
        decreto: Optional[str] = None,
        limit: int = 20
    ) -> List[SearchResult]:
        """Búsqueda estructurada en SQLite"""
        conn = self.get_db()
        cursor = conn.cursor()

        query = '''
            SELECT
                f.cedula,
                f.nombre_completo,
                n.codigo_novedad,
                n.tipo_novedad,
                n.cargo_actual,
                n.dependencia,
                n.observaciones,
                d.numero_decreto,
                d.fecha_decreto_texto,
                d.anio,
                d.contenido_texto,
                d.razonamiento_llm,
                d.ruta_completa
            FROM novedades n
            LEFT JOIN funcionarios f ON n.funcionario_id = f.id
            LEFT JOIN decretos d ON n.decreto_id = d.id
            WHERE 1=1
        '''
        params = []

        if cedula:
            query += ' AND f.cedula LIKE ?'
            params.append(f'%{cedula}%')

        if nombre:
            query += ' AND f.nombre_completo LIKE ?'
            params.append(f'%{nombre}%')

        if codigo_novedad:
            query += ' AND n.codigo_novedad = ?'
            params.append(codigo_novedad)

        if anio:
            query += ' AND d.anio = ?'
            params.append(anio)

        if decreto:
            query += ' AND d.numero_decreto LIKE ?'
            params.append(f'%{decreto}%')

        query += ' ORDER BY d.anio DESC LIMIT ?'
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            content = f"""
            Funcionario: {row['nombre_completo'] or 'N/A'} (CC: {row['cedula'] or 'N/A'})
            Novedad: {row['tipo_novedad']} ({row['codigo_novedad']})
            Decreto: {row['numero_decreto']}-{row['anio']}
            Cargo: {row['cargo_actual'] or 'N/A'}
            Dependencia: {row['dependencia'] or 'N/A'}
            Fecha: {row['fecha_decreto_texto'] or 'N/A'}
            """

            if row['razonamiento_llm']:
                content += f"\nRazonamiento: {row['razonamiento_llm'][:500]}..."

            results.append(SearchResult(
                content=content.strip(),
                score=1.0,  # Coincidencia exacta
                source=row['ruta_completa'] or 'database',
                metadata={
                    'cedula': row['cedula'],
                    'nombre': row['nombre_completo'],
                    'codigo_novedad': row['codigo_novedad'],
                    'decreto': row['numero_decreto'],
                    'anio': row['anio']
                },
                search_type='structured'
            ))

        return results

    def hybrid_search(
        self,
        query: str,
        cedula: Optional[str] = None,
        nombre: Optional[str] = None,
        codigo_novedad: Optional[str] = None,
        anio: Optional[int] = None,
        n_semantic: int = 5,
        n_structured: int = 5
    ) -> List[SearchResult]:
        """
        Búsqueda híbrida combinando semántica y estructurada.
        Útil para consultas en lenguaje natural que también tienen filtros específicos.
        """
        results = []

        # 1. Búsqueda semántica si hay query de texto
        if query and len(query) > 5:
            filter_meta = {}
            if anio:
                filter_meta['year'] = anio
            if codigo_novedad:
                filter_meta['codigo_novedad'] = codigo_novedad

            semantic_results = self.semantic_search(
                query=query,
                n_results=n_semantic,
                filter_metadata=filter_meta if filter_meta else None
            )
            results.extend(semantic_results)

        # 2. Búsqueda estructurada si hay filtros específicos
        if cedula or nombre or codigo_novedad or anio:
            structured_results = self.structured_search(
                cedula=cedula,
                nombre=nombre,
                codigo_novedad=codigo_novedad,
                anio=anio,
                limit=n_structured
            )
            results.extend(structured_results)

        # 3. Deduplicar y ordenar por score
        seen = set()
        unique_results = []
        for r in results:
            key = (r.metadata.get('cedula', ''), r.metadata.get('decreto', ''))
            if key not in seen:
                seen.add(key)
                unique_results.append(r)

        # Ordenar: semánticos primero (por score), luego estructurados
        unique_results.sort(key=lambda x: (x.search_type != 'semantic', -x.score))

        return unique_results

    # ==================== GENERACIÓN RAG ====================

    def generate_answer(
        self,
        question: str,
        context_results: List[SearchResult],
        system_prompt: Optional[str] = None
    ) -> str:
        """Generar respuesta usando contexto recuperado"""
        if not self.client:
            return "Error: Cliente OpenAI no configurado"

        # Construir contexto
        context_parts = []
        for i, result in enumerate(context_results[:10], 1):
            context_parts.append(f"[Documento {i}]\n{result.content}\n")

        context = "\n---\n".join(context_parts)

        default_system = """Eres un asistente experto en novedades de personal de la Procuraduría General de la Nación de Colombia.
Tu función es responder preguntas basándote en los documentos de decretos y resoluciones proporcionados.

Reglas:
1. Responde SOLO con información que esté en los documentos proporcionados
2. Si no encuentras la información, indícalo claramente
3. Cita el número de decreto/resolución cuando menciones datos específicos
4. Usa formato estructurado para listas de funcionarios o novedades
5. Si hay múltiples resultados relevantes, resúmelos de forma clara"""

        messages = [
            {"role": "system", "content": system_prompt or default_system},
            {"role": "user", "content": f"""Contexto de documentos:
{context}

Pregunta del usuario: {question}

Responde basándote únicamente en el contexto proporcionado."""}
        ]

        try:
            if self.use_azure:
                response = self.client.chat.completions.create(
                    model=self.chat_deployment,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=2000
                )
            else:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.3,
                    max_tokens=2000
                )

            return response.choices[0].message.content

        except Exception as e:
            return f"Error generando respuesta: {str(e)}"

    def query(
        self,
        question: str,
        cedula: Optional[str] = None,
        nombre: Optional[str] = None,
        codigo_novedad: Optional[str] = None,
        anio: Optional[int] = None
    ) -> Dict:
        """
        Método principal: consulta RAG completa.
        Combina búsqueda híbrida + generación de respuesta.
        """
        # 1. Búsqueda híbrida
        results = self.hybrid_search(
            query=question,
            cedula=cedula,
            nombre=nombre,
            codigo_novedad=codigo_novedad,
            anio=anio,
            n_semantic=7,
            n_structured=5
        )

        # 2. Generar respuesta
        answer = self.generate_answer(question, results)

        # 3. Preparar fuentes
        sources = []
        for r in results[:10]:
            sources.append({
                'content_preview': r.content[:200] + '...' if len(r.content) > 200 else r.content,
                'score': round(r.score, 3),
                'source': r.source,
                'search_type': r.search_type,
                'metadata': r.metadata
            })

        return {
            'question': question,
            'answer': answer,
            'sources': sources,
            'filters_applied': {
                'cedula': cedula,
                'nombre': nombre,
                'codigo_novedad': codigo_novedad,
                'anio': anio
            },
            'total_results': len(results)
        }

    # ==================== ESTADÍSTICAS ====================

    def get_stats(self) -> Dict:
        """Obtener estadísticas del sistema RAG"""
        stats = {
            'chroma_documents': 0,
            'sqlite_decretos': 0,
            'sqlite_funcionarios': 0,
            'sqlite_novedades': 0,
            'azure_configured': self.use_azure,
            'client_available': self.client is not None
        }

        if self.collection:
            stats['chroma_documents'] = self.collection.count()

        conn = self.get_db()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM decretos')
        stats['sqlite_decretos'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM funcionarios')
        stats['sqlite_funcionarios'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM novedades')
        stats['sqlite_novedades'] = cursor.fetchone()[0]

        conn.close()

        return stats


# ==================== INTEGRACIÓN CON FLASK ====================

def create_rag_routes(app, rag: RAGNovedades):
    """Agregar rutas RAG a la aplicación Flask existente"""
    from flask import request, jsonify

    @app.route('/api/rag/query', methods=['POST'])
    def rag_query():
        """Endpoint principal de consulta RAG"""
        data = request.get_json()
        if not data or not data.get('question'):
            return jsonify({'error': 'Se requiere el campo "question"'}), 400

        try:
            result = rag.query(
                question=data.get('question'),
                cedula=data.get('cedula'),
                nombre=data.get('nombre'),
                codigo_novedad=data.get('codigo_novedad'),
                anio=data.get('anio')
            )
            return jsonify(result)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/rag/search', methods=['GET'])
    def rag_search():
        """Endpoint de búsqueda semántica simple"""
        query = request.args.get('q', '')
        n_results = int(request.args.get('n', 10))

        if not query:
            return jsonify({'error': 'Se requiere parámetro "q"'}), 400

        try:
            results = rag.semantic_search(query, n_results=n_results)
            return jsonify({
                'query': query,
                'results': [
                    {
                        'content': r.content[:500],
                        'score': round(r.score, 3),
                        'metadata': r.metadata
                    }
                    for r in results
                ]
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/rag/stats')
    def rag_stats():
        """Estadísticas del sistema RAG"""
        return jsonify(rag.get_stats())

    @app.route('/api/rag/index', methods=['POST'])
    def rag_index():
        """Iniciar indexación (solo admin)"""
        data = request.get_json() or {}
        force = data.get('force', False)

        try:
            rag.index_all_documents(force_reindex=force)
            return jsonify({
                'success': True,
                'message': 'Indexación completada',
                'documents': rag.collection.count() if rag.collection else 0
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    print("✓ Rutas RAG agregadas: /api/rag/query, /api/rag/search, /api/rag/stats, /api/rag/index")


# ==================== CLI ====================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RAG Novedades PGN")
    parser.add_argument('--index', action='store_true', help='Indexar documentos')
    parser.add_argument('--force', action='store_true', help='Forzar reindexación')
    parser.add_argument('--query', type=str, help='Consulta a realizar')
    parser.add_argument('--stats', action='store_true', help='Mostrar estadísticas')

    args = parser.parse_args()

    print("=" * 60)
    print("RAG NOVEDADES PGN")
    print("=" * 60)

    rag = RAGNovedades()

    if args.stats:
        stats = rag.get_stats()
        print("\nEstadísticas:")
        for k, v in stats.items():
            print(f"  {k}: {v}")

    elif args.index:
        print("\nIniciando indexación...")
        rag.index_all_documents(force_reindex=args.force)

    elif args.query:
        print(f"\nConsulta: {args.query}")
        result = rag.query(args.query)
        print(f"\nRespuesta:\n{result['answer']}")
        print(f"\nFuentes: {result['total_results']} documentos encontrados")

    else:
        # Modo interactivo
        print("\nModo interactivo. Escribe 'salir' para terminar.")
        print("Comandos: /stats, /index, /help")

        while True:
            try:
                user_input = input("\n> ").strip()

                if user_input.lower() in ['salir', 'exit', 'quit']:
                    break
                elif user_input == '/stats':
                    stats = rag.get_stats()
                    for k, v in stats.items():
                        print(f"  {k}: {v}")
                elif user_input == '/index':
                    rag.index_all_documents()
                elif user_input == '/help':
                    print("Comandos: /stats, /index, /help, salir")
                    print("O escribe una pregunta sobre novedades PGN")
                elif user_input:
                    result = rag.query(user_input)
                    print(f"\n{result['answer']}")
                    print(f"\n[{result['total_results']} fuentes encontradas]")

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")

    print("\n¡Hasta luego!")
