# 2025-JP-GENESIS
Agentic AI for applications

TFM - UPM - Proyecto de desarrollo de Genesis 
Autor: Javier Pajares

## Estructura

Se ha diseñado un prototipo basado en el estándar API de OpenAI, el cual permite el desarrollo de un backend a través de OpenWebUI Pipelines para poder tener así un modelo que tenga la capacidad de razonamiento y procesamiento de consultas sobre el contexto existente en el PostgreSQL de Nicolás Correa. Este modelo debe ser capaz de usar múltiples agentes especializados en cada base de datos existente en el contexto mencionado.

La arquitectura se compone de las siguientes capas:

### Frontend: OpenWebUI
Interfaz de usuario para interactuar mediante conversaciones. OpenWebUI se comunica con el backend usando OpenWebUI Pipelines (conexión API propia de OpenWebUI).

### Motor de Inferencia (LLM): Ollama
Se utilizan modelos locales (en particular llama3:latest) para tareas de razonamiento generativo como la conversión de lenguaje natural a consultas en SQL.

### Capa de Razonamiento: OpenWebUI Pipelines
Actúa como backend compatible con OpenAI y como punto central de decisión del agente. Esta capa permite la creación de múltiples pipelines que puedan funcionar como modelos distintos uno del otro.

### Lógica del Agente: LangGraph
El comportamiento del agente se define mediante un grafo de ejecución en base a LangGraph. Esto permite modelar de forma clara las decisiones, el uso de herramientas y la síntesis de resultados del agente.

### Herramientas (Tools): PostgreSQL
Los agentes pueden ejecutar consultas de solo lectura sobre una base de datos PostgreSQL como herramienta externa, con validación y control de seguridad. Esto se realiza para no modificar accidentalmente las bases de datos a consultar.

## Flujo de ejecución del modelo

Usuario → OpenWebUI → Pipelines → Router
→ LLM
→ Validación SQL
→ PostgreSQL
→ Síntesis
→ OpenWebUI

### Salida
La respuesta final se devuelve a OpenWebUI en formato compatible con OpenAI, con soporte tanto para streaming como para respuestas síncronas.

