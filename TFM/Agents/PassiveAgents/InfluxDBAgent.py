# backend/agent/tools/influx_agent.py

import os
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS

# Load environment variables
load_dotenv()

INFLUXDB_URL = os.getenv("INFLUXDB_URL")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET")


class InfluxDBAgent:
    """
    Passive agent for querying time-series data from InfluxDB.
    Does not have planning — only receives a query and returns results.
    """

    def __init__(self):
        if not all([INFLUXDB_URL, INFLUXDB_TOKEN, INFLUXDB_ORG, INFLUXDB_BUCKET]):
            raise ValueError("❌ Missing one or more required InfluxDB variables in .env")

        try:
            self.client = InfluxDBClient(
                url=INFLUXDB_URL,
                token=INFLUXDB_TOKEN,
                org=INFLUXDB_ORG,
                verify_ssl=False
            )
            self.query_api = self.client.query_api()
        except Exception as e:
            raise RuntimeError(f"❌ Could not initialize InfluxDB client: {str(e)}")

    def run_query(self, flux_query: str):
        """
        Executes a FLUX query in InfluxDB.

        Args:
            flux_query (str): A valid Flux query string.

        Returns:
            list: Parsed result rows or an error description.
        """

        try:
            tables = self.query_api.query(flux_query)

            results = []
            for table in tables:
                for row in table.records:
                    results.append({
                        "measurement": row.get_measurement(),
                        "field": row.get_field(),
                        "value": row.get_value(),
                        "time": row.get_time().isoformat()
                    })

            return {
                "success": True,
                "count": len(results),
                "results": results
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# Helper function for LLM agent dispatcher
def influx_query_tool(query: str) -> str:
    """
    Wrapper tool that the LLM can call directly.

    Args:
        query (str): flux query string

    Returns:
        str: JSON-like formatted response
    """
    try:
        agent = InfluxDBAgent()
        result = agent.run_query(query)
        return str(result)
    except Exception as e:
        return f"❌ InfluxDB tool error: {str(e)}"

