from aiohttp import ClientSession

from bot.config import config

API_URL = "https://api-inference.huggingface.co/models/cointegrated/rubert-tiny-toxicity"
HEADERS = {"Authorization": f"Bearer {config.HF_TOKEN}"}


async def is_toxic(text) -> bool:
    async with ClientSession(headers=HEADERS) as session:
        response = await session.post(API_URL, json={"inputs": text})

        if response.status in [404, 500, 503]:
            return False  # https://youtube.com/shorts/o6Ei6XMVNEU?si=kPBVuIDKnTClim9V

        result_list = (await response.json())[0]

        if result_list[0]["label"] == "non-toxic":
            return False
        elif result_list[0]["score"] >= config.BASE_TOXICITY_ENCOURAGE:
            return True
