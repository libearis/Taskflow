/**
 * Thin wrapper around the generated grpc-web client for the ONE streaming RPC
 * this project uses gRPC for: StreamBoardUpdates. Everything else is REST
 * (see api/rest.ts) — this file must stay the only gRPC touchpoint in the FE.
 *
 * `src/generated/` is produced by `scripts/generate_proto_web.sh` — do not
 * import protoc output here until that script has been run.
 */
import { BoardStreamServiceClient } from "@/generated/Board_streamServiceClientPb";
// Namespace import, not named: the generated CommonJS module attaches its
// exports dynamically (`goog.object.extend(exports, proto.taskflow)`), which
// static ESM named-import analysis can't see. The generated client itself
// uses the same namespace-import style for this reason.
import * as board_stream_pb from "@/generated/board_stream_pb";

type BoardUpdateEvent = board_stream_pb.BoardUpdateEvent;

export interface BoardUpdate {
  taskId: string;
  title: string;
  oldStatus: string;
  newStatus: string;
  assigneeId: string;
  changedAt: string;
}

function toBoardUpdate(event: BoardUpdateEvent): BoardUpdate {
  return {
    taskId: event.getTaskId(),
    title: event.getTitle(),
    oldStatus: event.getOldStatus(),
    newStatus: event.getNewStatus(),
    assigneeId: event.getAssigneeId(),
    changedAt: event.getChangedAt(),
  };
}

export function subscribeToBoardUpdates(
  projectId: string,
  onUpdate: (update: BoardUpdate) => void,
  onError?: (err: unknown) => void
): () => void {
  const client = new BoardStreamServiceClient(import.meta.env.VITE_GRPC_WEB_URL);
  const request = new board_stream_pb.StreamBoardRequest();
  request.setProjectId(projectId);

  const stream = client.streamBoardUpdates(request, {});
  stream.on("data", (event: BoardUpdateEvent) => onUpdate(toBoardUpdate(event)));
  stream.on("error", (err: unknown) => onError?.(err));

  return () => stream.cancel();
}
