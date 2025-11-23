# Code for the Database Agent

import asyncpg

class DBQueryAgent:
    def __init__(self, host="localhost", db="cedint", user="postgres", password="password"):
        self.host = host
        self.db = db
        self.user = user
        self.password = password

    async def run(self, query: str):
        try:
            conn = await asyncpg.connect(
                host=self.host, database=self.db, user=self.user, password=self.password
            )
            rows = await conn.fetch(query)
            await conn.close()

            return {"rows": [dict(r) for r in rows]}
        except Exception as e:
            return {"error": f"DB query failed: {str(e)}"}

