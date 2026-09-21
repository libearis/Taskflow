# Architecture Decision Record — TaskFlow

## 1. CQRS di dalam satu modular monolith, bukan microservices

**Keputusan:** Command (write) dan query (read) dipisah secara internal — model, repository,
dan datastore berbeda — tapi tetap satu deployable unit, satu codebase, satu `docker-compose.yml`.

**Kenapa:** CQRS sering disalahartikan sebagai alasan untuk memecah aplikasi jadi command-service
dan query-service yang terpisah. Padahal inti CQRS adalah pemisahan *tanggung jawab* baca/tulis
(model data, validasi, bentuk response), bukan pemisahan *deployment*. Memecah jadi microservice di
project sekecil ini hanya menambah operational overhead (network call tambahan, service discovery,
deployment terpisah) tanpa manfaat konkret, karena beban baca dan tulis di sini tidak butuh scaling
independen.

**Trade-off:** Kalau suatu saat query load jauh lebih besar dari command load dan perlu di-scale
terpisah, modular monolith ini harus dipecah dulu — tapi karena command/query sudah terpisah secara
internal (handler, repository, datastore), pemisahan itu jadi boundary yang jelas untuk dipecah,
bukan refactor besar dari nol.

## 2. PostgreSQL (write) + MongoDB (read) — polyglot persistence

**Keputusan:** Semua command tervalidasi dan disimpan ke PostgreSQL sebagai source of truth. Semua
query dilayani dari koleksi MongoDB yang sudah didenormalisasi sesuai kebutuhan tampilan (board per
project, workload per user).

**Kenapa:** Data write (task, project) punya relasi dan constraint yang jelas (task harus punya
project yang valid, status harus salah satu dari beberapa nilai) — cocok untuk relational DB dengan
transaction guarantee. Data read untuk board view butuh bentuk yang sudah dikelompokkan per status
kolom, siap tampil tanpa join — cocok untuk document store yang bentuknya sudah menyerupai response
API.

**Trade-off:** Dua datastore berarti dua skema untuk dijaga konsistenlogi-nya, dan butuh mekanisme
sinkronisasi eksplisit (lihat #3) — kompleksitas ini tidak ada kalau pakai satu database untuk
semuanya. Untuk aplikasi CRUD sederhana tanpa kebutuhan tampilan yang kompleks, satu Postgres saja
sudah cukup dan lebih murah untuk dioperasikan.

## 3. Outbox Pattern untuk sinkronisasi, bukan dual-write atau message broker

**Keputusan:** Command handler menulis perubahan data + row event ke tabel `outbox_events` dalam
satu transaksi Postgres. Sebuah projector worker (polling, `FOR UPDATE SKIP LOCKED`) membaca event
`PENDING`, memperbarui MongoDB, lalu menandai event `PROCESSED` (atau `FAILED` setelah retry
habis).

**Kenapa:** Dual-write (tulis Postgres lalu langsung tulis Mongo di request yang sama) punya window
kegagalan: kalau proses mati setelah Postgres commit tapi sebelum Mongo update, kedua datastore jadi
tidak konsisten selamanya, tanpa cara otomatis untuk pulih. Outbox pattern memindahkan window
kegagalan itu ke tempat yang bisa di-retry: event tersimpan permanen di Postgres (atomic dengan
data-nya sendiri, dalam satu transaksi), jadi projector bisa mati dan hidup lagi kapan saja tanpa
kehilangan event.

Dipilih *polling* (bukan `LISTEN/NOTIFY` atau message broker seperti Kafka/RabbitMQ) karena scope
project ini tidak butuh latency sub-detik, dan menambah broker berarti menambah satu lagi moving
part untuk di-operate — tidak sepadan untuk mini task board ini.

**Trade-off (didokumentasikan, bukan disembunyikan):**
- **Eventual consistency** — ada jeda antara task berubah status di Postgres dan tampil berubah di
  board (Mongo). Jeda ini terlihat di UI (indikator "syncing"), bukan disembunyikan seolah update
  real-time instan.
- **Kompleksitas tambahan** dibanding CRUD biasa: tabel outbox, worker terpisah, logic retry/dead
  letter (`retry_count`, status `FAILED`).
- **Idempotency wajib** di sisi projector: karena event bisa diproses ulang (misal kalau projector
  crash setelah update Mongo tapi sebelum menandai `PROCESSED`), rebuild board/workload document
  dilakukan dengan *full recompute* dari Postgres per project/user, bukan increment — supaya
  pemrosesan ulang event yang sama tidak menduplikasi data.

## 4. gRPC hanya untuk `StreamBoardUpdates`, REST untuk semuanya

**Keputusan:** Semua command dan query (create project, create task, ubah status, assign, get
board, get workload) lewat REST/JSON biasa. Satu-satunya RPC gRPC adalah
`BoardStreamService.StreamBoardUpdates` — server-streaming untuk live update board, diekspos ke
browser lewat grpc-web + Envoy proxy (endpoint REST lain tidak lewat Envoy sama sekali).

**Kenapa:** gRPC unggul dibanding REST untuk kasus yang memang butuh streaming multipleks di satu
koneksi HTTP/2 — live update board persis kasus itu. Untuk CRUD biasa, REST/JSON lebih sederhana,
lebih mudah di-debug (bisa `curl` langsung), dan tidak butuh code generation di frontend. Memaksakan
gRPC untuk semua endpoint hanya untuk konsistensi protokol tidak memberi manfaat nyata di sini, dan
menambah friksi development (perlu regenerate stub untuk setiap perubahan schema kecil).

**Trade-off:** Frontend perlu dua jalur klien berbeda (axios untuk REST, grpc-web client generated
untuk stream) dan satu proxy tambahan (Envoy) khusus untuk RPC ini. Ini kompleksitas ekstra yang
sengaja diterima karena manfaatnya (server push yang efisien, di luar konteks microservice) memang
dipakai secara nyata, bukan sekadar dipasang.

## 5. Tidak ada tabel `users`

**Keputusan:** `owner_id` dan `assignee_id` disimpan sebagai UUID mentah tanpa tabel `users`
terpisah; read model menampilkan ID tersebut sebagai representasi nama.

**Kenapa:** Manajemen user (auth, profile) di luar scope demonstrasi CQRS/Outbox/gRPC yang menjadi
fokus project ini. Menambahkannya hanya menambah permukaan kode tanpa menunjukkan pattern baru yang
relevan dengan tujuan portfolio ini.

**Trade-off:** Board dan dashboard menampilkan UUID, bukan nama manusia yang enak dibaca — cukup
untuk demo pattern, tidak cukup untuk produksi nyata.
