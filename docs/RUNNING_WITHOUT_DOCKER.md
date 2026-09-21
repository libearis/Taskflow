# Menjalankan TaskFlow tanpa Docker

Docker di project ini cuma kemudahan orkestrasi (Postgres + Mongo + Envoy + app
sekaligus). Tidak ada bagian dari CQRS atau gRPC yang mengharuskan Docker — di
bawah ini cara menjalankan backend & frontend langsung di mesin lokal (native),
tanpa Docker buat proses backend/frontend-nya sendiri.

**Catatan soal Mongo:** panduan ini tidak mengasumsikan Mongo terinstall
native di komputer kamu — kalau kamu tidak menginstallnya sendiri, cara
termudah (dan yang dipakai di bawah) adalah tetap menyalakan **container
Mongo saja** lewat Docker Compose, bukan seluruh stack. Ini bukan "curang" —
Mongo memang tidak sedang didemonstrasikan apa-apa soal cara jalaninnya, jadi
gak masalah numpang container buat itu satu saja, sementara backend & frontend
tetap kamu jalankan sendiri langsung di mesin buat development/debugging.

## 1. Prasyarat

- Python 3.12+
- Node.js 20+
- PostgreSQL 16+ berjalan lokal (atau host lain yang bisa diakses) — bisa
  instalasi native, tidak harus di Docker
- MongoDB — via container Docker (lihat catatan di atas), atau install native
  kalau mau benar-benar lepas dari Docker
- `protoc` + `protoc-gen-grpc-web` (hanya kalau mau regenerate stub frontend —
  lihat bagian 5)
- Envoy binary (opsional — hanya kalau mau coba live-stream dari browser;
  lihat bagian 4 untuk alternatif tanpa Envoy)

## 2. Setup database

```bash
createdb taskflow   # atau lewat psql/pgAdmin

# Mongo: nyalain container-nya saja (butuh Docker jalan, tapi cuma buat Mongo,
# bukan seluruh stack) — dan biarkan tetap jalan selama kamu develop:
docker compose up -d mongo
# Koleksinya sendiri tidak perlu setup awal — dibuat otomatis oleh projector.
```

## 3. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

cp .env.example .env
# edit .env kalau host/port Postgres atau Mongo kamu beda dari default

./scripts/generate_proto.sh   # generate stub gRPC Python (butuh grpcio-tools, sudah ke-install di atas)

alembic upgrade head
python -m app.main
```

Ini menjalankan FastAPI (`:8000`) dan gRPC server (`:50051`) di proses yang
sama, plus outbox projector sebagai background task — persis seperti di
Docker, cuma tanpa container.

## 4. Envoy (grpc-web proxy) — opsional

Browser tidak bisa bicara gRPC native, jadi `StreamBoardUpdates` butuh proxy
translasi. Dua opsi:

**Opsi A — jalankan Envoy langsung** (kalau sudah ada binary-nya):

```bash
envoy -c envoy/envoy.yaml
```

**Opsi B — pakai `grpcwebproxy`** (single binary, lebih ringan daripada
Envoy untuk dev lokal):

```bash
grpcwebproxy \
  --backend_addr=localhost:50051 \
  --run_tls_server=false \
  --allow_all_origins \
  --server_http_debug_port=8081
```

Frontend tetap mengarah ke `http://localhost:8081` (lihat `VITE_GRPC_WEB_URL`
di `.env`) di kedua opsi. Port `8081` dipilih (bukan `8080`) karena `8080`
gampang bentrok dengan proses lain yang sudah jalan di banyak mesin dev — kalau
kamu juga bentrok, ganti saja ke port bebas mana pun asalkan `VITE_GRPC_WEB_URL`
ikut disesuaikan.

Kalau kamu tidak butuh live-update untuk development (misalnya cuma mau test
REST API), langkah ini bisa dilewati — board tetap bisa di-load lewat REST,
cuma tidak akan update otomatis saat status berubah.

## 5. Frontend

```bash
cd frontend
npm install

# generate client grpc-web (butuh protoc + protoc-gen-grpc-web di PATH)
./scripts/generate_proto_web.sh

cp .env.example .env   # lalu sesuaikan VITE_API_BASE_URL / VITE_GRPC_WEB_URL kalau perlu
npm run dev
```

Buka `http://localhost:5173`.

## 6. Menjalankan test

```bash
cd backend
pytest tests/unit                # tidak butuh Postgres/Mongo — pakai SQLite in-memory
pytest tests/integration         # butuh Docker (testcontainers) ATAU set env var
                                  # TESTCONTAINERS_* untuk pakai Postgres/Mongo yang sudah jalan
```

Catatan: test integrasi tetap memakai `testcontainers`, yang secara default
butuh Docker untuk spin up Postgres/Mongo sekali pakai — ini independen dari
cara kamu menjalankan aplikasinya sendiri.
