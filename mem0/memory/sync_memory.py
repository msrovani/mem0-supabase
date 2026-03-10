import concurrent
import hashlib
import json
import logging
import uuid
import warnings
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, Optional, List

import pytz
from pydantic import ValidationError

from mem0.configs.base import MemoryConfig, MemoryItem
from mem0.configs.enums import MemoryType
from mem0.configs.prompts import (
    PROCEDURAL_MEMORY_SYSTEM_PROMPT,
    get_update_memory_messages,
    MEMORY_MERGE_PROMPT,
)
from mem0.exceptions import ValidationError as Mem0ValidationError
from mem0.memory.base import MemoryBase
from mem0.memory.setup import setup_config
from mem0.memory.telemetry import capture_event
from mem0.memory.utils import (
    build_filters_and_metadata,
    extract_json,
    get_fact_retrieval_messages,
    parse_messages,
    parse_vision_messages,
    remove_code_blocks,
    select_fields,
)
from mem0.utils.factory import (
    EmbedderFactory,
    LlmFactory,
    VectorStoreFactory,
    RerankerFactory,
    GraphStoreFactory,
)
from mem0.lifecycle import LifecycleManager
from mem0.enterprise import Nexus
from mem0.recollection import RecollectionEngine
from mem0.memory.surprise import SurpriseEngine
from mem0.memory.ego import EgoEngine
from mem0.memory.orchestrator import ContextOrchestrator
from mem0.memory.reflection import ReflectionEngine
from mem0.memory.dreaming import DreamingEngine
from mem0.memory.tool_state import ToolStateManager
from mem0.memory.bridge import MemoryBridge

# Suppress SWIG deprecation warnings globally
warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*SwigPy.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*swigvarlink.*")

setup_config()
logger = logging.getLogger(__name__)


class Memory(MemoryBase):
    def __init__(self, config: MemoryConfig = MemoryConfig()):
        self.config = config

        self.custom_fact_extraction_prompt = self.config.custom_fact_extraction_prompt
        self.custom_update_memory_prompt = self.config.custom_update_memory_prompt
        self.embedding_model = EmbedderFactory.create(
            self.config.embedder.provider,
            self.config.embedder.config,
            self.config.vector_store.config,
        )
        self.vector_store = VectorStoreFactory.create(
            self.config.vector_store.provider, self.config.vector_store.config
        )
        self.llm = LlmFactory.create(self.config.llm.provider, self.config.llm.config)

        if self.config.vector_store.provider != "supabase":
            raise ValueError("This build only supports Supabase as the vector store provider.")
        from mem0.memory.storage_postgres import PostgresManager

        conn_string = self.config.vector_store.config.connection_string
        self.db = PostgresManager(conn_string)

        self.collection_name = self.config.vector_store.config.collection_name
        self.api_version = self.config.version

        # Initialize reranker if configured
        self.reranker = None
        if config.reranker:
            self.reranker = RerankerFactory.create(config.reranker.provider, config.reranker.config)

        self.enable_graph = False
        self.graph = None

        if self.config.graph_store and self.config.graph_store.config:
            provider = self.config.graph_store.provider
            try:
                self.graph = GraphStoreFactory.create(provider, self.config.graph_store)
                self.enable_graph = True
            except NotImplementedError:
                logger.warning(f"Graph store provider '{provider}' not supported. Graph disabled.")
                self.enable_graph = False
            except Exception as e:
                logger.error(f"Failed to initialize graph store: {e}")
                self.enable_graph = False

        # Create telemetry config manually to avoid deepcopy issues with thread locks
        telemetry_config_dict = {}
        if hasattr(self.config.vector_store.config, "model_dump"):
            # For pydantic models
            telemetry_config_dict = self.config.vector_store.config.model_dump()
        else:
            # For other objects, manually copy common attributes
            for attr in ["host", "port", "path", "api_key", "index_name", "dimension", "metric"]:
                if hasattr(self.config.vector_store.config, attr):
                    telemetry_config_dict[attr] = getattr(self.config.vector_store.config, attr)

        # Override collection name for telemetry
        telemetry_config_dict["collection_name"] = "mem0migrations"

        # Create the config object using the same class as the original
        telemetry_config = self.config.vector_store.config.__class__(**telemetry_config_dict)
        self._telemetry_vector_store = VectorStoreFactory.create(self.config.vector_store.provider, telemetry_config)

        # Enterprise & Lifecycle Managers
        self.lifecycle = None
        self.nexus = None
        if self.config.vector_store.provider == "supabase":
            conn_ptr = self.config.vector_store.config.connection_string
            self.lifecycle = LifecycleManager(conn_ptr, table_name=self.collection_name)
            self.nexus = Nexus(conn_ptr, table_name=self.collection_name)

        # Layer 11: Recollection Engine
        self.recollection = RecollectionEngine(self)

        # SSR: Surprise Engine
        self.surprise_engine = SurpriseEngine()

        # Layer 12: Ego Engine
        self.ego_engine = EgoEngine(llm=self.llm)

        # [Salto 2] Context Orchestrator
        self.orchestrator = ContextOrchestrator(limit=self.config.context_window_limit, llm=self.llm)

        # [Salto 3] Reflection Engine
        self.reflection_engine = ReflectionEngine(llm=self.llm)
        self.addition_counter = 0

        # [Salto: Dreaming Mode]
        self.dreaming_engine = DreamingEngine(llm=self.llm)
        self.dreaming_counter = 0

        # [Salto: Tool-State Memory]
        self.tool_state = ToolStateManager(vector_store=self.vector_store)

        # [Salto: Memory Bridge]
        self.bridge = MemoryBridge(memory_instance=self)

        # SSR: Resonance Buffer (Subconscious Working Memory)
        self.resonance_buffer = []
        if self.config.enable_resonance and self.lifecycle:
            self.resonance_channel = self.lifecycle.subscribe_to_resonance(self._handle_resonance)

        capture_event("mem0.init", self, {"sync_type": "sync"})

    def _handle_resonance(self, payload: Dict[str, Any]):
        """
        Processes a real-time resonance signal (synaptic pulse).
        Adds the item to a priority buffer for inclusion in the next search context.
        """
        memory_data = {
            "id": payload.get("id"),
            "memory": payload.get("payload", {}).get("data", ""),
            "is_flashbulb": payload.get("is_flashbulb", False),
            "importance_score": payload.get("payload", {}).get("importance_score", 0.0),
        }
        self.resonance_buffer.append(memory_data)
        # Keep buffer lean (e.g., last 5 resonances)
        if len(self.resonance_buffer) > 5:
            self.resonance_buffer.pop(0)
        logger.info(f"Subconscious resonance absorbed: {memory_data['id']}")

    def synthesize_identity(self, user_id: str, agent_id: Optional[str] = None) -> str:
        """
        Layer 12: Meta-Cognitive Identity Synthesis.
        Extracts current persona traits from recent memories.
        """
        if not self.config.enable_ego:
            return "Ego Layer disabled."

        # Fetch recent memories for synthesis
        filters = {"user_id": user_id}
        if agent_id:
            filters["agent_id"] = agent_id

        recent = self.search("", filters=filters, limit=20)
        persona = self.ego_engine.synthesize(recent.get("results", []))

        # Store identity as a specific memory type
        self.add(
            f"CURRENT IDENTITY: {persona}", user_id=user_id, agent_id=agent_id, metadata={"memory_type": "identity"}
        )

        return persona

    @classmethod
    def from_config(cls, config_dict: Dict[str, Any]):
        try:
            config_dict = cls._process_config(config_dict)
            config = MemoryConfig(**config_dict)
        except ValidationError as e:
            logger.error(f"Configuration validation error: {e}")
            raise
        return cls(config)

    @staticmethod
    def _process_config(config_dict: Dict[str, Any]) -> Dict[str, Any]:
        if "graph_store" in config_dict:
            # Allow graph store if it is supabase
            pass
        try:
            return config_dict
        except ValidationError as e:
            logger.error(f"Configuration validation error: {e}")
            raise

    def _add_to_graph(self, messages, filters):
        """
        Add messages to the graph store.
        """
        if not self.enable_graph or not self.graph:
            return None

        from mem0.memory.utils import get_graph_extraction_prompt

        # Combine messages into a single text for extraction
        text_content = ""
        for msg in messages:
            if isinstance(msg, dict):
                text_content += f"{msg.get('role', 'user')}: {msg.get('content', '')}\n"
            else:
                text_content += str(msg) + "\n"

        prompt = get_graph_extraction_prompt(text_content)

        try:
            response = self.llm.generate_response(messages=[{"role": "user", "content": prompt}])
            data = json.loads(extract_json(response))

            nodes = data.get("nodes", [])
            edges = data.get("edges", [])

            # Enrich nodes/edges with user_id/agent_id from filters if available
            common_props = {}
            if "user_id" in filters:
                common_props["user_id"] = filters["user_id"]
            if "agent_id" in filters:
                common_props["agent_id"] = filters["agent_id"]
            if "run_id" in filters:
                common_props["run_id"] = filters["run_id"]

            for node in nodes:
                node["properties"] = {**node.get("properties", {}), **common_props}

            for edge in edges:
                edge["properties"] = {**edge.get("properties", {}), **common_props}

            self.graph.add(nodes, edges)
            return {"nodes": len(nodes), "edges": len(edges)}
        except Exception as e:
            logger.error(f"Error adding to graph: {e}")
            return None

    def _should_use_agent_memory_extraction(self, messages, metadata):
        """Determine whether to use agent memory extraction"""
        has_agent_id = metadata.get("agent_id") is not None
        has_assistant_messages = any(msg.get("role") == "assistant" for msg in messages)
        return has_agent_id and has_assistant_messages

    def add(
        self,
        messages,
        *,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        infer: bool = True,
        memory_type: Optional[str] = None,
        prompt: Optional[str] = None,
        org_id: Optional[str] = None,
        team_id: Optional[str] = None,
        visibility: str = "private",
    ):
        processed_metadata, effective_filters = build_filters_and_metadata(
            user_id=user_id,
            agent_id=agent_id,
            run_id=run_id,
            input_metadata=metadata,
        )

        if org_id:
            processed_metadata["org_id"] = org_id
        if team_id:
            processed_metadata["team_id"] = team_id
        processed_metadata["visibility"] = visibility

        if memory_type is not None and memory_type != MemoryType.PROCEDURAL.value:
            raise Mem0ValidationError(
                message=f"Invalid 'memory_type'. Please pass {MemoryType.PROCEDURAL.value} to create procedural memories.",
                error_code="VALIDATION_002",
                details={"provided_type": memory_type, "valid_type": MemoryType.PROCEDURAL.value},
                suggestion=f"Use '{MemoryType.PROCEDURAL.value}' to create procedural memories.",
            )

        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        elif isinstance(messages, dict):
            messages = [messages]
        elif not isinstance(messages, list):
            raise Mem0ValidationError(
                message="messages must be str, dict, or list[dict]",
                error_code="VALIDATION_003",
                details={"provided_type": type(messages).__name__, "valid_types": ["str", "dict", "list[dict]"]},
                suggestion="Convert your input to a string, dictionary, or list of dictionaries.",
            )

        if agent_id is not None and memory_type == MemoryType.PROCEDURAL.value:
            return self._create_procedural_memory(messages, metadata=processed_metadata, prompt=prompt)

        if self.config.llm.config.get("enable_vision"):
            messages = parse_vision_messages(messages, self.llm, self.config.llm.config.get("vision_details"))
        else:
            messages = parse_vision_messages(messages)

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future1 = executor.submit(self._add_to_vector_store, messages, processed_metadata, effective_filters, infer)
            future2 = executor.submit(self._add_to_graph, messages, effective_filters)

            vector_store_result = future1.result()
            graph_result = future2.result()

        capture_event(
            "mem0.add",
            self,
            {"version": self.api_version, "sync_type": "sync"},
        )

        # [Salto 3] Trigger Reflection Background Task
        if self.config.enable_reflection:
            self.addition_counter += 1
            if self.addition_counter >= self.config.reflection_interval:
                self.addition_counter = 0

                def run_reflection_sync(u_id, a_id):
                    try:
                        recent = self.get_all(user_id=u_id, agent_id=a_id, limit=20)
                        if isinstance(recent, dict):
                            recent_list = recent.get("results", [])
                        else:
                            recent_list = recent
                        
                        insights = self.reflection_engine.reflect(recent_list)
                        for insight in insights:
                            self.add(insight, user_id=u_id, agent_id=a_id, infer=False, metadata={"memory_type": "insight"})
                        logger.info(f"Reflection completed: {len(insights)} insights generated.")
                    except Exception as e:
                        logger.error(f"Background reflection failed: {e}")

                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                executor.submit(run_reflection_sync, user_id, agent_id)
                executor.shutdown(wait=False)

        # [Salto: Dreaming Mode] Trigger
        if self.config.enable_dreaming:
            self.dreaming_counter += 1
            if self.dreaming_counter >= self.config.dreaming_interval:
                self.dreaming_counter = 0

                def run_dreaming_sync(u_id, a_id):
                    try:
                        recent = self.get_all(user_id=u_id, agent_id=a_id, limit=30)
                        recent_list = recent.get("results", []) if isinstance(recent, dict) else recent
                        synthetic = self.dreaming_engine.dream(recent_list)
                        for s_mem in synthetic:
                            self.add(s_mem, user_id=u_id, agent_id=a_id, infer=False, metadata={"memory_type": "synthetic"})
                        logger.info(f"Dreaming completed: {len(synthetic)} synthetic memories generated.")
                    except Exception as e:
                        logger.error(f"Background dreaming failed: {e}")

                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                executor.submit(run_dreaming_sync, user_id, agent_id)
                executor.shutdown(wait=False)

        if self.enable_graph:
            return {"results": vector_store_result, "relations": graph_result}
        return {"results": vector_store_result}

    def _add_to_vector_store(self, messages, metadata, filters, infer):
        if not infer:
            returned_memories = []
            for message_dict in messages:
                if not isinstance(message_dict, dict) or not message_dict.get("role") or not message_dict.get("content"):
                    continue
                if message_dict["role"] == "system":
                    continue

                per_msg_meta = deepcopy(metadata)
                per_msg_meta["role"] = message_dict["role"]
                actor_name = message_dict.get("name")
                if actor_name:
                    per_msg_meta["actor_id"] = actor_name

                msg_content = message_dict["content"]
                msg_embeddings = self.embedding_model.embed(msg_content, "add")
                mem_id = self._create_memory(msg_content, {msg_content: msg_embeddings}, per_msg_meta)

                returned_memories.append({
                    "id": mem_id,
                    "memory": msg_content,
                    "event": "ADD",
                    "actor_id": actor_name,
                    "role": message_dict["role"],
                })
            return returned_memories

        parsed_messages = parse_messages(messages)
        is_agent_memory = self._should_use_agent_memory_extraction(messages, metadata)
        system_prompt, user_prompt = get_fact_retrieval_messages(parsed_messages, is_agent_memory)

        response = self.llm.generate_response(
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            response_format={"type": "json_object"},
        )

        try:
            response = remove_code_blocks(response)
            new_retrieved_facts = json.loads(response).get("facts", [])
        except Exception as e:
            logger.error(f"Error parsing facts: {e}")
            new_retrieved_facts = []

        retrieved_old_memory = []
        new_message_embeddings = {}
        surprise_results = {}
        search_filters = {k: v for k, v in filters.items() if k in ("user_id", "agent_id", "run_id")}

        for new_mem in new_retrieved_facts:
            embeddings = self.embedding_model.embed(new_mem, "add")
            new_message_embeddings[new_mem] = embeddings
            existing = self.vector_store.search(query=new_mem, vectors=embeddings, limit=5, filters=search_filters)

            surprise = self.surprise_engine.evaluate(embeddings, [{"id": m.id, "score": m.score} for m in existing])
            surprise_results[new_mem] = surprise

            for mem in existing:
                retrieved_old_memory.append({"id": mem.id, "text": mem.payload.get("data", "")})

        unique_old = {m["id"]: m for m in retrieved_old_memory}
        retrieved_old_memory = list(unique_old.values())

        temp_uuid_mapping = {str(idx): m["id"] for idx, m in enumerate(retrieved_old_memory)}
        for idx, m in enumerate(retrieved_old_memory):
            m["id"] = str(idx)

        if new_retrieved_facts:
            update_prompt = get_update_memory_messages(retrieved_old_memory, new_retrieved_facts, self.config.custom_update_memory_prompt)
            try:
                response = self.llm.generate_response(
                    messages=[{"role": "user", "content": update_prompt}],
                    response_format={"type": "json_object"},
                )
                new_memories_with_actions = json.loads(remove_code_blocks(response))
            except Exception as e:
                logger.error(f"Error updating memories: {e}")
                new_memories_with_actions = {}
        else:
            new_memories_with_actions = {}

        returned_memories = []
        for resp in new_memories_with_actions.get("memory", []):
            try:
                action_text = resp.get("text")
                if not action_text:
                    continue

                event_type = resp.get("event")
                if event_type == "ADD":
                    surprise = surprise_results.get(action_text, {"is_surprising": True})

                    # [Salto 1] Semantic Compression
                    if (self.config.enable_compression and not surprise["is_surprising"] 
                        and surprise["best_match_id"] and surprise["max_similarity"] >= self.config.compression_threshold):
                        mem_id = surprise["best_match_id"]
                        existing = self.vector_store.get(vector_id=mem_id)
                        prompt = MEMORY_MERGE_PROMPT.format(existing_memory=existing.payload.get("data", ""), new_fact=action_text)
                        merged = remove_code_blocks(self.llm.generate_response(messages=[{"role": "user", "content": prompt}]))
                        self.update(memory_id=mem_id, data=merged)
                        returned_memories.append({"id": mem_id, "memory": action_text, "event": "COMPRESS"})
                        continue

                    if not surprise["is_surprising"] and surprise["best_match_id"]:
                        if self.lifecycle:
                            self.lifecycle.reinforce_memory(surprise["best_match_id"])
                        returned_memories.append({"id": surprise["best_match_id"], "memory": action_text, "event": "REINFORCE"})
                        continue

                    mem_id = self._create_memory(action_text, new_message_embeddings, deepcopy(metadata))
                    returned_memories.append({"id": mem_id, "memory": action_text, "event": "ADD"})

                elif event_type == "UPDATE":
                    mem_id = temp_uuid_mapping.get(resp.get("id"))
                    if mem_id:
                        self._update_memory(mem_id, action_text, new_message_embeddings, deepcopy(metadata))
                        returned_memories.append({"id": mem_id, "memory": action_text, "event": "UPDATE"})

                elif event_type == "DELETE":
                    mem_id = temp_uuid_mapping.get(resp.get("id"))
                    if mem_id:
                        self._delete_memory(mem_id)
                        returned_memories.append({"id": mem_id, "memory": action_text, "event": "DELETE"})
            except Exception as e:
                logger.error(f"Error in memory action: {e}")

        return returned_memories

    def get(self, memory_id):
        memory = self.vector_store.get(vector_id=memory_id)
        if not memory:
            return None
        promoted = ["user_id", "agent_id", "run_id", "actor_id", "role"]
        result = MemoryItem(id=memory.id, memory=memory.payload.get("data", ""), hash=memory.payload.get("hash"), 
                            created_at=memory.payload.get("created_at"), updated_at=memory.payload.get("updated_at")).model_dump()
        for k in promoted:
            if k in memory.payload:
                result[k] = memory.payload[k]
        meta = {k: v for k, v in memory.payload.items() if k not in promoted and k not in ("data", "hash", "created_at", "updated_at", "id")}
        if meta:
            result["metadata"] = meta
        return result

    def get_all(self, *, user_id=None, agent_id=None, run_id=None, filters=None, limit=100, fields=None):
        _, eff_filters = build_filters_and_metadata(user_id=user_id, agent_id=agent_id, run_id=run_id, input_filters=filters)
        if not any(k in eff_filters for k in ("user_id", "agent_id", "run_id")):
            raise ValueError("ID required.")
        mems = self.vector_store.list(filters=eff_filters, limit=limit)
        if isinstance(mems, (list, tuple)) and mems and isinstance(mems[0], (list, tuple)):
            mems = mems[0]
        
        promoted = ["user_id", "agent_id", "run_id", "actor_id", "role"]
        results = []
        for m in mems:
            item = MemoryItem(id=m.id, memory=m.payload.get("data", ""), hash=m.payload.get("hash"), 
                              created_at=m.payload.get("created_at"), updated_at=m.payload.get("updated_at")).model_dump(exclude={"score"})
            for k in promoted:
                if k in m.payload:
                    item[k] = m.payload[k]
            results.append(item)
        return {"results": select_fields(results, fields)}

    def search(self, query, *, user_id=None, agent_id=None, run_id=None, limit=100, filters=None, threshold=None, metadata_filters=None, fields=None, rerank=True):
        applied = (filters or {}).copy()
        if metadata_filters:
            applied.update(metadata_filters)
        _, eff_filters = build_filters_and_metadata(user_id=user_id, agent_id=agent_id, run_id=run_id)
        if applied and self._has_advanced_operators(applied):
            eff_filters.update(self._process_metadata_filters(applied))
        elif applied:
            eff_filters.update(applied)

        embeddings = self.embedding_model.embed(query, "search")
        mems = self.vector_store.search(query=query, vectors=embeddings, limit=limit, filters=eff_filters)
        
        promoted = ["user_id", "agent_id", "run_id", "actor_id", "role"]
        formatted = []
        for m in mems:
            if threshold and m.score < threshold:
                continue
            item = MemoryItem(id=m.id, memory=m.payload.get("data", ""), hash=m.payload.get("hash"), 
                              created_at=m.payload.get("created_at"), updated_at=m.payload.get("updated_at"), score=m.score).model_dump()
            for k in promoted:
                if k in m.payload:
                    item[k] = m.payload[k]
            formatted.append(item)

        if rerank and self.reranker and formatted:
            try:
                formatted = self.reranker.rerank(query, formatted, limit)
            except Exception as e:
                logger.warning(f"Rerank failed: {e}")

        results = {"results": select_fields(formatted, fields)}
        if self.resonance_buffer:
            results["subconscious_context"] = self.resonance_buffer
        if self.config.enable_ego and eff_filters.get("user_id"):
            id_filters = {"user_id": eff_filters["user_id"], "memory_type": "identity"}
            identity_mems = self.vector_store.list(filters=id_filters, limit=1)
            if isinstance(identity_mems, (list, tuple)) and identity_mems and isinstance(identity_mems[0], (list, tuple)):
                identity_mems = identity_mems[0]
            
            if identity_mems:
                results["persona_identity"] = identity_mems[0].payload.get("data", "")
        return results

    def _has_advanced_operators(self, filters):
        if not isinstance(filters, dict):
            return False
        for k, v in filters.items():
            if k in ("AND", "OR", "NOT") or v == "*":
                return True
            if isinstance(v, dict) and any(op in v for op in ("eq", "ne", "gt", "gte", "lt", "lte", "in", "nin", "contains", "icontains")):
                return True
        return False

    def _process_metadata_filters(self, filters):
        def proc(k, v):
            if not isinstance(v, dict):
                return {k: v}
            res = {}
            for op, val in v.items():
                if op in ("eq", "ne", "gt", "gte", "lt", "lte", "in", "nin", "contains", "icontains"):
                    res[k] = {op: val}
            return res
        processed = {}
        for k, v in filters.items():
            if k == "AND":
                for cond in v:
                    processed.update(self._process_metadata_filters(cond))
            elif k in ("OR", "NOT"):
                processed[f"${k.lower()}"] = [self._process_metadata_filters(c) for cond in v for c in cond.items()]
            else:
                processed.update(proc(k, v))
        return processed

    def update(self, memory_id, data=None, metadata=None):
        existing = self.vector_store.get(vector_id=memory_id)
        if not existing:
            raise ValueError(f"Memory with ID {memory_id} not found.")
            
        new_data = data if data is not None else existing.payload.get("data")
        emb = {new_data: self.embedding_model.embed(new_data, "update")}
        self._update_memory(memory_id, new_data, emb, metadata=metadata)
        return {"message": "Memory updated successfully!"}

    def delete(self, memory_id):
        self._delete_memory(memory_id)
        return {"message": "Memory deleted successfully!"}

    def delete_all(self, user_id=None, agent_id=None, run_id=None):
        f = {k: v for k, v in {"user_id": user_id, "agent_id": agent_id, "run_id": run_id}.items() if v}
        if not f:
            raise ValueError("Filter required.")
        mems = self.vector_store.list(filters=f)[0]
        for m in mems:
            self._delete_memory(m.id)
        return {"message": "Deleted."}

    def history(self, memory_id):
        return self.db.get_history(memory_id)

    def _create_memory(self, data, existing_embeddings, metadata=None):
        emb = existing_embeddings.get(data) or self.embedding_model.embed(data, "add")
        mid = str(uuid.uuid4())
        meta = metadata or {}
        meta.update({"data": data, "hash": hashlib.md5(data.encode()).hexdigest(), "created_at": datetime.now(pytz.UTC).isoformat()})
        for k in ["org_id", "team_id"]: 
            if k not in meta:
                meta[k] = None
        if "visibility" not in meta:
            meta["visibility"] = "private"
        if "importance_score" not in meta:
            meta["importance_score"] = 1.0
        self.vector_store.insert(vectors=[emb], ids=[mid], payloads=[meta])
        self.db.add_history(mid, None, data, "ADD", created_at=meta["created_at"], user_id=meta.get("user_id"))
        return mid

    def _create_procedural_memory(self, messages, metadata=None, prompt=None):
        msgs = [{"role": "system", "content": prompt or PROCEDURAL_MEMORY_SYSTEM_PROMPT}, *messages, {"role": "user", "content": "Summarize conversation."}]
        proc = remove_code_blocks(self.llm.generate_response(messages=msgs))
        metadata["memory_type"] = MemoryType.PROCEDURAL.value
        mid = self._create_memory(proc, {proc: self.embedding_model.embed(proc, "add")}, metadata)
        return {"results": [{"id": mid, "memory": proc, "event": "ADD"}]}

    def _update_memory(self, memory_id, data, existing_embeddings, metadata=None):
        existing = self.vector_store.get(vector_id=memory_id)
        prev = existing.payload.get("data")
        meta = (metadata or {}).copy()
        meta.update({"data": data, "hash": hashlib.md5(data.encode()).hexdigest(), "updated_at": datetime.now(pytz.UTC).isoformat()})
        for k in ["user_id", "agent_id", "run_id", "actor_id", "role", "org_id", "team_id", "visibility", "created_at"]:
            if k not in meta and k in existing.payload:
                meta[k] = existing.payload[k]
        meta["importance_score"] = 1.0
        emb = existing_embeddings.get(data) or self.embedding_model.embed(data, "update")
        self.vector_store.update(vector_id=memory_id, vector=emb, payload=meta)
        self.db.add_history(memory_id, prev, data, "UPDATE", created_at=meta.get("created_at"), updated_at=meta["updated_at"], user_id=meta.get("user_id"))
        return memory_id

    def _delete_memory(self, memory_id):
        existing = self.vector_store.get(vector_id=memory_id)
        self.vector_store.delete(vector_id=memory_id)
        self.db.add_history(memory_id, existing.payload.get("data"), None, "DELETE", is_deleted=1, user_id=existing.payload.get("user_id"))
        return memory_id

    def reset(self):
        self.db.reset()
        if hasattr(self.vector_store, "reset"):
            self.vector_store = VectorStoreFactory.reset(self.vector_store)
        else:
            self.vector_store.delete_col()
            self.vector_store = VectorStoreFactory.create(self.config.vector_store.provider, self.config.vector_store.config)

    def process_interaction(self, query, user_id=None, agent_id=None, run_id=None, limit=10, filters=None, learn=True, 
                            include_memories=True, include_associations=True, include_history=True, include_persona=True, 
                            memory_fields=None, history_fields=None):
        res_rec = {}
        if include_memories or include_associations or include_persona:
            _, base_f = build_filters_and_metadata(user_id, agent_id, run_id, input_filters=filters)
            res_rec = self.recollect(query=query, filters=base_f, limit=limit, enable_graph_jump=True)
        hist = self.get_all(user_id=user_id, agent_id=agent_id, run_id=run_id, limit=limit, fields=history_fields) if include_history else None
        if learn:
            self.add([{"role": "user", "content": query}], user_id=user_id, agent_id=agent_id, run_id=run_id, metadata=filters or {})
        result = {}
        if include_memories:
            result["memories"] = select_fields(res_rec.get("memories", []), memory_fields)
        if include_associations:
            result["associations"] = res_rec.get("associations", [])
        if include_persona:
            result["persona"] = res_rec.get("persona_identity")
        if include_history:
            result["history"] = hist.get("results", []) if isinstance(hist, dict) else hist
        return result

    def chat(self, query): raise NotImplementedError()

    def recollect(self, query, filters=None, limit=10, enable_graph_jump=True):
        res = self.recollection.recollect(query=query, filters=filters, limit=limit, enable_graph_jump=enable_graph_jump)
        
        # [Salto: Agentic Compaction]
        if self.config.enable_compaction and len(res.get("memories", [])) > self.config.context_window_limit * 2:
            compacted = self.reflection_engine.compact(res["memories"])
            if compacted:
                # Replace the bottom half with compacted memories
                res["memories"] = res["memories"][:self.config.context_window_limit]
                res["compacted_principles"] = compacted
                logger.info(f"Agentic Compaction active: {len(compacted)} principles generated.")

        if self.config.enable_paging:
            orch = self.orchestrator.orchestrate(res.get("memories", []))
            res["memories"], res["background_context"] = orch["active_context"], orch["background_context"]
        
        # [Salto: Proactive Heartbeats]
        if self.config.enable_heartbeat:
            heartbeat = self.reflection_engine.generate_heartbeat(res.get("memories", []))
            if heartbeat:
                res["proactive_heartbeat"] = heartbeat
                logger.info(f"Proactive Heartbeat generated: {heartbeat[:50]}...")

        return res

    def save_tool_state(self, tool_id: str, state: Dict[str, Any], user_id: str, agent_id: Optional[str] = None):
        """
        [Salto: Tool-State Memory]
        Saves the current state of a tool for later resumption.
        """
        return self.tool_state.save_state(tool_id, state, user_id, agent_id)

    def get_tool_state(self, tool_id: str, user_id: str, agent_id: Optional[str] = None):
        """
        [Salto: Tool-State Memory]
        Retrieves the last saved state of a tool.
        """
        return self.tool_state.get_state(tool_id, user_id, agent_id)

    def share_memory(self, memory_id: str, target_agent_ids: Optional[List[str]] = None):
        """
        [Salto: Memory Bridge]
        Shares a private memory with other agents.
        """
        return self.bridge.share_memory(memory_id, target_agent_ids)

