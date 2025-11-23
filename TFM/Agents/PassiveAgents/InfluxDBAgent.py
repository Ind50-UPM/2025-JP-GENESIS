from influxdb_client import InfluxDBClient
import os

class InfluxAgent:
    def __init__(self):
        self.url = os.getenv("INFLUX_URL", "http://localhost:8086")
        self.token = os.getenv("INFLUX_TOKEN", "my-token")
        self.org = os.getenv("INFLUX_ORG", "upm")
        self.bucket = os.getenv("INFLUX_BUCKET", "cedint")

        self.client = InfluxDBClient(
            url=self.url,
            token=self.token,
            org=self.org
        )

    async def run(self, query: str):
        try:
            qapi = self.client.query_api()
            tables = qapi.query(query)
            
            output = []
            for table in tables:
                for row in table.records:
                    output.append({
                        "measurement": row.get_measurement(),
                        "time": str(row.get_time()),
                        "fields": row.values
                    })

            return {"results": output}

        except Exception as e:
            return {"error": f"Influx query failed: {str(e)}"}
