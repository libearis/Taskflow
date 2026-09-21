.PHONY: up down proto proto-web test

up:
	docker compose up --build

down:
	docker compose down -v

proto:
	cd backend && ./scripts/generate_proto.sh

proto-web:
	cd frontend && ./scripts/generate_proto_web.sh

test:
	cd backend && pytest
