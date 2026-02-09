## Ejemplo 1 — Consulta SQL válida

**Usuario**
> sql: SELECT datname FROM pg_database LIMIT 10;

**Razonamiento**
1. El input se reconoce como SQL manual
2. Se valida que sea solo lectura
3. Se ejecuta PostgreSQL
4. Se devuelven las filas

**Respuesta**
✅ Resultado
Intent: sql
SQL:
SELECT datname FROM pg_database LIMIT 10;

```text
datname
-------
postgres
trombofilia
1245
ncorrea
2207
autosurveillance
deepquality
enel
enel_guillena
enel_lleida
```


##  Ejemplo 2 — Consulta no permitida (bloqueada)

**Usuario**

sql: DROP TABLE machine_activity;

**Razonamiento**

1) Se detecta palabra clave prohibida (DROP).

2) La ejecución se bloquea.

3) No se accede a la base de datos.

**Respuesta**

❌ Error DB: SQL no permitido (solo SELECT/WITH).
SQL:
DROP TABLE machine_activity LIMIT 50;


## Ejemplo 3 — Consulta SQL sin filas

**Usuario**

sql: SELECT * FROM machine_activity WHERE 1=0;

**Razonamiento**

1) SQL válido y de solo lectura.

2) PostgreSQL devuelve 0 filas.

3) El agente responde correctamente.

**Respuesta**

✅ Resultado
Intent: sql
SQL:
SELECT * FROM machine_activity WHERE 1=0 LIMIT 50;

```text
Sin filas.
```
