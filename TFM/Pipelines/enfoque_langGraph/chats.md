## Ejemplo 1 — Consulta SQL válida

**Usuario**
> sql: SELECT datname FROM pg_database LIMIT 10;

**Razonamiento**
1. El input se reconoce como SQL manual
2. Se valida que sea solo lectura
3. Se ejecuta PostgreSQL
4. Se devuelven las filas

**Respuesta**
```text
datname
-------
postgres
ncorrea
...
