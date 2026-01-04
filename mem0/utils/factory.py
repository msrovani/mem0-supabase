import importlib
from typing import Dict, Optional, Union

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.openai import OpenAIConfig
from mem0.configs.rerankers.base import BaseRerankerConfig
from mem0.embeddings.mock import MockEmbeddings


def load_class(class_type):
    module_path, class_name = class_type.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)



class LlmFactory:
    """
    Factory for creating LLM instances with appropriate configurations.
    Supports both old-style BaseLlmConfig and new provider-specific configs.
    """

    # Provider mappings with their config classes
    provider_to_class = {
        "openai": ("mem0.llms.openai.OpenAILLM", OpenAIConfig),
        "openai_structured": ("mem0.llms.openai_structured.OpenAIStructuredLLM", OpenAIConfig),
    }

    @classmethod
    def create(cls, provider_name: str, config: Optional[Union[BaseLlmConfig, Dict]] = None, **kwargs):
        """
        Create an LLM instance with the appropriate configuration.

        Args:
            provider_name (str): The provider name (e.g., 'openai')
            config: Configuration object or dict. If None, will create default config
            **kwargs: Additional configuration parameters

        Returns:
            Configured LLM instance

        Raises:
            ValueError: If provider is not supported
        """
        if provider_name not in cls.provider_to_class:
            raise ValueError(f"Unsupported Llm provider: {provider_name}")

        class_type, config_class = cls.provider_to_class[provider_name]
        llm_class = load_class(class_type)

        # Handle configuration
        if config is None:
            # Create default config with kwargs
            config = config_class(**kwargs)
        elif isinstance(config, dict):
            # Merge dict config with kwargs
            config.update(kwargs)
            config = config_class(**config)
        elif isinstance(config, BaseLlmConfig):
            # Convert base config to provider-specific config if needed
            if config_class != BaseLlmConfig:
                # Convert to provider-specific config
                config_dict = {
                    "model": config.model,
                    "temperature": config.temperature,
                    "api_key": config.api_key,
                    "max_tokens": config.max_tokens,
                    "top_p": config.top_p,
                    "top_k": config.top_k,
                    "enable_vision": config.enable_vision,
                    "vision_details": config.vision_details,
                    "http_client_proxies": config.http_client,
                }
                config_dict.update(kwargs)
                config = config_class(**config_dict)
            else:
                # Use base config as-is
                pass
        else:
            # Assume it's already the correct config type
            pass

        return llm_class(config)

    @classmethod
    def register_provider(cls, name: str, class_path: str, config_class=None):
        """
        Register a new provider.

        Args:
            name (str): Provider name
            class_path (str): Full path to LLM class
            config_class: Configuration class for the provider (defaults to BaseLlmConfig)
        """
        if config_class is None:
            config_class = BaseLlmConfig
        cls.provider_to_class[name] = (class_path, config_class)

    @classmethod
    def get_supported_providers(cls) -> list:
        """
        Get list of supported providers.

        Returns:
            list: List of supported provider names
        """
        return list(cls.provider_to_class.keys())


class EmbedderFactory:
    provider_to_class = {
        "openai": "mem0.embeddings.openai.OpenAIEmbedding",
        "fastembed": "mem0.embeddings.fastembed.FastEmbedEmbedding",
    }

    @classmethod
    def create(cls, provider_name, config, vector_config: Optional[dict]):
        if provider_name == "upstash_vector" and vector_config and vector_config.enable_embeddings:
            return MockEmbeddings()
        class_type = cls.provider_to_class.get(provider_name)
        if class_type:
            embedder_instance = load_class(class_type)
            base_config = BaseEmbedderConfig(**config)
            return embedder_instance(base_config)
        else:
            raise ValueError(f"Unsupported Embedder provider: {provider_name}")


class VectorStoreFactory:
    provider_to_class = {
        "supabase": "mem0.vector_stores.supabase.Supabase",
    }

    @classmethod
    def create(cls, provider_name, config):
        class_type = cls.provider_to_class.get(provider_name)
        if class_type:
            if not isinstance(config, dict):
                config = config.model_dump()
            vector_store_instance = load_class(class_type)
            return vector_store_instance(**config)
        else:
            raise ValueError(f"Unsupported VectorStore provider: {provider_name}")

    @classmethod
    def reset(cls, instance):
        instance.reset()
        return instance


class GraphStoreFactory:
    """
    Factory for creating MemoryGraph instances.
    Deprecated: No Graph support in Supabase Edition.
    """

    provider_to_class = {
        "supabase": "mem0.graph_stores.supabase.SupabaseGraph",
    }

    @classmethod
    def create(cls, provider_name, config):
        class_type = cls.provider_to_class.get(provider_name)
        if class_type:
             if not isinstance(config, dict):
                 # Handle Pydantic config
                 if hasattr(config, "model_dump"):
                    config_dict = config.model_dump()
                 else:
                    # Bare object, wrap it
                    config_dict = {"config": config.config}  # Naive, might need adjustment based on config structure
             else:
                 config_dict = config
             
             # Load class
             from mem0.utils.factory import load_class
             graph_store_class = load_class(class_type)
             return graph_store_class(config)
        
        raise NotImplementedError(f"Graph Store '{provider_name}' not supported.")


class RerankerFactory:
    """
    Factory for creating reranker instances with appropriate configurations.
    Supports provider-specific configs following the same pattern as other factories.
    """

    # Provider mappings with their config classes
    provider_to_class = {
        "cohere": ("mem0.reranker.cohere_reranker.CohereReranker", BaseRerankerConfig),
    }

    @classmethod
    def create(cls, provider_name: str, config: Optional[Union[BaseRerankerConfig, Dict]] = None, **kwargs):
        if provider_name not in cls.provider_to_class:
            raise ValueError(f"Unsupported Reranker provider: {provider_name}")

        class_type, config_class = cls.provider_to_class[provider_name]
        reranker_class = load_class(class_type)

        if config is None:
            config = config_class(**kwargs)
        elif isinstance(config, dict):
            config.update(kwargs)
            config = config_class(**config)
        
        return reranker_class(config)

