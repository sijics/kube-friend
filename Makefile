# Makefile — shortcuts for kubefriend development and usage
#
# Usage:
#   make install    One-time setup
#   make run        Start natively (no Docker)
#   make stop       Stop everything
#   make status     Show running status
#   make logs       Tail live logs
#   make dev        Start with hot-reload (same as run)
#   make docker     Start with Docker Compose instead
#   make switch c=<context>   Switch kubectl context

.PHONY: install run stop restart status logs dev docker switch contexts llm help

# Default target
help:
	@./kubefriend help

install:
	@chmod +x install.sh run.sh stop.sh kubefriend
	@./install.sh

run: dev

dev:
	@chmod +x run.sh
	@./run.sh

stop:
	@chmod +x stop.sh
	@./stop.sh

restart:
	@chmod +x stop.sh run.sh
	@./stop.sh && sleep 1 && ./run.sh

status:
	@./kubefriend status

logs:
	@./kubefriend logs

# Switch cluster context: make switch c=rancher-desktop
switch:
	@./kubefriend switch $(c)

contexts:
	@./kubefriend contexts

# Switch LLM: make llm p=watsonx  or  make llm p=openai
llm:
	@./kubefriend llm $(p)

# Start with Docker Compose (original method)
docker:
	@docker compose up --build

docker-stop:
	@docker compose down

# Clean up PID files and logs
clean:
	@rm -rf .kubefriend/
	@echo "✓ Cleaned up PID files and logs"
