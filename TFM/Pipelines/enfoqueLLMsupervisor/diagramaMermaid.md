flowchart TD
    Start([Usuario envía mensaje]) --> Pipeline[Pipeline.pipe]
    Pipeline --> CheckLangGraph{LangGraph<br/>disponible?}
    CheckLangGraph -->|No| ErrorLG[❌ Error: LangGraph no disponible]
    CheckLangGraph -->|Sí| ExtractMsg[Extraer mensaje del usuario]
    ExtractMsg --> CheckGreeting{Es saludo<br/>o ayuda?}
    CheckGreeting -->|Sí| DirectResponse[Respuesta directa amigable]
    CheckGreeting -->|No| StartGraph[Iniciar LangGraph]
    StartGraph --> NodeInput[Node: Input<br/>Recibe estado inicial]
    NodeInput --> NodeSupervisor[Node: Supervisor<br/>Analiza la solicitud]
    NodeSupervisor --> QuickDetect{Pregunta sobre<br/>BDs disponibles?}
    QuickDetect -->|Sí| QuickAnswer[Respuesta directa<br/>con lista de BDs]
    QuickDetect -->|No| CallOllama[Llamar a Ollama LLM]
    CallOllama --> RetryLoop{Reintentos<br/>< MAX_RETRIES?}
    RetryLoop -->|No| Fallback[Plan fallback:<br/>route=direct, mensaje de ayuda]
    RetryLoop -->|Sí| PostOllama[POST a /api/generate]
    PostOllama --> ParseResponse{Respuesta<br/>HTTP 200?}
    ParseResponse -->|No| RetryLoop
    ParseResponse -->|Sí| ExtractJSON[Extraer objeto JSON<br/>de la respuesta]
    ExtractJSON --> ValidJSON{JSON<br/>válido?}
    ValidJSON -->|No| RetryLoop
    ValidJSON -->|Sí| FixErrors[Corregir errores comunes<br/>ej: pg_direct → direct]
    FixErrors --> ValidatePlan[Validar plan]
    ValidatePlan --> PlanValid{Plan<br/>válido?}
    PlanValid -->|No| InvalidPlan[Plan inválido:<br/>route=direct con mensaje de ayuda]
    PlanValid -->|Sí| SetRoute[Establecer route en el estado]
    QuickAnswer --> SetRoute
    Fallback --> SetRoute
    InvalidPlan --> SetRoute
    SetRoute --> RouteDecision{route en<br/>AGENTS?}
    RouteDecision -->|No - direct| NodeDone[Node: Done<br/>Preparar respuesta final]
    RouteDecision -->|Sí - pg_*| NodePostgres[Node: Postgres Agent<br/>Ejecutar consulta SQL]
    NodePostgres --> CheckPsycopg2{psycopg2<br/>disponible?}
    CheckPsycopg2 -->|No| DBError1[Error: psycopg2 no disponible]
    CheckPsycopg2 -->|Sí| CheckReadOnly{SQL es<br/>solo lectura?}
    CheckReadOnly -->|No| DBError2[Error: SQL no permitido<br/>solo SELECT/WITH]
    CheckReadOnly -->|Sí| NormalizeSQL[Normalizar SQL<br/>agregar/validar LIMIT]
    NormalizeSQL --> ConnectDB[Conectar a PostgreSQL<br/>readonly mode]
    ConnectDB --> ExecuteSQL{Ejecución<br/>exitosa?}
    ExecuteSQL -->|No| DBError3[Error de ejecución SQL]
    ExecuteSQL -->|Sí| FetchRows[Obtener filas<br/>máximo MAX_LIMIT]
    FetchRows --> CloseConn[Cerrar conexión]
    CloseConn --> DBSuccess[Resultado exitoso<br/>con filas]
    DBError1 --> NodeDone
    DBError2 --> NodeDone
    DBError3 --> NodeDone
    DBSuccess --> NodeDone
    NodeDone --> CheckRoute{Tipo de<br/>respuesta?}
    CheckRoute -->|direct| FormatDirect[Formatear respuesta<br/>conversacional]
    CheckRoute -->|query exitosa| FormatSuccess[Formatear resultado SQL<br/>✅ con tabla y stats]
    CheckRoute -->|query error| FormatError[Formatear mensaje error<br/>❌ con detalles]
    CheckRoute -->|query sin filas| FormatEmpty[Formatear mensaje<br/>ℹ️ sin resultados]
    FormatDirect --> PrepareOutput[Preparar output final]
    FormatSuccess --> PrepareOutput
    FormatError --> PrepareOutput
    FormatEmpty --> PrepareOutput
    DirectResponse --> PrepareOutput
    ErrorLG --> PrepareOutput
    PrepareOutput --> StreamMode{Modo<br/>stream?}
    StreamMode -->|Sí| SSEStream[Generar SSE chunks<br/>data: JSON]
    StreamMode -->|No| NonStream[Generar respuesta completa<br/>JSON]
    SSEStream --> Return([Retornar al usuario])
    NonStream --> Return
    style Start fill:#e1f5e1
    style Return fill:#e1f5e1
    style ErrorLG fill:#ffe1e1
    style DBError1 fill:#ffe1e1
    style DBError2 fill:#ffe1e1
    style DBError3 fill:#ffe1e1
    style FormatError fill:#ffe1e1
    style DBSuccess fill:#e1f0ff
    style FormatSuccess fill:#e1f0ff
    style DirectResponse fill:#fff9e1
    style QuickAnswer fill:#fff9e1
    style CallOllama fill:#f0e1ff
    style NodeSupervisor fill:#f0e1ff
    style NodePostgres fill:#e1f0ff
    style NodeDone fill:#ffe1f5
