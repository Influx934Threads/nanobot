"""Heartbeat service - periodic agent wake-up to check for tasks."""

from __future__ import annotations

import asyncio
import re
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from loguru import logger

if TYPE_CHECKING:
    from nanobot.providers.base import LLMProvider

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_TEMPLATE_FILES = frozenset({
    "HEARTBEAT.md", "HEARTBEAT-old.md", "AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md",
})
_MAX_STATE_FILE_BYTES = 256

_HEARTBEAT_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "heartbeat",
            "description": "Report heartbeat decision after reviewing tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["skip", "run"],
                        "description": "skip = nothing to do, run = has active tasks",
                    },
                    "tasks": {
                        "type": "string",
                        "description": "Natural-language summary of active tasks (required for run)",
                    },
                },
                "required": ["action"],
            },
        },
    }
]


class HeartbeatService:
    """
    Periodic heartbeat service that wakes the agent to check for tasks.

    Phase 1 (decision): reads HEARTBEAT.md and asks the LLM — via a virtual
    tool call — whether there are active tasks.  This avoids free-text parsing
    and the unreliable HEARTBEAT_OK token.

    Phase 2 (execution): only triggered when Phase 1 returns ``run``.  The
    ``on_execute`` callback runs the task through the full agent loop and
    returns the result to deliver.
    """

    def __init__(
        self,
        workspace: Path,
        provider: LLMProvider,
        model: str,
        on_execute: Callable[[str], Coroutine[Any, Any, str]] | None = None,
        on_notify: Callable[[str], Coroutine[Any, Any, None]] | None = None,
        interval_s: int = 30 * 60,
        enabled: bool = True,
        fast_provider: LLMProvider | None = None,
        fast_model: str | None = None,
    ):
        self.workspace = workspace
        self.provider = provider
        self.model = model
        self.fast_provider = fast_provider
        self.fast_model = fast_model or (fast_provider.get_default_model() if fast_provider else None)
        self.on_execute = on_execute
        self.on_notify = on_notify
        self.interval_s = interval_s
        self.enabled = enabled
        self._running = False
        self._task: asyncio.Task | None = None

    @property
    def heartbeat_file(self) -> Path:
        return self.workspace / "HEARTBEAT.md"

    def _collect_workspace_state(self) -> dict[str, str]:
        """Read small .txt state files from workspace root to inject into decide prompt."""
        state: dict[str, str] = {}
        try:
            for path in self.workspace.iterdir():
                if (
                    path.is_file()
                    and path.suffix == ".txt"
                    and not path.name.startswith(".")
                    and path.name not in _TEMPLATE_FILES
                    and path.stat().st_size <= _MAX_STATE_FILE_BYTES
                ):
                    try:
                        state[path.name] = path.read_text(encoding="utf-8").strip()
                    except Exception:
                        pass
        except Exception:
            pass
        return state

    def _read_heartbeat_file(self) -> str | None:
        if self.heartbeat_file.exists():
            try:
                return self.heartbeat_file.read_text(encoding="utf-8")
            except Exception:
                return None
        return None

    async def _decide(self, content: str) -> tuple[str, str]:
        """Phase 1: ask LLM to decide skip/run via virtual tool call.

        Returns (action, tasks) where action is 'skip' or 'run'.
        """
        from nanobot.utils.helpers import current_time_str

        decide_provider = self.fast_provider or self.provider
        decide_model = self.fast_model or self.model
        response = await decide_provider.chat_with_retry(
            messages=[
                {"role": "system", "content": (
                    "You are a heartbeat agent. Review the workspace state and HEARTBEAT.md, "
                    "then call the heartbeat tool. Use 'skip' if all tasks are already completed "
                    "for today based on their last-run dates in the workspace state. Use 'run' only "
                    "if a task genuinely needs to execute right now."
                )},
                {"role": "user", "content": (
                    f"Current Time: {current_time_str()}\n\n"
                    "Check the workspace state dates against the current time. "
                    "If a task's last-run date matches today, it is already done — use skip. "
                    "Otherwise use run.\n\n"
                    f"{content}"
                )},
            ],
            tools=_HEARTBEAT_TOOL,
            model=decide_model,
        )

        if not response.has_tool_calls:
            return "skip", ""

        args = response.tool_calls[0].arguments
        return args.get("action", "skip"), args.get("tasks", "")

    async def start(self) -> None:
        """Start the heartbeat service."""
        if not self.enabled:
            logger.info("Heartbeat disabled")
            return
        if self._running:
            logger.warning("Heartbeat already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Heartbeat started (every {}s)", self.interval_s)

    def stop(self) -> None:
        """Stop the heartbeat service."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    async def _run_loop(self) -> None:
        """Main heartbeat loop."""
        while self._running:
            try:
                await asyncio.sleep(self.interval_s)
                if self._running:
                    await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Heartbeat error: {}", e)

    async def _tick(self) -> None:
        """Execute a single heartbeat tick."""
        from nanobot.utils.evaluator import evaluate_response

        content = self._read_heartbeat_file()
        if not content:
            logger.debug("Heartbeat: HEARTBEAT.md missing or empty")
            return

        state = self._collect_workspace_state()
        today = date.today().isoformat()
        if state:
            date_states = {k: v for k, v in state.items() if _DATE_PATTERN.match(v)}
            if date_states and all(v == today for v in date_states.values()):
                logger.info("Heartbeat: all date-gated tasks done today, skipping")
                return
            state_lines = "\n".join(
                f"- {k}: {v} ({'done today — skip' if _DATE_PATTERN.match(v) and v == today else 'stale — run' if _DATE_PATTERN.match(v) else ''})"
                for k, v in state.items()
            )
            content = f"## Workspace State\n{state_lines}\n\n{content}"

        logger.info("Heartbeat: checking for tasks...")

        try:
            action, tasks = await self._decide(content)

            if action != "run":
                logger.info("Heartbeat: OK (nothing to report)")
                return

            logger.info("Heartbeat: tasks found, executing...")
            if self.on_execute:
                response = await self.on_execute(tasks)

                if response:
                    should_notify = await evaluate_response(
                        response, tasks,
                        self.fast_provider or self.provider,
                        self.fast_model or self.model,
                    )
                    if should_notify and self.on_notify:
                        logger.info("Heartbeat: completed, delivering response")
                        await self.on_notify(response)
                    else:
                        logger.info("Heartbeat: silenced by post-run evaluation")
        except Exception:
            logger.exception("Heartbeat execution failed")

    async def trigger_now(self) -> str | None:
        """Manually trigger a heartbeat."""
        content = self._read_heartbeat_file()
        if not content:
            return None
        state = self._collect_workspace_state()
        if state:
            today = date.today().isoformat()
            state_lines = "\n".join(
                f"- {k}: {v} ({'done today — skip' if _DATE_PATTERN.match(v) and v == today else 'stale — run' if _DATE_PATTERN.match(v) else ''})"
                for k, v in state.items()
            )
            content = f"## Workspace State\n{state_lines}\n\n{content}"
        action, tasks = await self._decide(content)
        if action != "run" or not self.on_execute:
            return None
        return await self.on_execute(tasks)
