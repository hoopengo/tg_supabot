FROM postgres:15-alpine

HEALTHCHECK --interval=10s --timeout=5s --retries=5 CMD [ "pg_isready", "-U", "postgres", "-d", "hotbebrasbot_db", "-q" ]
