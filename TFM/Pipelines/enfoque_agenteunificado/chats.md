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
