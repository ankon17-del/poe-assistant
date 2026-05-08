class PoeNinjaClient:
    async def get_currency_overview(self, league_name: str) -> dict:
        return {"league": league_name, "items": []}

