import redis.asyncio as redis
from bot.config import config

message_cache = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=0, decode_responses=True)
