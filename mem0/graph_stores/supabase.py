import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text
from mem0.graph_stores.base import GraphStoreBase

logger = logging.getLogger(__name__)

class SupabaseGraph(GraphStoreBase):
    def __init__(self, config):
        self.config = config
        self.connection_string = config.config.get("connection_string")
        if not self.connection_string:
             # Try to get from env or default
             import os
             self.connection_string = os.environ.get(
                 "SUPABASE_CONNECTION_STRING", 
                 "postgresql://postgres:postgres@localhost:5432/postgres"
             )
        self.engine = create_engine(self.connection_string)

    def add(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]):
        """
        Add nodes and edges to the graph.
        
        Args:
            nodes: List of dicts, e.g. [{"name": "Alice", "label": "Person", "properties": {...}}]
            edges: List of dicts, e.g. [{"source": "Alice", "target": "Bob", "relation": "knows"}]
        """
        with self.engine.connect() as conn:
            # 1. Insert Nodes (Upsert)
            for node in nodes:
                try:
                    stmt = text("""
                        insert into nodes (name, label, properties)
                        values (:name, :label, :properties)
                        on conflict (name, label) 
                        do update set properties = nodes.properties || :properties
                        returning id
                    """)
                    conn.execute(stmt, {
                        "name": node["name"],
                        "label": node.get("label", "Entity"),
                        "properties": node.get("properties", {})
                    })
                except Exception as e:
                    logger.error(f"Error adding node {node}: {e}")

            # 2. Insert Edges (Upsert)
            for edge in edges:
                try:
                    # Resolve IDs first
                    source_id = conn.execute(text("select id from nodes where name = :name"), {"name": edge["source"]}).scalar()
                    target_id = conn.execute(text("select id from nodes where name = :name"), {"name": edge["target"]}).scalar()
                    
                    if source_id and target_id:
                        stmt = text("""
                            insert into edges (source_node_id, target_node_id, relation, properties)
                            values (:source, :target, :relation, :properties)
                            on conflict (source_node_id, target_node_id, relation)
                            do update set properties = edges.properties || :properties
                        """)
                        conn.execute(stmt, {
                            "source": source_id,
                            "target": target_id,
                            "relation": edge["relation"],
                            "properties": edge.get("properties", {})
                        })
                    else:
                        logger.warning(f"Could not link nodes for edge {edge}: IDs not found")
                except Exception as e:
                    logger.error(f"Error adding edge {edge}: {e}")
            conn.commit()

    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for related subgraphs based on a node name (query).
        Uses 'match_related_nodes' RPC.
        """
        results = []
        with self.engine.connect() as conn:
            try:
                # Assuming query is a node name for now
                stmt = text("select * from match_related_nodes(:query)")
                rows = conn.execute(stmt, {"query": query}).fetchall()
                for row in rows:
                    results.append({
                        "source": row.source,
                        "relation": row.relation,
                        "target": row.target
                    })
            except Exception as e:
                logger.error(f"Error searching graph: {e}")
        return results

    def delete(self, filters: Dict[str, Any]):
        # Implementation for delete pending requirements
        pass
    
    def delete_all(self):
        # Implementation for delete_all
        pass
