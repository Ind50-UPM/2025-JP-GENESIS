## Ejemplo 1

**Usuario**
> cuántas filas hay en machine_activity

**Razonamiento**
1. El router detecta intención `count`.
2. Se selecciona la ruta determinista (`plan_sql`).
3. Se genera SQL fijo sin requerir del uso del LLM.
4. Se ejecuta la tool PostgreSQL.
5. Se sintetiza la respuesta.

**SQL ejecutado**
```sql
SELECT COUNT(*) AS n FROM public.machine_activity;
```

**Respuesta**
n = 1000


## Ejemplo 2

**Usuario**

últimas 24 horas en time_record

**Razonamiento**

1) El router detecta intención del usuario de usar time_range.
2) Se selecciona la tabla time_record.
3) Se construye SQL con filtro temporal.
4) Se ejecuta PostgreSQL.
5) Se devuelve el conteo.

**SQL ejecutado**

```sql
SELECT COUNT(*) AS n
FROM public.time_record
WHERE ts >= NOW() - INTERVAL '24 hours';
```

**Respuesta**

n = 1000

## Ejemplo 3

**Usuario**

muéstrame los nombres de las tablas del esquema público

**Razonamiento**

1) El router no detecta patrón determinista.

2) Se invoca el nodo LLM (llm_generate_sql).

3) El LLM genera una consulta SQL.

4) Se valida que sea solo lectura.

5) Se ejecuta PostgreSQL.

6) Se formatea la respuesta.

**SQL generado por el LLM**

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
LIMIT 50;
```

**Respuesta**

table_name
----------
machine_activity
time_record
...
