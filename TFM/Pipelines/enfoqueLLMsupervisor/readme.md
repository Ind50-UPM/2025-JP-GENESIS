# Caso 4 - LLM implementado en forma de supervisor, el cual dispone de agentes para cada base de datos existente y que permite conversaciones con lenguaje natural con el usuario

## Objetivo
Lograr que el usuario, mediante lenguaje natural, pueda interactuar con este modelo para obtener informaciòn sobre las bases de datos existentes y que el modelo pueda usar un razonamiento estructurado en LangGraph para poder procesar esta consulta, a través del uso de agentes especializados en cada base de datos presente.

## Componentes
- OpenWebUI (frontend)
- OpenWebUI Pipelines
- Ollama: llama3:latest
- PostgreSQL: sí
- LangGraph/LangChain: sí

## Componentes LangGraph utilizados

---

### **StateGraph**

```python
g = StateGraph(AgentState)
```

#### Función

* Define el grafo de estados del agente
* Es la estructura central donde se declaran nodos, transiciones y estado compartido
* Permite modelar el flujo de razonamiento como un proceso explícito y controlado
* Es el motor de orquestación del sistema, formaliza el razonamiento del modelo
* Permite separar decisiones, ejecución de herramientas y generación de respuesta

---

### **AgentState**

```python
class AgentState(TypedDict, total=False):
    user_text: str
    plan: dict
    route: str
    db_result: dict
    answer: str
```

#### Función

* Define la memoria compartida entre nodos
* Cada nodo puede leer y modificar partes del estado
* Hace explícito el estado cognitivo del sistema en cada paso
* Es la memoria de trabajo del agente, permite trazabilidad del razonamiento
* Facilita depuración y análisis del flujo

---

### **Nodos (add_node)**

```python
g.add_node("input", node_input)
g.add_node("supervisor", node_supervisor)
g.add_node("postgres_agent", node_postgres_agent)
g.add_node("done", node_done)
```

#### Función

* Cada nodo encapsula una unidad funcional del sistema
* Separan claramente:

  * Interpretación
  * Planificación
  * Ejecución
  * Respuesta

---

### **Supervisor LLM**

El supervisor utiliza un modelo (Ollama + Llama3) con un prompt estructurado que obliga a devolver un JSON con el siguiente esquema:

```json
{
  "route": "...",
  "action": "query | answer",
  "sql": "...",
  "answer": "..."
}
```

#### Función

* Actúa como cerebro estratégico o supervisor, está encargado de la planificación del razonamiento
* Decide qué agente especializado debe actuar
* No ejecuta directamente herramientas
* No accede directamente a bases de datos
* Separa planificación de ejecución
* Implementa una arquitectura de tipo supervisor-worker

---

### **Agentes especializados por base de datos**

Cada base de datos PostgreSQL tiene una instancia:

```python
PostgresSafeAgent(route="pg_ncorrea", dbname="ncorrea")
PostgresSafeAgent(route="pg_enel", dbname="enel")
...
```

#### Función

* Ejecutar consultas únicamente en su base de datos asignada
* Validar que el SQL sea de solo lectura
* Forzar límites de seguridad
* Conectar en modo `readonly`
* Registrar métricas

#### Qué representan en el sistema

* Agentes especializados por familia de datos
* Permiten tener modularidad y escalabilidad
* Permiten la separación de responsabilidades

---

### **Transiciones condicionales**

```python
g.add_conditional_edges("supervisor", route_function, {...})
```

#### Función

* Implementan el razonamiento como decisión de ruta
* El flujo cambia dinámicamente según el `route` decidido por el supervisor
* Permiten arquitectura multi-agente
* El sistema no es lineal, es un grafo dinámico controlado por decisión cognitiva

---

### **Transiciones secuenciales**

```python
g.add_edge("postgres_agent", "done")
```

#### Función

* Definen el flujo tras una decisión
* Permiten encadenar ejecución con respuesta

---

### **Estado final (END)**

```python
from langgraph.graph import END
g.add_edge("done", END)
```

#### Función

* Marca el final del razonamiento
* El sistema devuelve una respuesta estructurada compatible con OpenAI API

---

### **Compilación del grafo**

```python
GRAPH = g.compile()
```

#### Función

* Convierte la definición declarativa en un ejecutable
* Permite invocar el agente con:

```python
GRAPH.invoke({...})
```

---

## Seguridad en la ejecución SQL

El sistema implementa múltiples capas de protección:

* Validación por regex (bloqueo de INSERT/UPDATE/DELETE/etc.)
* Validación del primer token SQL
* Forzado de `LIMIT`
* Conexión en modo `readonly`
* Usuario PostgreSQL con permisos restringidos
* Timeout de conexión
* Límite máximo de filas
* Recorte de salida excesiva

Esto evita que el LLM pueda ejecutar operaciones destructivas.

---

## Flujo general del sistema

```text
Usuario
   ↓
OpenWebUI
   ↓
Pipeline
   ↓
LangGraph
   ↓
Supervisor (LLM)
   ↓
Agente PostgreSQL especializado
   ↓
Base de Datos
   ↓
Respuesta formateada
   ↓
Usuario
```

---

## Flujo representado en Mermaid



