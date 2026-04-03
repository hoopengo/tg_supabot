import asyncio

from aiohttp import ClientSession

from bot.config import config

API_URL = "https://router.huggingface.co/hf-inference/models/cointegrated/rubert-tiny-toxicity"
HEADERS = {"Authorization": f"Bearer {config.HF_TOKEN}"}

_session: ClientSession | None = None


def _get_session() -> ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = ClientSession(headers=HEADERS)
    return _session


async def is_toxic(text) -> bool:
    session = _get_session()
    try:
        async with asyncio.timeout(3):
            response = await session.post(API_URL, json={"inputs": text})

            if response.status != 200:
                return False

            data = await response.json()

            if not isinstance(data, list) or not data or not isinstance(data[0], list):
                return False

            result_list = data[0]

            if result_list[0]["label"] == "non-toxic":
                return False
            if result_list[0]["score"] >= config.BASE_TOXICITY_ENCOURAGE:
                return True
            return False
    except (TimeoutError, Exception):
        return False
