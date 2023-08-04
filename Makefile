restart:
	docker compose up -f docker-compose.yml -d --build && docker logs tg_supabot-bot-1 --follow
stop:
	docker compose down -v