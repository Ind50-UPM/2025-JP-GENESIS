# Arquitectura y flujo de ejecución

## Capas
- Frontend: OpenWebUI (sin modificar)
- Backend: OpenWebUI Pipelines (modificable, permite la creación de uno o más scripts que son compatibles con OpenWebUI, los cuales se basan en el estándar API de OpenAI)
- Orquestación: LangGraph (grafo de decisión)
- LLM: Ollama (llama3) para transformación de lenguaje natural a SQL (NL→SQL)
- Tools: PostgreSQL (lectura) con validación de intención (para prevenir alteraciones en la base de datos a consultar)

## Control del flujo
Actualmente el controlador es el LLM. El LLM es capaz de decidir cuál es la ruta a seguir para responder a la consulta hecha por el usuario.

Siguiente paso: Lograr que el LLM tenga una mayor libertad de decisión, ya que actualmente los caminos que toma el LLM son bastante estrictos y limitados.
