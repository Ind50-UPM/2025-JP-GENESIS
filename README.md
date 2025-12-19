# 2025-JP-GENESIS
Agentic AI for applications

TFM - UPM - Proyecto de desarrollo de Genesis 
Autor: Javier Pajares

## Estructura
- src/: Código fuente principal  
- data/: Datos utilizados  
- models/: Modelos entrenados o descargados  
- results/: Resultados generados  
- docs/: Documentación técnica


# TFM - Agentic Backend

## 1. Objetivo
Desarrollar un backend con un framework que pueda integrar Agentics y que permita consultar información de un edificio inteligente de la UPM (sensores, bases de datos temporales, BIM, etc.) mediante lenguaje natural, utilizando
un modelo LLM como motor de razonamiento y planificación para un chatbot que sea el puente entre la arquitectura generada y los usuarios/clientes.

## 2. Enfoque Agentic
El sistema sigue una arquitectura multi-agente con:
- Un agente activo central (CorePlanner)
- Agentes pasivos especializados en las necesidades de razonamiento para el LLM (como la lectura de información en bases de datos, cálculos matemáticos, etc.)
- Herramientas, las cuales son usadas directamente por los agentes como parte de su comportamiento

El LLM no responde directamente al usuario, sino que sigue una arquitectura y un flujo de toma de decisiones para poder hacerlo.

## 3. Arquitectura General
Usuario → Open WebUI → Backend FastAPI → CorePlanner → Agentes/Herramientas → Respuesta

## 4. Componentes
### 4.1 main.py
Capa de compatibilidad OpenAI que permite conectar Open WebUI al sistema agentic (backend).

### 4.2 Agents
- CorePlanner: agente activo que planifica y decide las acciones a realizar en el sistema, tiene libertad de poder decidir lo que los agentes pasivos pueden o no pueden ejecutar.
- Agentes pasivos: cálculo, consultas, verificación. Están sujetos a las instrucciones del CorePlanner, pero dentro de sus funciones tienen autonomía para resolver las tareas pedidas de la manera en la que consideren conveniente.

### 4.3 Tools
Funciones que ejecutan acciones concretas (queries, cálculos, etc.). Se considera que estas son las unidades básicas que terminan componiendo el conjunto de acciones que los agentes (tanto pasivos como activos) pueden realizar.

### 4.4 llm
Cliente de conexión al LLM (Ollama / servidor UPM).

## 5. Motivación
Separar razonamiento, planificación y ejecución permite:
- Trazabilidad
- Modularidad
- Seguridad
- Extensibilidad
- Evaluación de confiabilidad

