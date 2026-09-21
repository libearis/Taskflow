# TaskFlow

A small task/project management app (think a scaled-down Jira) built as a portfolio project to explore **CQRS**, the **Outbox Pattern**, and **gRPC used only where it actually fits** — packaged as a *modular monolith*, not a microservice split.

![status](https://img.shields.io/badge/status-portfolio--project-blue)

## Why this project exists

This project focuses on a pattern that's often misunderstood: **CQRS is about separating read and write responsibility, not a reason to split everything into separate services.** Here, CQRS is applied inside a single application (modular monolith), with two datastores each optimized for its own role.

## Features

- 📁 Create projects and tasks, change status (To Do → In Progress → Done) — via REST API
- 📊 Board view and per-user workload dashboard — data read from a view model already denormalized for display
- 🔄 Real-time board updates when a task's status changes, via gRPC server-streaming
- ⚙️ Automatic background sync of the read model, with no message broker

## Tech Stack

| | |
|---|---|
| **Backend** | Python, FastAPI |
| **API** | REST (command & query) + gRPC/grpc-web (live updates only) |
| **Write DB** | PostgreSQL |
| **Read DB** | MongoDB |
| **Frontend** | Vue 3 + Vite + Pinia |
| **Infra** | Docker Compose |

## Architecture Concepts

**CQRS** — commands (writes) are validated and persisted to PostgreSQL as the source of truth. Queries (reads) are served from MongoDB in a shape already denormalized for the view (board, dashboard), so no heavy joins are needed on every page load.

**Outbox Pattern** — rather than writing to two databases at once (which risks a partial failure), every command writes an "event" row to an outbox table in the same transaction as the data change. A background worker reads these events and updates MongoDB. The consequence: a short delay between a write landing and it showing up on the board (*eventual consistency*) — a documented trade-off, not something hidden.

**gRPC (used deliberately, not by default)** — gRPC isn't forced onto every endpoint. Ordinary commands and queries (create, update, get board) stay on REST, since that's the simplest and sufficient choice. gRPC is used intentionally for exactly one feature it's actually suited to: **live board updates** via server-streaming, consumed by the browser through grpc-web + an Envoy proxy. This separation avoids using gRPC "just because," and demonstrates an understanding of when gRPC genuinely outperforms REST.

Architectural decision details live in [`docs/ADR.md`](docs/ADR.md).

## Running the Project

```bash
git clone <repo-url>
cd taskflow
docker compose up
```

This project connects to a **native PostgreSQL install on the host**, not a containerized one — Postgres itself doesn't run in Docker here. Copy `.env.example` to `.env` at the repo root and set `DATABASE_URL` to point at your own local Postgres instance before running `docker compose up`. See [`docs/RUNNING_WITHOUT_DOCKER.md`](docs/RUNNING_WITHOUT_DOCKER.md) for the exact steps.

- Backend REST: `localhost:8000`
- Backend gRPC (streaming): `localhost:50051`
- Frontend: `localhost:5173`
- Envoy (grpc-web proxy, streaming route only): `localhost:8081`
- Mongo (for MongoDB Compass, etc.): `localhost:27017`

Docker here is just an orchestration convenience (Mongo + Envoy + the app together) — not a requirement of CQRS or gRPC themselves. Steps to run without Docker entirely are in [`docs/RUNNING_WITHOUT_DOCKER.md`](docs/RUNNING_WITHOUT_DOCKER.md).

## Project Structure

```
taskflow/
├── backend/     # FastAPI (REST) + gRPC server (streaming only), command/query handlers, outbox worker
├── frontend/    # Vue 3 app
├── envoy/       # grpc-web proxy config (StreamBoardUpdates route only)
└── docs/        # ADR & architecture notes
```
