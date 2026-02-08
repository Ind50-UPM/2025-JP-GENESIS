# 2025-JP-GENESIS
Agentic AI for applications

TFM - UPM - Proyecto de desarrollo de Genesis 
Autor: Javier Pajares

## Estructura

Se ha diseñado un prototipo basado en el estándar API de OpenAI, el cual permite el desarrollo de un backend a través de OpenWebUI Pipelines para poder tener así un agente que tenga la capacidad de razonamiento y procesamiento de consultas sobre el contexto existente en el PostgreSQL de Nicolás Correa.

La arquitectura se compone de las siguientes capas:

#Frontend: OpenWebUI
Interfaz de usuario para interactuar mediante conversaciones. OpenWebUI se comunica con el backend usando OpenWebUI Pipelines (conexión API propia de OpenWebUI).

#Motor de Inferencia (LLM): Ollama
Se utilizan modelos locales (en particular llama3:latest) para tareas de razonamiento generativo como la conversión de lenguaje natural a consultas en SQL.

#Capa de Razonamiento: OpenWebUI Pipelines
Actúa como backend compatible con OpenAI y como punto central de decisión del agente. Esta capa permite la creación de múltiples pipelines que puedan funcionar como modelos distintos uno del otro.

#Lógica del Agente: LangGraph
El comportamiento del agente se define mediante un grafo de ejecución en base a LangGraph. Esto permite modelar de forma clara las decisiones, el uso de herramientas y la síntesis de resultados del agente.

#Herramientas (Tools): PostgreSQL
El agente puede ejecutar consultas de solo lectura sobre una base de datos PostgreSQL como herramienta externa, con validación y control de seguridad. Esto se realiza para no modificar accidentalmente la base de datos a consultar.

## Flujo de ejecución del agente

Usuario → OpenWebUI → Pipelines → Router
→ (Ruta determinista | Ruta generativa con LLM)
→ Validación SQL
→ PostgreSQL
→ Síntesis
→ OpenWebUI

# Nodos del grafo

Nodo 1 – Router (detección de intención)
Recibe la consulta del usuario y clasifica la intención:

-Comandos de ayuda o test (help, ping)

-Consultas realizadas directamente usando queries en SQL (conteos, rangos temporales)

-Consultas en lenguaje natural libre (NL)

Nodo 2a – Planificación determinista (plan_sql)
Para consultas estructuradas (por ejemplo, conteos o rangos temporales), el agente genera SQL mediante plantillas deterministas.
Esta ruta evita el uso del LLM y reduce el riesgo de alucinaciones, además de que permite a los usuarios familiarizados con la base de datos y con SQL realizar consultas sin acceder directamente a la base de datos.

Nodo 2b – Generación de SQL con LLM (llm_generate_sql)
Para consultas en lenguaje natural libre, el agente utiliza un LLM local (llama3:latest vía Ollama) para generar la consulta SQL correspondiente.

Nodo 3 – Validación de SQL (validate_sql / validate_llm_sql)
Toda consulta SQL, independientemente de su origen, se valida antes de ejecutarse:

-Solo se permiten consultas de lectura (SELECT / WITH)

-Se bloquean operaciones DDL/DML (Create, Alter, Drop, Insert, Update, Delete)

-Se fuerza un límite máximo de filas (LIMIT)

Nodo 4 – Ejecución de herramienta (run_db)
El agente ejecuta la consulta validada en PostgreSQL utilizando el usuario lectura.

Nodo 5 – Síntesis de resultados (summarize)
Los resultados de la consulta se formatean y se convierten en una respuesta textual adecuada para el usuario.

Salida
La respuesta final se devuelve a OpenWebUI en formato compatible con OpenAI, con soporte tanto para streaming como para respuestas síncronas.

