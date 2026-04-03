import importlib.metadata

try:
    __version__ = importlib.metadata.version("mem0ai")
except importlib.metadata.PackageNotFoundError:
    __version__ = "2.0.0-dev"  # Development version when not installed

# Core modules (may have external dependencies)
try:
    from mem0.memory.main import AsyncMemory, Memory  # noqa
except ImportError:
    AsyncMemory = None
    Memory = None

try:
    from mem0.temporal import TemporalMemory, time_travel  # noqa
except ImportError:
    TemporalMemory = None
    time_travel = None

try:
    from mem0.mcp_server import Mem0MCPServer  # noqa
except ImportError:
    Mem0MCPServer = None

try:
    from mem0.lifecycle import LifecycleManager  # noqa
except ImportError:
    LifecycleManager = None

try:
    from mem0.enterprise import Nexus  # noqa
except ImportError:
    Nexus = None

try:
    from mem0.recollection import RecollectionEngine  # noqa
except ImportError:
    RecollectionEngine = None

# Phase 1: Quick Wins
try:
    from mem0.cache import SemanticCache, HybridCache  # noqa
except ImportError:
    SemanticCache = None
    HybridCache = None

# Phase 1.3: Reranking
try:
    from mem0.reranker.pipeline import RerankingPipeline  # noqa
except ImportError:
    RerankingPipeline = None

# Phase 1.4: Staleness Detection
try:
    from mem0.memory.staleness import StalenessDetector, StalenessConfig  # noqa
except ImportError:
    StalenessDetector = None
    StalenessConfig = None

# Phase 2: Core Improvements
try:
    from mem0.memory.procedural_memory import ProceduralMemoryStore, Procedure, MemoryCategory  # noqa
except ImportError:
    ProceduralMemoryStore = None
    Procedure = None
    MemoryCategory = None

try:
    from mem0.memory.metadata_filter import MemoryFilter, FilterBuilder  # noqa
except ImportError:
    MemoryFilter = None
    FilterBuilder = None

try:
    from mem0.privacy.consent import ConsentManager, MemoryType  # noqa
except ImportError:
    ConsentManager = None
    MemoryType = None

# Phase 3: Advanced Features
try:
    from mem0.identity.resolver import IdentityResolver  # noqa
except ImportError:
    IdentityResolver = None

try:
    from mem0.exp_index.indexer import ExperienceIndexer, OutcomeType  # noqa
except ImportError:
    ExperienceIndexer = None
    OutcomeType = None

try:
    from mem0.voice.memory import VoiceMemoryManager, VoiceMetadata  # noqa
except ImportError:
    VoiceMemoryManager = None
    VoiceMetadata = None

# Phase 3: Evaluation (moved from tests/)
try:
    from mem0.evaluation import MemoryEvaluator, EvaluationResult, EvaluationReport  # noqa
except ImportError:
    MemoryEvaluator = None
    EvaluationResult = None
    EvaluationReport = None

# Phase 4: Research-Grade
try:
    from mem0.rl.mempo import RuleBasedMemoryPolicy, MemoryAction  # noqa
except ImportError:
    RuleBasedMemoryPolicy = None
    MemoryAction = None

try:
    from mem0.memory.lifelong import SimpleMemLifelong  # noqa
except ImportError:
    SimpleMemLifelong = None

try:
    from mem0.memory.reflective import MetaCognitiveReflector  # noqa
except ImportError:
    MetaCognitiveReflector = None

# Optional LangGraph integration
try:
    from mem0.langgraph_integration import Mem0CheckpointSaver, get_checkpoint_saver  # noqa
except ImportError:
    Mem0CheckpointSaver = None
    get_checkpoint_saver = None

__all__ = [
    # Core
    "Memory",
    "AsyncMemory",
    "SemanticCache",
    "HybridCache",
    "TemporalMemory",
    "time_travel",
    "Mem0MCPServer",
    "Mem0CheckpointSaver",
    "get_checkpoint_saver",
    "LifecycleManager",
    "Nexus",
    "RecollectionEngine",
    # Phase 1
    "RerankingPipeline",
    "StalenessDetector",
    "StalenessConfig",
    # Phase 2
    "ProceduralMemoryStore",
    "Procedure",
    "MemoryCategory",
    "MemoryFilter",
    "FilterBuilder",
    "ConsentManager",
    "MemoryType",
    # Phase 3
    "IdentityResolver",
    "ExperienceIndexer",
    "OutcomeType",
    "VoiceMemoryManager",
    "VoiceMetadata",
    "MemoryEvaluator",
    "EvaluationResult",
    "EvaluationReport",
    # Phase 4
    "RuleBasedMemoryPolicy",
    "MemoryAction",
    "SimpleMemLifelong",
    "MetaCognitiveReflector",
]
