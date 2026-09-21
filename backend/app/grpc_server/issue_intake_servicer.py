import logging

import grpc

from app.command.handlers import (
    CreateExternalIssueCommand,
    InvalidSeverityError,
    create_external_issue,
)
from app.db import async_session_factory
from app.grpc_server.generated import issue_intake_pb2, issue_intake_pb2_grpc

logger = logging.getLogger(__name__)


class IssueIntakeServicer(issue_intake_pb2_grpc.IssueIntakeServicer):
    """Lets external systems (e.g. the .NET Catalog & Order Performance Lab)
    report issues into TaskFlow. Each report becomes a Task under a
    dedicated, auto-provisioned "External Reports" project, going through
    the same outbox path as a UI-created task — see command/handlers.py."""

    async def CreateIssue(
        self,
        request: issue_intake_pb2.CreateIssueRequest,
        context: grpc.aio.ServicerContext,
    ) -> issue_intake_pb2.CreateIssueResponse:
        if not request.title.strip():
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "title is required")

        async with async_session_factory() as session:
            try:
                task = await create_external_issue(
                    session,
                    CreateExternalIssueCommand(
                        title=request.title,
                        description=request.description or None,
                        severity=request.severity,
                        trigger_type=request.trigger_type or "manual",
                        external_reporter=request.reported_by,
                    ),
                )
            except InvalidSeverityError as exc:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
            except Exception:
                logger.exception("CreateIssue failed")
                await context.abort(grpc.StatusCode.INTERNAL, "Failed to create issue")

        return issue_intake_pb2.CreateIssueResponse(issue_id=str(task.id), status="created")
