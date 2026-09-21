# Architecture Decision Record — TaskFlow

## 1. CQRS within a single modular monolith, not microservices

**Decision:** Command (write) and query (read) are separated internally — different models,
repositories, and datastores — but remain a single deployable unit, one codebase, one
`docker-compose.yml`.

**Rationale:** CQRS is often misread as a reason to split an application into a separate
command-service and query-service. In fact, the core of CQRS is separating read/write
*responsibility* (data model, validation, response shape), not separating *deployment*. Splitting
this into microservices at this project's scale would only add operational overhead (extra network
calls, service discovery, separate deployments) with no concrete benefit, since read and write load
here don't need to scale independently.

**Trade-off:** If query load ever grows far beyond command load and needs to scale separately, this
modular monolith would need to be split first — but because command and query are already separated
internally (handlers, repositories, datastores), that separation gives a clear boundary to split
along, rather than requiring a rewrite from scratch.

## 2. PostgreSQL (write) + MongoDB (read) — polyglot persistence

**Decision:** Every command is validated and persisted to PostgreSQL as the source of truth. Every
query is served from MongoDB collections already denormalized for the view they back (per-project
board, per-user workload).

**Rationale:** Write data (tasks, projects) has clear relationships and constraints (a task must
belong to a valid project, status must be one of a fixed set of values) — a good fit for a
relational database with transactional guarantees. Read data for the board view needs a shape
already grouped by status column, ready to render without joins — a good fit for a document store
whose shape already resembles the API response.

**Trade-off:** Two datastores means two schemas whose consistency must be actively maintained, and
requires an explicit synchronization mechanism (see #3) — complexity that wouldn't exist with a
single database for everything. For a simple CRUD app without complex view requirements, a single
Postgres instance would be sufficient and cheaper to operate.

## 3. Outbox Pattern for synchronization, not dual-write or a message broker

**Decision:** The command handler writes the data change and an event row to the `outbox_events`
table in a single Postgres transaction. A projector worker (polling, `FOR UPDATE SKIP LOCKED`) reads
`PENDING` events, updates MongoDB, then marks the event `PROCESSED` (or `FAILED` once retries are
exhausted).

**Rationale:** Dual-write (writing to Postgres, then immediately writing to Mongo within the same
request) has a failure window: if the process dies after the Postgres commit but before the Mongo
update, the two datastores become permanently inconsistent, with no automatic way to recover. The
Outbox Pattern moves that failure window somewhere retryable: the event is stored permanently in
Postgres (atomically with its own data, in a single transaction), so the projector can die and come
back at any time without losing an event.

Polling was chosen (rather than `LISTEN/NOTIFY` or a message broker like Kafka/RabbitMQ) because
this project's scope doesn't need sub-second latency, and adding a broker means adding another
moving part to operate — not worth it for a mini task board like this.

**Trade-offs (documented, not hidden):**
- **Eventual consistency** — there is a delay between a task's status changing in Postgres and that
  change appearing on the board (Mongo). This delay is made visible in the UI (a "syncing"
  indicator), rather than hidden behind a pretense of instant real-time updates.
- **Added complexity** compared to plain CRUD: an outbox table, a separate worker, retry/dead-letter
  logic (`retry_count`, `FAILED` status).
- **Idempotency is required** on the projector side: since an event can be reprocessed (for example,
  if the projector crashes after updating Mongo but before marking the event `PROCESSED`), rebuilding
  the board/workload document is done via a *full recompute* from Postgres per project/user, rather
  than an increment — so reprocessing the same event never duplicates data.

## 4. gRPC only for `StreamBoardUpdates`, REST for everything else

**Decision:** Every command and query (create project, create task, change status, assign, get
board, get workload) goes through plain REST/JSON. The only gRPC RPC is
`BoardStreamService.StreamBoardUpdates` — server-streaming for live board updates, exposed to the
browser via grpc-web + an Envoy proxy (no other REST endpoint goes through Envoy at all).

**Rationale:** gRPC outperforms REST specifically for cases that need multiplexed streaming over a
single HTTP/2 connection — live board updates are exactly that case. For plain CRUD, REST/JSON is
simpler, easier to debug (a direct `curl` works), and needs no code generation on the frontend.
Forcing gRPC onto every endpoint purely for protocol consistency would provide no real benefit here,
and would add development friction (regenerating stubs for every small schema change).

**Trade-off:** The frontend needs two distinct client paths (axios for REST, a generated grpc-web
client for the stream) and one extra proxy (Envoy) dedicated to this single RPC. This is extra
complexity accepted deliberately, because its benefit (efficient server push, outside a microservice
context) is genuinely used here, not merely included for show.

## 5. No `users` table

**Decision:** `owner_id` and `assignee_id` are stored as raw UUIDs with no separate `users` table;
the read model displays these IDs as a stand-in for a name.

**Rationale:** User management (auth, profiles) is outside the scope of the CQRS/Outbox/gRPC patterns
this project sets out to demonstrate. Adding it would only add surface area without demonstrating any
pattern relevant to this project's purpose.

**Trade-off:** The board and dashboard display raw UUIDs rather than human-readable names — sufficient
for demonstrating the pattern, not sufficient for real production use.
