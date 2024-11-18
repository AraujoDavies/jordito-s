.PHONY: dev
dev:
	poetry run ipython -i jordito.py


.PHONY: up
up:
	docker compose down
	docker compose up -d


.PHONY: down
down:
	docker compose down

.PHONY: logs
logs:
	docker compose logs --follow


.PHONY: git
git:
	git add -A
	git commit -m "${MSG}"
	git push -u origin main

.PHONY: chat_id
chat_id:
	poetry run python get_chats.py