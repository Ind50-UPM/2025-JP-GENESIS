## Ejemplo 1 — Conteo por lenguaje natural

**Usuario**
> cuántas filas hay en machine_activity

**Razonamiento**
1. El router detecta intención `count`
2. Se selecciona la ruta determinista
3. Se genera SQL fijo
4. Se ejecuta PostgreSQL

**SQL**
```sql
SELECT COUNT(*) AS n FROM public.machine_activity;
```

## Ejemplo 2 — Rango temporal

**Usuario**

entre 2025-01-01 y 2025-02-01 en time_record

**Razonamiento**

1) El router detecta intención time_range

2) Se identifican fechas

3) Se genera SQL con BETWEEN

4) Se ejecuta PostgreSQL

**SQL**

SELECT COUNT(*) AS n
FROM public.time_record
WHERE ts BETWEEN '2025-01-01' AND '2025-02-01';

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

Comandos disponibles: help, ping
