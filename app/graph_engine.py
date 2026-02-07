"""
Legal Graph Engine for GraphRAG
================================
Motor de grafos para análisis de decretos de la Procuraduría General de la Nación.
Implementa búsqueda local y global basada en Microsoft GraphRAG.
"""

import os
import json
import networkx as nx
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """Representa una entidad en el grafo (DECRETO, FUNCIONARIO, UNIDAD)"""
    id: str
    type: str
    name: str
    properties: Dict[str, Any] = field(default_factory=dict)
    source_file: str = ""


@dataclass
class Relationship:
    """Representa una relación entre entidades"""
    source: str
    target: str
    type: str
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Community:
    """Representa una comunidad detectada en el grafo"""
    id: int
    nodes: List[str]
    summary: str = ""
    dominant_type: str = ""
    size: int = 0


class LegalGraphManager:
    """
    Gestor del grafo de conocimiento legal.
    Implementa carga de datos, construcción del grafo, 
    detección de comunidades y búsquedas Local/Global.
    """
    
    def __init__(self, graphrag_dir: str = None):
        """
        Inicializa el gestor del grafo.
        
        Args:
            graphrag_dir: Directorio con archivos *.graphrag.json
        """
        self.graphrag_dir = graphrag_dir or r"C:\temp\PNG_CERTIFICADO_V3\output_2009_hybrid\graphrag"
        self.graph = nx.Graph()
        self.entities: Dict[str, Entity] = {}
        self.relationships: List[Relationship] = []
        self.communities: Dict[int, Community] = {}
        self.source_files: Dict[str, str] = {}  # entity_id -> source_file
        self._loaded = False
        
    def load_graphrag_files(self, limit: int = None) -> int:
        """
        Carga todos los archivos *.graphrag.json del directorio.
        
        Args:
            limit: Número máximo de archivos a cargar (None = todos)
            
        Returns:
            Número de archivos cargados exitosamente
        """
        if not os.path.exists(self.graphrag_dir):
            logger.error(f"Directorio no encontrado: {self.graphrag_dir}")
            return 0
            
        files = sorted([
            f for f in os.listdir(self.graphrag_dir) 
            if f.endswith('.graphrag.json')
        ])
        
        if limit:
            files = files[:limit]
            
        loaded_count = 0
        for filename in files:
            filepath = os.path.join(self.graphrag_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._process_graphrag_file(data, filepath)
                loaded_count += 1
            except json.JSONDecodeError as e:
                logger.warning(f"Error JSON en {filename}: {e}")
            except Exception as e:
                logger.warning(f"Error procesando {filename}: {e}")
                
        self._loaded = True
        logger.info(f"Cargados {loaded_count} archivos GraphRAG")
        logger.info(f"Grafo: {len(self.entities)} entidades, {len(self.relationships)} relaciones")
        return loaded_count
    
    def load_from_database(self, db_path: str = None) -> int:
        """
        Carga el grafo directamente desde la base de datos SQLite.
        Esto proporciona sincronización en tiempo real con novedades_pgn.db.
        
        Args:
            db_path: Ruta a la base de datos SQLite
            
        Returns:
            Número de entidades cargadas
        """
        import sqlite3
        
        db_path = db_path or r"C:\temp\PNG_CERTIFICADO_V3\novedades_pgn.db"
        
        if not os.path.exists(db_path):
            logger.error(f"Base de datos no encontrada: {db_path}")
            return 0
            
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        loaded_count = 0
        
        try:
            # 1. Cargar DECRETOS como entidades
            cursor.execute('''
                SELECT d.*, 
                       COUNT(n.id) as num_novedades
                FROM decretos d
                LEFT JOIN novedades n ON d.id = n.decreto_id
                GROUP BY d.id
            ''')
            
            for row in cursor.fetchall():
                entity_id = f"DECRETO_{row['id']}"
                entity = Entity(
                    id=entity_id,
                    type='DECRETO',
                    name=f"DECRETO {row['numero_decreto']}-{row['anio']}",
                    properties={
                        'numero': row['numero_decreto'],
                        'anio': row['anio'],
                        'fecha': row['fecha_decreto_texto'] or '',
                        'archivo': row['archivo_origen'] or '',
                        'ruta_completa': row['ruta_completa'] or '',
                        'num_novedades': row['num_novedades'],
                        'estado': row['estado_procesamiento'] or 'PROCESADO'
                    },
                    source_file=row['archivo_origen'] or ''
                )
                
                self.entities[entity_id] = entity
                self.graph.add_node(
                    entity_id,
                    type='DECRETO',
                    name=entity.name,
                    **entity.properties
                )
                loaded_count += 1
            
            # 2. Cargar FUNCIONARIOS como entidades
            cursor.execute('''
                SELECT f.*,
                       COUNT(n.id) as num_novedades,
                       GROUP_CONCAT(DISTINCT n.codigo_novedad) as codigos_novedad
                FROM funcionarios f
                LEFT JOIN novedades n ON f.id = n.funcionario_id
                GROUP BY f.id
            ''')
            
            for row in cursor.fetchall():
                entity_id = f"FUNC_{row['id']}"
                nombre = row['nombre_completo'] or f"{row['nombres'] or ''} {row['apellidos'] or ''}".strip()
                
                entity = Entity(
                    id=entity_id,
                    type='FUNCIONARIO',
                    name=nombre.upper() if nombre else f"CC {row['cedula']}",
                    properties={
                        'cedula': row['cedula'] or '',
                        'nombres': row['nombres'] or '',
                        'apellidos': row['apellidos'] or '',
                        'num_novedades': row['num_novedades'],
                        'tipos_novedad': row['codigos_novedad'] or ''
                    },
                    source_file=''
                )
                
                self.entities[entity_id] = entity
                self.graph.add_node(
                    entity_id,
                    type='FUNCIONARIO',
                    name=entity.name,
                    **entity.properties
                )
                loaded_count += 1
            
            # 3. Cargar NOVEDADES como relaciones (FUNCIONARIO -> DECRETO)
            cursor.execute('''
                SELECT n.*, d.numero_decreto, d.anio,
                       f.nombre_completo, f.cedula
                FROM novedades n
                JOIN decretos d ON n.decreto_id = d.id
                LEFT JOIN funcionarios f ON n.funcionario_id = f.id
            ''')
            
            for row in cursor.fetchall():
                source_id = f"FUNC_{row['funcionario_id']}" if row['funcionario_id'] else None
                target_id = f"DECRETO_{row['decreto_id']}"
                
                if source_id and source_id in self.entities and target_id in self.entities:
                    rel = Relationship(
                        source=source_id,
                        target=target_id,
                        type=row['codigo_novedad'] or 'NOVEDAD',
                        properties={
                            'tipo_novedad': row['tipo_novedad'] or '',
                            'cargo': row['cargo_actual'] or '',
                            'dependencia': row['dependencia'] or '',
                            'observaciones': row['observaciones'] or '',
                            'fecha_inicio': row['fecha_inicio_texto'] or ''
                        }
                    )
                    
                    self.relationships.append(rel)
                    self.graph.add_edge(
                        source_id, target_id,
                        type=rel.type,
                        **rel.properties
                    )
            
            # 4. Cargar DEPENDENCIAS como entidades (extraer de novedades)
            cursor.execute('''
                SELECT DISTINCT dependencia, COUNT(*) as count
                FROM novedades 
                WHERE dependencia IS NOT NULL AND dependencia != ''
                GROUP BY dependencia
                HAVING count > 1
            ''')
            
            for row in cursor.fetchall():
                dep_name = row['dependencia']
                entity_id = f"DEP_{hash(dep_name) % 100000}"
                
                entity = Entity(
                    id=entity_id,
                    type='DEPENDENCIA',
                    name=dep_name[:80],
                    properties={'total_novedades': row['count']},
                    source_file=''
                )
                
                self.entities[entity_id] = entity
                self.graph.add_node(
                    entity_id,
                    type='DEPENDENCIA',
                    name=entity.name,
                    **entity.properties
                )
                loaded_count += 1
                
        except Exception as e:
            logger.error(f"Error cargando desde base de datos: {e}")
        finally:
            conn.close()
            
        self._loaded = True
        self.graphrag_dir = f"SQLite: {db_path}"
        logger.info(f"Cargadas {loaded_count} entidades desde base de datos")
        logger.info(f"Grafo: {len(self.entities)} entidades, {len(self.relationships)} relaciones")
        return loaded_count

        
    def _process_graphrag_file(self, data: Dict, source_file: str):
        """Procesa un archivo graphrag.json y agrega al grafo."""
        
        # Procesar entidades
        for entity_data in data.get('entities', []):
            entity_id = entity_data.get('id', '')
            if not entity_id:
                continue
                
            entity = Entity(
                id=entity_id,
                type=entity_data.get('type', 'UNKNOWN'),
                name=entity_data.get('name', ''),
                properties=entity_data.get('properties', {}),
                source_file=source_file
            )
            
            self.entities[entity_id] = entity
            self.source_files[entity_id] = source_file
            
            # Agregar nodo al grafo
            self.graph.add_node(
                entity_id,
                type=entity.type,
                name=entity.name,
                **entity.properties
            )
            
        # Procesar relaciones
        for rel_data in data.get('relationships', []):
            source = rel_data.get('source', '')
            target = rel_data.get('target', '')
            
            if not source or not target:
                continue
                
            rel = Relationship(
                source=source,
                target=target,
                type=rel_data.get('type', 'RELATED'),
                properties=rel_data.get('properties', {})
            )
            
            self.relationships.append(rel)
            
            # Agregar arista al grafo
            self.graph.add_edge(
                source, target,
                type=rel.type,
                **rel.properties
            )
            
    def build_graph(self) -> nx.Graph:
        """
        Construye y retorna el grafo de NetworkX.
        Si no está cargado, carga los archivos primero.
        """
        if not self._loaded:
            self.load_graphrag_files()
        return self.graph
        
    def detect_communities(self, algorithm: str = 'louvain') -> Dict[int, Community]:
        """
        Detecta comunidades en el grafo usando el algoritmo especificado.
        
        Args:
            algorithm: 'louvain' (default), 'leiden', o 'label_propagation'
            
        Returns:
            Diccionario de comunidades detectadas
        """
        if not self._loaded:
            self.load_graphrag_files()
            
        if len(self.graph.nodes()) == 0:
            return {}
            
        # Usar Louvain (disponible en networkx)
        try:
            from networkx.algorithms.community import louvain_communities
            communities_list = list(louvain_communities(self.graph, seed=42))
        except ImportError:
            # Fallback a label propagation
            from networkx.algorithms.community import label_propagation_communities
            communities_list = list(label_propagation_communities(self.graph))
            
        self.communities = {}
        for i, nodes in enumerate(communities_list):
            nodes_list = list(nodes)
            
            # Determinar tipo dominante
            type_counts = defaultdict(int)
            for node_id in nodes_list:
                if node_id in self.entities:
                    type_counts[self.entities[node_id].type] += 1
            dominant_type = max(type_counts.keys(), key=lambda k: type_counts[k]) if type_counts else "MIXED"
            
            # Generar resumen básico
            sample_names = [
                self.entities[n].name for n in nodes_list[:3] 
                if n in self.entities
            ]
            summary = f"Comunidad de {len(nodes_list)} elementos ({dominant_type}): {', '.join(sample_names)}"
            
            self.communities[i] = Community(
                id=i,
                nodes=nodes_list,
                summary=summary,
                dominant_type=dominant_type,
                size=len(nodes_list)
            )
            
        logger.info(f"Detectadas {len(self.communities)} comunidades")
        return self.communities
        
    def local_search(self, query: str, entity_id: str = None, depth: int = 2) -> Dict:
        """
        Búsqueda local: navega por vecinos inmediatos del nodo.
        
        Args:
            query: Consulta del usuario (nombre, cédula, decreto)
            entity_id: ID de entidad específica (opcional)
            depth: Profundidad de búsqueda en el grafo
            
        Returns:
            Diccionario con resultados de la búsqueda
        """
        if not self._loaded:
            self.load_graphrag_files()
            
        results = {
            'query': query,
            'matches': [],
            'related_entities': [],
            'relationships': [],
            'source_files': set()
        }
        
        # Buscar entidades que coincidan
        query_lower = query.lower()
        matched_ids = []
        
        for entity_id, entity in self.entities.items():
            # Buscar en nombre, cédula, propiedades
            if query_lower in entity.name.lower():
                matched_ids.append(entity_id)
                continue
            if query_lower in str(entity.properties.get('cedula', '')):
                matched_ids.append(entity_id)
                continue
            if query_lower in str(entity.properties.get('numero', '')):
                matched_ids.append(entity_id)
                
        # Para cada match, obtener vecinos
        for eid in matched_ids:
            entity = self.entities[eid]
            results['matches'].append({
                'id': eid,
                'type': entity.type,
                'name': entity.name,
                'properties': entity.properties,
                'source_file': entity.source_file
            })
            results['source_files'].add(entity.source_file)
            
            # Obtener vecinos hasta la profundidad especificada
            try:
                neighbors = nx.single_source_shortest_path_length(self.graph, eid, cutoff=depth)
                for neighbor_id, distance in neighbors.items():
                    if neighbor_id != eid and neighbor_id in self.entities:
                        neighbor = self.entities[neighbor_id]
                        results['related_entities'].append({
                            'id': neighbor_id,
                            'type': neighbor.type,
                            'name': neighbor.name,
                            'distance': distance,
                            'source_file': neighbor.source_file
                        })
                        results['source_files'].add(neighbor.source_file)
            except nx.NetworkXError:
                pass
                
        # Obtener relaciones relevantes
        for rel in self.relationships:
            if rel.source in matched_ids or rel.target in matched_ids:
                results['relationships'].append({
                    'source': rel.source,
                    'target': rel.target,
                    'type': rel.type,
                    'properties': rel.properties
                })
                
        results['source_files'] = list(results['source_files'])
        results['total_matches'] = len(matched_ids)
        
        return results
        
    def global_search(self, query: str) -> Dict:
        """
        Búsqueda global: consulta transversal usando resúmenes de comunidades.
        Implementa lógica Map-Reduce sobre las comunidades.
        
        Args:
            query: Consulta del usuario sobre temas transversales
            
        Returns:
            Diccionario con resultados agregados
        """
        if not self._loaded:
            self.load_graphrag_files()
            
        if not self.communities:
            self.detect_communities()
            
        results = {
            'query': query,
            'relevant_communities': [],
            'statistics': {},
            'timeline': [],
            'source_files': set()
        }
        
        query_lower = query.lower()
        
        # MAP: Analizar cada comunidad
        community_scores = []
        for comm_id, community in self.communities.items():
            score = 0
            relevant_nodes = []
            
            for node_id in community.nodes:
                if node_id in self.entities:
                    entity = self.entities[node_id]
                    # Calcular relevancia
                    if query_lower in entity.name.lower():
                        score += 2
                        relevant_nodes.append(entity)
                    if query_lower in str(entity.properties).lower():
                        score += 1
                        if entity not in relevant_nodes:
                            relevant_nodes.append(entity)
                            
            if score > 0:
                community_scores.append({
                    'community_id': comm_id,
                    'score': score,
                    'summary': community.summary,
                    'dominant_type': community.dominant_type,
                    'size': community.size,
                    'relevant_nodes': relevant_nodes[:5]  # Limitar a 5
                })
                
        # REDUCE: Agregar resultados
        community_scores.sort(key=lambda x: x['score'], reverse=True)
        results['relevant_communities'] = community_scores[:10]  # Top 10
        
        # Estadísticas globales
        type_counts = defaultdict(int)
        yearly_counts = defaultdict(int)
        novedad_counts = defaultdict(int)
        
        for entity in self.entities.values():
            type_counts[entity.type] += 1
            if entity.type == 'DECRETO':
                year = entity.properties.get('anio')
                if year:
                    yearly_counts[year] += 1
                novedad = entity.properties.get('codigo_novedad')
                if novedad:
                    novedad_counts[novedad] += 1
                    
        results['statistics'] = {
            'total_entities': len(self.entities),
            'total_relationships': len(self.relationships),
            'total_communities': len(self.communities),
            'by_type': dict(type_counts),
            'by_year': dict(sorted(yearly_counts.items())),
            'by_novedad': dict(sorted(novedad_counts.items(), key=lambda x: -x[1]))
        }
        
        # Línea temporal de decretos
        decretos = [
            e for e in self.entities.values() 
            if e.type == 'DECRETO' and e.properties.get('fecha')
        ]
        decretos.sort(key=lambda x: str(x.properties.get('anio', 0)))
        results['timeline'] = [
            {
                'id': d.id,
                'name': d.name,
                'fecha': d.properties.get('fecha'),
                'anio': d.properties.get('anio'),
                'codigo_novedad': d.properties.get('codigo_novedad'),
                'resumen': d.properties.get('resumen', '')[:100]
            }
            for d in decretos[:50]  # Últimos 50
        ]
        
        return results
        
    def get_entity_details(self, entity_id: str) -> Optional[Dict]:
        """Obtiene detalles completos de una entidad."""
        if entity_id not in self.entities:
            return None
            
        entity = self.entities[entity_id]
        
        # Obtener relaciones
        related = []
        for rel in self.relationships:
            if rel.source == entity_id:
                if rel.target in self.entities:
                    related.append({
                        'direction': 'outgoing',
                        'type': rel.type,
                        'entity': {
                            'id': rel.target,
                            'name': self.entities[rel.target].name,
                            'type': self.entities[rel.target].type
                        },
                        'properties': rel.properties
                    })
            elif rel.target == entity_id:
                if rel.source in self.entities:
                    related.append({
                        'direction': 'incoming',
                        'type': rel.type,
                        'entity': {
                            'id': rel.source,
                            'name': self.entities[rel.source].name,
                            'type': self.entities[rel.source].type
                        },
                        'properties': rel.properties
                    })
                    
        return {
            'id': entity.id,
            'type': entity.type,
            'name': entity.name,
            'properties': entity.properties,
            'source_file': entity.source_file,
            'relationships': related,
            'degree': self.graph.degree(entity_id) if entity_id in self.graph else 0
        }
        
    def get_graph_data_for_visualization(self) -> Dict:
        """
        Prepara datos del grafo para visualización en Streamlit.
        
        Returns:
            Diccionario con nodos y aristas formateados
        """
        if not self._loaded:
            self.load_graphrag_files()
            
        nodes = []
        for node_id in self.graph.nodes():
            if node_id in self.entities:
                entity = self.entities[node_id]
                nodes.append({
                    'id': node_id,
                    'label': entity.name[:30] if len(entity.name) > 30 else entity.name,
                    'type': entity.type,
                    'size': 10 + self.graph.degree(node_id) * 2,
                    'properties': entity.properties
                })
                
        edges = []
        for source, target, data in self.graph.edges(data=True):
            edges.append({
                'source': source,
                'target': target,
                'type': data.get('type', 'RELATED'),
                'label': data.get('tipo_novedad', data.get('type', ''))[:15]
            })
            
        return {
            'nodes': nodes,
            'edges': edges,
            'stats': {
                'total_nodes': len(nodes),
                'total_edges': len(edges)
            }
        }
        
    def get_summary(self) -> Dict:
        """Retorna resumen del estado del grafo."""
        if not self._loaded:
            return {'status': 'not_loaded', 'message': 'Grafo no cargado'}
            
        return {
            'status': 'loaded',
            'total_entities': len(self.entities),
            'total_relationships': len(self.relationships),
            'total_communities': len(self.communities),
            'entity_types': dict(defaultdict(int, {
                e.type: sum(1 for x in self.entities.values() if x.type == e.type)
                for e in self.entities.values()
            })),
            'source_directory': self.graphrag_dir
        }


# Test básico
if __name__ == '__main__':
    manager = LegalGraphManager()
    manager.load_graphrag_files(limit=20)
    manager.detect_communities()
    
    print("\n=== Resumen del Grafo ===")
    print(json.dumps(manager.get_summary(), indent=2, ensure_ascii=False))
    
    print("\n=== Búsqueda Local: 'SIERRA' ===")
    results = manager.local_search('SIERRA')
    print(f"Encontrados: {results['total_matches']} matches")
    for m in results['matches'][:3]:
        print(f"  - {m['name']} ({m['type']})")
        
    print("\n=== Búsqueda Global: 'encargo' ===")
    global_results = manager.global_search('encargo')
    print(f"Comunidades relevantes: {len(global_results['relevant_communities'])}")
    print(f"Estadísticas: {global_results['statistics']['by_novedad']}")
