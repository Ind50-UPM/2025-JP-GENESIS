Code for the Database Agent


# influx_agent.py
import os
from influxdb_client import InfluxDBClient
from influxdb_client.client.query_api import QueryApi

INFLUX_URL = os.getenv("INFLUX_URL","http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN","token")
INFLUX_ORG = os.getenv("INFLUX_ORG","org")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET","bucket")

class InfluxDBAgent:
    def __init__(self):
        self.client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        self.query_api = self.client.query_api()

    def build_query(self, text: str) -> str:
        t = text.lower()
        if "average" in t or "mean" in t:
            return f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_field"] == "value")
  |> mean()
'''
        if "last" in t and "hour" in t:
            return f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_field"] == "value")
  |> last()
'''
        raise ValueError("Cannot build flux query from text")

    def execute_query(self, flux: str):
        res = self.query_api.query(org=INFLUX_ORG, query=flux)
        rows=[]
        for table in res:
            for record in table.records:
                rows.append({
                    "time": record.get_time().isoformat(),
                    "value": record.get_value(),
                    "measurement": record.get_measurement(),
                    "field": record.get_field()
                })
        return rows

    def run(self, context: dict):
        text = context.get("text","")
        try:
            flux = self.build_query(text)
        except ValueError as e:
            return {"error": str(e)}
        try:
            rows = self.execute_query(flux)
        except Exception as e:
            return {"error": f"query error: {e}"}
        return {"rows": rows, "count": len(rows)}


#####################


# run_query.py
import os
import asyncpg
import sqlite3
import pandas as pd

ALLOWED_TABLES = {"variable", "variable_log_float", "variable_log_string"}

def check_security(sql: str):
    ls = sql.lower()
    if any(w in ls for w in ["delete", "drop", "insert", "update"]):
        raise ValueError("QUERY BLOCKED: Modificación de datos no permitida.")

    for table in ALLOWED_TABLES:
        if table in ls:
            return

    raise ValueError("QUERY BLOCKED: Tabla no permitida.")

async def run_query(sql: str):
    check_security(sql)

    DB_TYPE = os.getenv("DB_TYPE", "postgres")

    if DB_TYPE == "postgres":
        conn = await asyncpg.connect(
            user=os.getenv("PG_USER"),
            password=os.getenv("PG_PASSWORD"),
            database=os.getenv("PG_DB"),
            host=os.getenv("PG_HOST"),
            port=os.getenv("PG_PORT", 5432)
        )
        rows = await conn.fetch(sql)
        await conn.close()
        return {"rows": [dict(r) for r in rows], "count": len(rows)}

    # Fallback: SQLite
    else:
        conn = sqlite3.connect("db/sqlite_demo.db")
        df = pd.read_sql_query(sql, conn)
        conn.close()
        return {"rows": df.to_dict(orient="records"), "count": len(df)}
