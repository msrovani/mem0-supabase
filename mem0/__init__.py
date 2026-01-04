import importlib.metadata

__version__ = importlib.metadata.version("mem0ai")

from mem0.memory.main import AsyncMemory, Memory  # noqa
from mem0.cache import SemanticCache  # noqa
from mem0.temporal import TemporalMemory, time_travel  # noqa
from mem0.mcp_server import Mem0MCPServer  # noqa
from mem0.lifecycle import LifecycleManager  # noqa
from mem0.enterprise import Nexus  # noqa
from mem0.recollection import RecollectionEngine  # noqa

# Optional LangGraph integration
try:
    from mem0.langgraph_integration import Mem0CheckpointSaver, get_checkpoint_saver  # noqa
except ImportError:
    Mem0CheckpointSaver = None
    get_checkpoint_saver = None

__all__ = [
    "Memory",
    "AsyncMemory",
    "SemanticCache",
    "TemporalMemory",
    "time_travel",
    "Mem0MCPServer",
    "Mem0CheckpointSaver",
    "get_checkpoint_saver",
    "LifecycleManager",
    "Nexus",
    "RecollectionEngine",
]
