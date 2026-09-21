# Running TaskFlow without Docker

Docker in this project is purely an orchestration convenience (Postgres + Mongo + Envoy + the app
all at once). No part of CQRS or gRPC requires Docker — below is how to run the backend & frontend
directly on your local machine (native), without Docker for the backend/frontend processes
themselves.

**Note on Mongo:** this guide does not assume Mongo is installed natively on your machine — if you
haven't installed it yourself, the easiest approach (and the one used below) is to still run just
the **Mongo container** via Docker Compose, not the whole stack. This isn't "cheating" — Mongo isn't
what's being demonstrated in terms of how it's run, so there's no issue borrowing a container for
that one piece alone, while you still run the backend & frontend directly on your machine for
development/debugging.

## 1. Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 16+ running locally (or another reachable host) — a native install works fine, it
  doesn't have to be in Docker
- MongoDB — via a Docker container (see the note above), or a native install if you want to be
  fully Docker-free
- `protoc` + `protoc-gen-grpc-web` (only if you want to regenerate the frontend stubs — see section
  5). Install:

  ```bash
  # macOS
  brew install protobuf              # protoc
  brew install protoc-gen-grpc-web   # protoc-gen-grpc-web

  # Ubuntu/Debian
  apt install -y protobuf-compiler   # protoc
  # protoc-gen-grpc-web isn't in apt — download the binary matching your OS/arch
  # from the official release page: https://github.com/grpc/grpc-web/releases
  # (look for the "protoc-gen-grpc-web-<version>-linux-x86_64" asset), then:
  #   chmod +x protoc-gen-grpc-web-<version>-linux-x86_64
  #   mv protoc-gen-grpc-web-<version>-linux-x86_64 /usr/local/bin/protoc-gen-grpc-web

  # Windows (via winget/choco, or manually)
  choco install protoc
  # protoc-gen-grpc-web: download the .exe from the release page and place it
  # somewhere on your PATH — https://github.com/grpc/grpc-web/releases
  ```

  The backend's Python tooling (`grpcio-tools`, already included via
  `pip install -e ".[dev]"` in section 3) is enough to generate the Python stubs — the `protoc`
  above is only needed to generate the **frontend** stubs (section 5).
- Envoy binary (optional — only if you want to try the live browser stream; see section 4 for an
  alternative to Envoy)

## 2. Database setup

```bash
createdb taskflow   # or via psql/pgAdmin

# Mongo: start just its container (needs Docker running, but only for Mongo,
# not the whole stack) — and leave it running for the rest of your dev session:
docker compose up -d mongo
# The collections themselves need no upfront setup — they're created
# automatically by the projector.
```

## 3. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

cp .env.example .env
# edit .env if your Postgres/Mongo host or port differ from the defaults

./scripts/generate_proto.sh   # generate the Python gRPC stubs (needs grpcio-tools, already installed above)

alembic upgrade head
python -m app.main
```

This runs FastAPI (`:8000`) and the gRPC server (`:50051`) in the same process, plus the outbox
projector as a background task — exactly as in Docker, just without a container.

## 4. Envoy (grpc-web proxy) — optional

The browser can't speak gRPC natively, so `StreamBoardUpdates` needs a translating proxy. Two
options:

**Option A — run Envoy directly** (if you already have the binary):

```bash
envoy -c envoy/envoy.yaml
```

**Option B — use `grpcwebproxy`** (a single binary, lighter than Envoy for local dev):

```bash
grpcwebproxy \
  --backend_addr=localhost:50051 \
  --run_tls_server=false \
  --allow_all_origins \
  --server_http_debug_port=8081
```

The frontend still points to `http://localhost:8081` (see `VITE_GRPC_WEB_URL` in `.env`) with either
option. Port `8081` was chosen instead of `8080` because `8080` tends to collide with other
processes already running on many dev machines — if you also hit a conflict, feel free to switch to
any free port as long as `VITE_GRPC_WEB_URL` is updated to match.

If you don't need live updates for development (e.g. you're only testing the REST API), this step
can be skipped entirely — the board can still be loaded via REST, it just won't auto-update when a
status changes.

> **Why isn't Envoy simply run via `docker compose up -d envoy`** (when Mongo is allowed to be)?
> Two concrete reasons:
> 1. `envoy.yaml` points its upstream at the host `backend` (`envoy/envoy.yaml`, cluster
>    `grpc_backend`) — that's a Docker Compose–internal DNS name, only resolvable to another
>    container on the same compose network. The backend you run natively (section 3) isn't on that
>    network, so the Envoy container has no way to reach it.
> 2. The `envoy` service in `docker-compose.yml` has `depends_on: backend` — starting it via compose
>    automatically starts the backend **container** too, which will then fight over ports
>    `8000`/`50051` with your native process. Mongo doesn't have this problem because no other
>    service `depends_on` it.
>
> That's why Envoy in this guide always runs natively (the Envoy binary or `grpcwebproxy`), while
> Mongo is allowed to stay containerized — not an inconsistency, but a direct consequence of what's
> actually in the config.

## 5. Frontend

```bash
cd frontend
npm install

# generate the grpc-web client (needs protoc + protoc-gen-grpc-web on PATH)
./scripts/generate_proto_web.sh

cp .env.example .env   # then adjust VITE_API_BASE_URL / VITE_GRPC_WEB_URL if needed
npm run dev
```

Open `http://localhost:5173`.

## 6. One-shot run (optional)

Sections 2-5 above are manual, one component at a time — good for understanding the sequence, but
if you just want everything (Mongo + backend + frontend) up at once without juggling several
terminals, there's a script at the repo root:

```powershell
./scripts/run-without-docker.ps1
```

(Windows/PowerShell only — see the note below if you're on macOS/Linux.)

This script automatically: starts the Mongo container, creates `.venv`/`node_modules` if missing,
generates the proto stubs, runs `alembic upgrade head`, then starts the backend & frontend together
in the background. Press `Ctrl+C` to stop the backend and frontend (the Mongo container keeps
running — stop it manually if needed with `docker compose stop mongo`).

**Prerequisite before the first run:** native Postgres is already running and `createdb taskflow`
has been done (section 2), and `backend/.env` / `frontend/.env` have already been filled in for your
own environment (the script only copies from `.env.example` when the file doesn't exist yet — it has
no way to know your Postgres password).

This script does **not** start Envoy/the grpc-web proxy (see the note in section 4 for why that has
to run natively and separately) — live board updates won't work without it, but the REST API and
loading the board manually still work.

> On macOS/Linux there is currently no equivalent one-shot script — follow sections 2-5 manually
> (they're plain shell commands either way).

## 7. Running tests

```bash
cd backend
pytest tests/unit                # doesn't need Postgres/Mongo — uses an in-memory SQLite
pytest tests/integration         # needs Docker (testcontainers) OR set the TESTCONTAINERS_*
                                  # env vars to use an already-running Postgres/Mongo
```

Note: the integration tests still use `testcontainers`, which by default needs Docker to spin up a
disposable Postgres/Mongo — this is independent of how you run the application itself.
