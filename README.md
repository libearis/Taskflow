# TaskFlow

Mini task/project management app (mirip Jira versi kecil) — dibuat sebagai portfolio project untuk mendalami **CQRS**, **Outbox Pattern**, dan penggunaan **gRPC yang tepat sasaran**, dikemas sebagai *modular monolith* (bukan microservice).

![status](https://img.shields.io/badge/status-portfolio--project-blue)

## Kenapa project ini dibuat

Project ini fokus ke pattern yang sering disalahpahami: **CQRS itu soal pemisahan tanggung jawab baca/tulis, bukan alasan untuk memecah service jadi banyak**. Di sini, CQRS diterapkan di dalam satu aplikasi (modular monolith), dengan dua datastore yang masing-masing dioptimasi untuk perannya masing-masing.

## Fitur

- 📁 Buat project & task, assign ke user, ubah status (To Do → In Progress → Done) — via REST API
- 📊 Board view & dashboard workload per user — data dibaca dari read model yang sudah dioptimasi untuk tampilan
- 🔄 Live update board secara real-time saat task berubah status, lewat gRPC server-streaming
- ⚙️ Sinkronisasi read model otomatis di background, tanpa message broker

## Tech Stack

| | |
|---|---|
| **Backend** | Python, FastAPI |
| **API** | REST (command & query) + gRPC/grpc-web (live update saja) |
| **Write DB** | PostgreSQL |
| **Read DB** | MongoDB |
| **Frontend** | Vue 3 + Vite + Pinia |
| **Infra** | Docker Compose |

## Konsep Arsitektur

**CQRS** — command (tulis) divalidasi dan disimpan ke PostgreSQL sebagai source of truth. Query (baca) dilayani dari MongoDB dengan bentuk data yang sudah denormalized sesuai kebutuhan tampilan (board, dashboard), jadi tidak perlu join berat tiap kali user buka halaman.

**Outbox Pattern** — daripada menulis ke dua database sekaligus (rawan gagal setengah jalan), setiap command menyimpan sebuah "event" ke tabel outbox dalam transaksi yang sama dengan perubahan data. Sebuah background worker membaca event tersebut lalu memperbarui MongoDB. Konsekuensinya: ada jeda singkat antara data ditulis dan tampil di board (*eventual consistency*) — trade-off yang didokumentasikan, bukan disembunyikan.

**gRPC (tepat sasaran, bukan default)** — gRPC tidak dipaksakan jadi protokol untuk semua endpoint. Command dan query biasa (create, update, get board) tetap pakai REST karena itu paling sederhana dan cukup. gRPC dipakai secara sengaja hanya untuk satu fitur yang memang cocok dengannya: **live update board** via server-streaming, dikonsumsi browser lewat grpc-web + Envoy proxy. Pemisahan ini menghindari pemakaian gRPC "asal ada", dan menunjukkan pemahaman kapan gRPC benar-benar unggul dibanding REST.

Detail keputusan arsitektur ada di [`docs/ADR.md`](docs/ADR.md).

## Menjalankan Project

```bash
git clone <repo-url>
cd taskflow
docker compose up
```

- Backend REST: `localhost:8000`
- Backend gRPC (streaming): `localhost:50051`
- Frontend: `localhost:5173`
- Envoy (grpc-web proxy, khusus stream): `localhost:8081`
- Postgres (buat diakses dari DBeaver/psql dsb): `localhost:5433`, user/password/db `taskflow`/`taskflow`/`taskflow`
- Mongo (buat diakses dari MongoDB Compass dsb): `localhost:27017`

> Port Postgres di-host sebagai `5433` (bukan default `5432`) supaya tidak\
> bentrok kalau kamu sudah punya instalasi Postgres native di komputer sendiri\
> yang juga listen di `5432` — keduanya server yang sama sekali terpisah\
> (beda data, beda kredensial), cuma kebetulan mau pakai port default yang sama.

Docker di sini cuma kemudahan orkestrasi (Postgres + Mongo + Envoy + app sekaligus) — bukan requirement dari CQRS atau gRPC itu sendiri. Cara menjalankan tanpa Docker ada di [`docs/RUNNING_WITHOUT_DOCKER.md`](docs/RUNNING_WITHOUT_DOCKER.md).

## Struktur Project

```
taskflow/
├── backend/     # FastAPI (REST) + gRPC server (streaming saja), command/query handlers, outbox worker
├── frontend/    # Vue 3 app
├── envoy/       # grpc-web proxy config (route khusus StreamBoardUpdates)
└── docs/        # ADR & diagram arsitektur
```

## Demo

*(tambahkan screenshot / GIF board view & live update di sini)*

## Lisensi

MIT
