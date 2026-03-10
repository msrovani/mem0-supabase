# Workflow de Documentação

## Objetivo
Manter a documentação alinhada com as capacidades cognitivas e com as implementações do `mem0-supabase`, garantindo consistência entre código, exemplos e navegação.

## Etapas do Workflow
1. **Inventário**: listar todos os documentos ativos (README, docs/, arquitetura, setup, open-source, core-concepts).
2. **Leitura crítica**: identificar inconsistências (camadas, nomes de recursos, links quebrados).
3. **Alinhamento técnico**: atualizar descrições para refletir implementações reais (Dreaming, Compaction, Tool-State, Bridge, Heartbeats, Paging).
4. **Atualização de navegação**: ajustar links, menus e referências cruzadas.
5. **Registro de mudanças**: documentar diferenças e implementações efetivamente executadas.
6. **Revisão final**: checagem rápida de consistência textual e exemplos.

## Registro desta Rodada

### Diferenças identificadas
- Menção a “11 camadas” em partes da documentação, enquanto o sistema é 12-layer.
- Links de arquitetura apontando para arquivos inexistentes ou fora do repositório.
- Ausência de flags novas (Dreaming, Compaction, Heartbeats, Tool-State, Bridge) na configuração.
- Operações de memória sem referência a Paging, Compaction e Heartbeats.

### Implementações executadas
- Atualização das camadas e links técnicos em [memory_layers.mdx](file:///c:/Users/bm2311640/Documents/trae_projects/mem0-supabase/mem0-supabase-main/docs/architecture/memory_layers.mdx).
- Alinhamento do setup para 12 camadas e suporte ao novo pipeline em [SETUP.md](file:///c:/Users/bm2311640/Documents/trae_projects/mem0-supabase/mem0-supabase-main/docs/SETUP.md).
- Inclusão de Tool-State, Bridge, Paging, Compaction e Heartbeats em [memory-operations.mdx](file:///c:/Users/bm2311640/Documents/trae_projects/mem0-supabase/mem0-supabase-main/docs/core-concepts/memory-operations.mdx).
- Inclusão de flags cognitivas em [configuration.mdx](file:///c:/Users/bm2311640/Documents/trae_projects/mem0-supabase/mem0-supabase-main/docs/open-source/configuration.mdx).
- Ajustes de links e release notes em [README.md](file:///c:/Users/bm2311640/Documents/trae_projects/mem0-supabase/mem0-supabase-main/README.md).
- Atualização de inovações Supabase e Super IQ em [supabase_innovations.md](file:///c:/Users/bm2311640/Documents/trae_projects/mem0-supabase/mem0-supabase-main/docs/architecture/supabase_innovations.md).
- Reforço do posicionamento de 12 camadas em [introduction.mdx](file:///c:/Users/bm2311640/Documents/trae_projects/mem0-supabase/mem0-supabase-main/docs/introduction.mdx) e [docs/README.md](file:///c:/Users/bm2311640/Documents/trae_projects/mem0-supabase/mem0-supabase-main/docs/README.md).

### Implementações técnicas relacionadas
- Dreaming Engine: [dreaming.py](file:///c:/Users/bm2311640/Documents/trae_projects/mem0-supabase/mem0-supabase-main/mem0/memory/dreaming.py)
- Reflection + Compaction + Heartbeats: [reflection.py](file:///c:/Users/bm2311640/Documents/trae_projects/mem0-supabase/mem0-supabase-main/mem0/memory/reflection.py)
- Tool-State Memory: [tool_state.py](file:///c:/Users/bm2311640/Documents/trae_projects/mem0-supabase/mem0-supabase-main/mem0/memory/tool_state.py)
- Memory Bridge: [bridge.py](file:///c:/Users/bm2311640/Documents/trae_projects/mem0-supabase/mem0-supabase-main/mem0/memory/bridge.py)
- Orchestrator (Paging): [orchestrator.py](file:///c:/Users/bm2311640/Documents/trae_projects/mem0-supabase/mem0-supabase-main/mem0/memory/orchestrator.py)

