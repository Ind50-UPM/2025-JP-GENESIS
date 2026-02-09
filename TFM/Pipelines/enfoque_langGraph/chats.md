**Usuario**

últimas 24 horas en time_record

**Razonamiento**

1) El router detecta intención time_range.
2) Se selecciona la tabla time_record.
3) Se construye SQL con filtro temporal.
4) Se ejecuta PostgreSQL.
5) Se devuelve el conteo.

**SQL ejecutado**

'''sql
SELECT COUNT(*) AS n
FROM public.time_record
WHERE ts >= NOW() - INTERVAL '24 hours';
'''

**Respuesta**

n = 18422
