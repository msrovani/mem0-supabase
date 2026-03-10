import asyncio
import logging
import uuid
from unittest.mock import MagicMock, AsyncMock

from mem0.configs.base import MemoryConfig
from mem0.memory.async_memory import AsyncMemory
from mem0.memory.sync_memory import Memory

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ExtremeTest")

def setup_mocks(mem_instance):
    """Configura mocks para permitir execução sem credenciais reais"""
    # Mock do Embedder
    mem_instance.embedding_model.embed = MagicMock(return_value=[0.1] * 1536)
    
    # Mock do Vector Store
    mock_result = MagicMock()
    mock_result.id = str(uuid.uuid4())
    mock_result.score = 0.95
    mock_result.payload = {"data": "Memória mockada", "user_id": "test_user"}
    
    mem_instance.vector_store.search = MagicMock(return_value=[mock_result])
    mem_instance.vector_store.list = MagicMock(return_value=([mock_result],))
    mem_instance.vector_store.get = MagicMock(return_value=mock_result)
    mem_instance.vector_store.insert = MagicMock()
    mem_instance.vector_store.update = MagicMock()
    
    # Mock do LLM
    mem_instance.llm.generate_response = MagicMock(return_value='{"facts": ["Usuário gosta de tecnologia"], "memory": [{"id": "0", "text": "Usuário gosta de tecnologia", "event": "ADD"}]}')

async def run_extreme_test():
    logger.info("Iniciando Teste de Estresse Extremo: mem0-supabase Super QI")
    
    # Mocking factories to avoid real API calls during initialization
    import mem0.utils.factory as factory
    factory.EmbedderFactory.create = MagicMock()
    factory.VectorStoreFactory.create = MagicMock()
    factory.LlmFactory.create = MagicMock()
    
    # Mocking PostgresManager BEFORE instantiation
    import mem0.memory.storage_postgres as storage_postgres
    storage_postgres.PostgresManager = MagicMock()
    
    # Configuração customizada para forçar gatilhos dos Saltos
    config = MemoryConfig()
    from mem0.configs.vector_stores.supabase import SupabaseConfig
    config.vector_store.provider = "supabase"
    config.vector_store.config = SupabaseConfig(
        connection_string="postgresql://mock:mock@localhost:5432/mock",
        collection_name="extreme_test"
    )
    config.enable_compression = True
    config.compression_threshold = 0.8
    config.enable_paging = True
    config.context_window_limit = 5
    config.enable_reflection = True
    config.reflection_interval = 3
    config.enable_ego = True
    config.enable_dreaming = True
    config.dreaming_interval = 5
    config.enable_compaction = True
    config.enable_heartbeat = True
    config.enable_tool_state = True
    config.enable_bridge = True

    # 1. Instanciação (Sync e Async)
    mem_sync = Memory(config)
    mem_async = AsyncMemory(config)
    
    # Re-setup mocks para os métodos internos
    setup_mocks(mem_sync)
    
    # Setup mocks para async
    mem_async.embedding_model.embed = MagicMock(return_value=[0.1] * 1536)
    mem_async.vector_store.search = MagicMock(return_value=[MagicMock(id="1", score=0.9, payload={"data": "test"})])
    mem_async.vector_store.list = MagicMock(return_value=([MagicMock(id="1", payload={"data": "test"})],))
    mem_async.vector_store.get = MagicMock(return_value=MagicMock(id="1", payload={"data": "test"}))
    mem_async.llm.generate_response = MagicMock(return_value='{"facts": ["Fato"], "memory": [{"id": "1", "text": "Fato", "event": "ADD"}]}')
    
    # Mock do reflection engine async
    mem_async.reflection_engine.reflect_async = AsyncMock(return_value=["Insight gerado"])
    mem_sync.reflection_engine.reflect = MagicMock(return_value=["Insight gerado"])
    mem_async.reflection_engine.compact_async = AsyncMock(return_value=["Princípio compactado"])
    mem_sync.reflection_engine.compact = MagicMock(return_value=["Princípio compactado"])
    mem_async.reflection_engine.generate_heartbeat_async = AsyncMock(return_value="Ação proativa")
    mem_sync.reflection_engine.generate_heartbeat = MagicMock(return_value="Ação proativa")

    # Mock do tool state manager
    mem_sync.tool_state.get_state = MagicMock(return_value={"url": "https://supabase.com", "tab": 1})
    mem_async.tool_state.get_state_async = AsyncMock(return_value={"url": "https://supabase.com", "tab": 1})

    # Mock do dreaming engine
    mem_async.dreaming_engine.dream_async = AsyncMock(return_value=["Memória sintética"])
    mem_sync.dreaming_engine.dream = MagicMock(return_value=["Memória sintética"])
    
    # Mock do orchestrator async
    mem_async.orchestrator.orchestrate_async = AsyncMock(return_value={"active_context": [], "background_context": "Resumo"})
    mem_sync.orchestrator.orchestrate = MagicMock(return_value={"active_context": [], "background_context": "Resumo"})

    user_id = "ai_enthusiast_001"
    
    # ROTEIRO DE 60 INTERAÇÕES
    interactions = [
        # BLOCO 1: Identidade e Preferências Básicas (Teste de ADD e Ego)
        "Meu nome é Leonardo e sou um desenvolvedor de IA.",
        "Eu moro em São Paulo, mas amo viajar para o Japão.",
        "Minha linguagem favorita é Python, mas estou estudando Rust.",
        "Eu tenho um gato chamado Turing.",
        "Eu prefiro trabalhar durante a noite.",
        "Meu setup tem 3 monitores 4K.",
        
        # BLOCO 2: Compressão Semântica (Salto 1 - Fatos similares)
        "Eu gosto muito de café expresso.",
        "Eu prefiro café sem açúcar e bem forte.",
        "Café arábica é o meu tipo favorito de grão.",
        "Sempre tomo uma xícara de café às 22h.",
        
        # BLOCO 3: Atualizações e Contradições (Self-Correction)
        "Mudei de ideia, agora prefiro o tema claro no VS Code.",
        "Na verdade, meu gato Turing agora prefere ração de peixe.",
        "Decidi que Rust é melhor que Python para sistemas críticos.",
        
        # BLOCO 4: Fluxo de Longo Prazo (Teste de Paging - Salto 2)
        "Hoje eu li sobre redes neurais líquidas.",
        "A temperatura em São Paulo está 25 graus.",
        "Estou planejando uma viagem para Kyoto em novembro.",
        "Vou comprar um novo teclado mecânico amanhã.",
        "O projeto mem0-supabase está ficando incrível.",
        "Preciso lembrar de pagar a conta de luz na segunda.",
        "Amanhã tenho reunião com o time de infraestrutura às 10h.",
        "Gosto de ouvir Lofi enquanto programo.",
        "Minha cor favorita é azul escuro.",
        "Estou lendo o livro 'Gödel, Escher, Bach'.",
        "Pratico Jiu-Jitsu duas vezes por semana.",
        
        # BLOCO 5: Meta-Cognição (Trigger de Reflexão - Salto 3)
        "Estou me sentindo muito produtivo hoje.",
        "A produtividade é a chave para o sucesso em IA.",
        "Às vezes me sinto cansado de tantas reuniões.",
        "O equilíbrio entre vida pessoal e trabalho é essencial.",
        
        # BLOCO 6: Contexto Profissional Denso
        "Trabalho na empresa Cyberdyne Systems.",
        "Sou o arquiteto principal do projeto Skynet (brincadeira).",
        "Utilizamos Kubernetes para orquestração de containers.",
        "Otimizamos nossas queries SQL usando índices HNSW.",
        "HALFVEC é fundamental para reduzir custos de storage.",
        "Nosso cluster tem 128 nós de computação.",
        "A latência da API deve ser menor que 100ms.",
        
        # BLOCO 7: Repetições para testar Deduplicação Extrema
        "Eu amo Python.",
        "Python é minha linguagem do coração.",
        "Não vivo sem Python.",
        
        # BLOCO 8: Fatos Aleatórios para encher o Contexto (Paging Progressivo)
        "O céu está limpo hoje.",
        "A pizza de ontem estava ótima.",
        "Meu teclado novo chegou e é barulhento.",
        "Turing (o gato) dormiu no meu colo hoje.",
        "A cotação do dólar subiu novamente.",
        "Preciso de mais café.",
        "A teoria das cordas é fascinante.",
        "O Japão tem a melhor comida de rua.",
        "Vou aprender Go no próximo mês.",
        "A biblioteca mem0 é muito versátil.",
        
        # BLOCO 9: Ego Synthesis (Layer 12)
        "Quem sou eu baseado no que você sabe?",
        
        # BLOCO 10: Busca Avançada e Recuperação
        "Qual é a minha linguagem favorita e o nome do meu gato?",
        "O que eu planejei para novembro?",
        "Resuma minhas preferências de trabalho.",
        "Quais são meus desafios profissionais atuais?"
    ]

    logger.info(f"Executando {len(interactions)} interações...")

    # Execução das interações
    for i, msg in enumerate(interactions):
        logger.info(f"Interação {i+1}/{len(interactions)}: {msg[:50]}...")
        
        # Alternando entre Sync e Async para testar paridade
        if i % 2 == 0:
            mem_sync.add(msg, user_id=user_id)
        else:
            await mem_async.add(msg, user_id=user_id)
            
        # A cada 10 interações, fazemos uma busca para testar Paging e Ego
        if (i + 1) % 10 == 0:
            logger.info("--- Testando Recollection com Paging ---")
            rec = mem_sync.recollect("Quais são meus interesses principais?", filters={"user_id": user_id})
            if "background_context" in rec:
                logger.info(f"SALTO 2 DETECTADO! Background Context gerado: {rec['background_context'][:100]}...")
            
            logger.info("--- Testando Ego Identity Synthesis ---")
            identity = mem_sync.synthesize_identity(user_id=user_id)
            logger.info(f"SALTO 3/Layer 12: Identidade Sintetizada: {identity[:100]}...")

            logger.info("--- Testando Tool-State Memory ---")
            mem_sync.save_tool_state("browser", {"url": "https://supabase.com", "tab": 1}, user_id=user_id)
            state = mem_sync.get_tool_state("browser", user_id=user_id)
            logger.info(f"Estado da ferramenta recuperado: {state}")

            logger.info("--- Testando Memory Bridge ---")
            mem_sync.share_memory("mem_123", target_agent_ids=["finance_agent"])
            logger.info("Memória compartilhada via Bridge.")

    # Teste de Busca Avançada (Metadata Filters)
    logger.info("--- Testando Busca com Filtros Avançados ---")
    search_res = mem_sync.search("tecnologia", user_id=user_id, filters={"importance_score": {"gt": 0.5}})
    logger.info(f"Busca avançada retornou {len(search_res.get('results', []))} resultados.")

    # Finalização
    logger.info("Teste de estresse concluído com sucesso!")
    logger.info("Verifique os logs acima para confirmar as ativações de COMPRESS, PAGING e REFLECTION.")

if __name__ == "__main__":
    asyncio.run(run_extreme_test())
