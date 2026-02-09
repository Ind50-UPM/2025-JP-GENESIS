# Arquitectura y flujo de ejecución

## Capas
- Frontend: OpenWebUI (sin modificar)
- Backend: OpenWebUI Pipelines (modificable, permite la creación de uno o más scripts que son compatibles con OpenWebUI, los cuales se basan en el estándar API de OpenAI)
- Orquestación: LangGraph (grafo de decisión)
- LLM: Ollama (llama3) para transformación de lenguaje natural a SQL (NL→SQL)
- Tools: PostgreSQL (lectura) con validación de intención (para prevenir alteraciones en la base de datos a consultar)

## Control del flujo
Actualmente el controlador es el grafo (LangGraph). El LLM se integra como nodo para tareas generativas como la conversión de NL a SQL.

Siguiente paso: Lograr que el LLM seleccione herramientas/agentes explícitamente, manteniendo LangGraph como orquestador. La manera en la que se podrìa lograr esto es mediante el uso de tool calling.
