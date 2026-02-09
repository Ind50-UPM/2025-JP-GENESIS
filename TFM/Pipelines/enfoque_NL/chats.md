## Ejemplo 1 — Conteo por lenguaje natural

**Usuario**
> nl: cuántas filas hay en machine_activity

**Razonamiento**
1. El router detecta intención `count`
2. Se selecciona la ruta determinista
3. Se genera SQL fijo
4. Se ejecuta PostgreSQL

**SQL**
```sql
SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'machine_activity' LIMIT 50;
```

**Resultado**
🤖 NL→SQL (Ollama) + ejecución en PostgreSQL

Pregunta:
cuántas filas hay en machine_activity

SQL generado:
SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'machine_activity' LIMIT 50;

Filas devueltas: 1 (total reportado: 1)

```text
count   
--------
1       
```

## Ejemplo 2 — Rango temporal

**Usuario**

nl: entre 2025-01-01 y 2025-02-01 en time_record usando ts en vez de timestamp

**Razonamiento**

1) El router detecta intención time_range

2) Se identifican fechas

3) Se genera SQL con BETWEEN

4) Se ejecuta PostgreSQL

**SQL**

SELECT *
FROM time_record
WHERE "ts" >= '2025-01-01'::timestamp AND "ts" < '2025-02-01'::timestamp LIMIT 50;

**Respuesta**

n = 89341

## Ejemplo 3 — Comando de ayuda

**Usuario**

help

**Razonamiento**

1) El router detecta intención de usar el comando help

2) No se consulta la base de datos

3) Se devuelve mensaje informativo

**Respuesta**

Comandos:
- `ping`
- `lista tablas`
- `sql: <SELECT ...>` (manual)
- `nl: <pregunta en español>` (NL→SQL)

Ejemplos NL:
- `nl: cuántas filas hay en variable`
- `nl: muestra 5 filas de variable_log_float`
