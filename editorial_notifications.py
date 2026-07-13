from __future__ import annotations

from datetime import datetime, timezone


class EditorialStatusNotifier:
    def __init__(self, *, edit_id: str, execution_log: list[dict[str, object]]) -> None:
        self._edit_id = edit_id
        self._execution_log = execution_log

    def notify(
        self,
        *,
        role: str,
        phase: str,
        status: str,
        message: str,
        line_start: int | None = None,
        line_end: int | None = None,
        purpose: str | None = None,
    ) -> dict[str, object]:
        timestamp = datetime.now(timezone.utc).isoformat()
        event: dict[str, object] = {
            "type": "editorial_status",
            "id": self._edit_id,
            "timestamp": timestamp,
            "role": role,
            "phase": phase,
            "status": status,
            "message": message,
        }
        if line_start is not None:
            event["line_start"] = line_start
        if line_end is not None:
            event["line_end"] = line_end
        if purpose:
            event["purpose"] = purpose
        self._execution_log.append({"event": "status", **event})
        return event
