NAME = EigenField
COMPOSE = docker compose

all: build up

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f $(SERVICE)

clean:
	$(COMPOSE) down --remove-orphans

fclean:
	$(COMPOSE) down -v --rmi local

re: fclean all

.PHONY: all build up down logs clean fclean re
