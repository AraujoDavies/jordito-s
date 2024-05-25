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