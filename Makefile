restart:
	docker compose up -d --build && docker logs tg_supabot-bot-1 --follow
stop:
	docker compose down -v
alembic-revision: # make alembic-revision COMMENT="your comment"
	docker exec -it tg_supabot-bot-1 bash -c "alembic revision --autogenerate -m \"${COMMENT}\""
relogs:
	docker logs tg_supabot-bot-1 --follow
psql:
	docker exec -it --user postgres tg_supabot-bot-1  psql
