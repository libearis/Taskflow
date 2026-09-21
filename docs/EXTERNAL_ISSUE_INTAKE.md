# TaskFlow Issue Intake — Integration Guide for External (.NET) Clients

This document is for teams integrating an external application (e.g. a .NET
service) with TaskFlow's `IssueIntake` gRPC service to report issues/bugs
that show up as Tasks on the TaskFlow board.

## 1. What this integration does

Your .NET app calls one unary gRPC method, `CreateIssue`. TaskFlow turns each
call into a Task inside a dedicated, auto-provisioned project called
**"External Reports"** (created automatically on first call — nothing to set
up on the TaskFlow side). The task then flows through TaskFlow's normal
CQRS/outbox pipeline and shows up on the board like any other task, tagged
with who reported it.

This is a **fire-and-forget report**, not a two-way sync: there is currently
no callback/webhook when the task's status changes (e.g. moves to "Done").
If you need that later, it has to be added as a separate feature — don't
assume it exists.

## 2. Connection details

| | |
|---|---|
| Protocol | Native gRPC (HTTP/2), **not** grpc-web |
| Host/port | `<taskflow-host>:50051` |
| TLS | None in this dev/demo setup — plaintext gRPC channel |
| Proxy | **None required.** Envoy is only used for the browser-facing `BoardStreamService` (grpc-web translation for JS, which can't read HTTP/2 trailers). A native .NET client connects straight to port `50051`. |

`.proto` file to copy into your project: [`backend/proto/issue_intake.proto`](../backend/proto/issue_intake.proto)

```protobuf
syntax = "proto3";
package taskflow.intake.v1;

service IssueIntake {
  rpc CreateIssue (CreateIssueRequest) returns (CreateIssueResponse);
}

message CreateIssueRequest {
  string title = 1;
  string description = 2;
  string severity = 3;       // "low" | "medium" | "high"
  string trigger_type = 4;   // "manual" | "automated" (automated not yet used)
  string reported_by = 5;    // free text, e.g. "admin@lab" — no TaskFlow user account backs this
}

message CreateIssueResponse {
  string issue_id = 1;
  string status = 2;         // "created" — real failures surface as a gRPC error status, not this field
}
```

## 3. Field rules

| Field | Required? | Rules |
|---|---|---|
| `title` | **Yes** | Non-empty after trim, or the call fails with `INVALID_ARGUMENT`. |
| `description` | No | Free text. Empty string is treated as "no description". |
| `severity` | No | Must be one of `"low"`, `"medium"`, `"high"` if set. Empty/unset defaults to `"low"`. Anything else fails with `INVALID_ARGUMENT`. |
| `trigger_type` | No | Free text; empty defaults to `"manual"`. `"automated"` is accepted but not yet wired to any special behavior on the TaskFlow side — treat it as a label for now. |
| `reported_by` | No | Free text identifier of who/what filed the report (e.g. an email or system name). Not validated against any user table — just stored and shown on the task card. |

## 4. What you get back

- On success: `CreateIssueResponse { issue_id, status: "created" }`. `issue_id` is the TaskFlow task's UUID as a string — store it on your side if you need to reference it later, since there's no query API for external callers yet.
- On failure: a gRPC error status, not a field in the response body.
  - `INVALID_ARGUMENT` — missing `title`, or an invalid `severity`.
  - `INTERNAL` — unexpected server-side error.

## 5. Minimal .NET client sketch

```csharp
using Grpc.Net.Client;
using Taskflow.Intake.V1; // namespace from the generated C# code

using var channel = GrpcChannel.ForAddress("http://taskflow-host:50051");
var client = new IssueIntake.IssueIntakeClient(channel);

var response = await client.CreateIssueAsync(new CreateIssueRequest
{
    Title = "Order sync failed for batch 4821",
    Description = "Timeout after 30s calling the pricing service.",
    Severity = "high",
    TriggerType = "automated",
    ReportedBy = "order-perf-lab",
});

// response.IssueId -> TaskFlow task UUID
// response.Status  -> "created"
```

Generate the C# stubs from `issue_intake.proto` using the standard
`Grpc.Tools` MSBuild integration (`<Protobuf Include="issue_intake.proto" GrpcServices="Client" />`) — no custom codegen steps are needed on the .NET side (unlike TaskFlow's own frontend, which needs grpc-web + extra JS post-processing).

## 6. Explicitly out of scope (for now)

- No callback/webhook to your app when a reported issue's status changes.
- No query/list RPC to read back issues you've reported — track `issue_id` on your side if needed.
- No auth/TLS on the gRPC channel in this dev setup — do not expose port `50051` outside a trusted network as-is.
