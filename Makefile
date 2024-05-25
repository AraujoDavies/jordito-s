.PHONY: dev
dev:
	poetry run ipython -i jordito.py


.PHONY: up
up:
	docker compose -f my_compose.yml down
	docker compose -f my_compose.yml up -d


.PHONY: down
down:
	docker compose -f my_compose.yml down

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