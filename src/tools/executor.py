"""
Tool Executor — dispatches agent function calls to ANF client methods.

When the Foundry agent determines a function needs to be called, it returns
a function name and JSON arguments. This executor routes that call to the
appropriate ANFClient method and returns the result as serialized JSON.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..anf_client.client import ANFClient

logger = logging.getLogger(__name__)

# Map of function names → ANFClient methods
FUNCTION_REGISTRY = {
    "list_capacity_pools",
    "list_volumes",
    "get_volume",
    "create_volume",
    "delete_volume",
    "create_snapshot",
    "list_snapshots",
    "delete_snapshot",
    "revert_volume",
    "resize_volume",
    "get_account_info",
    "check_volume_health",
    "get_quota_limits",
}


class ToolExecutor:
    """
    Executes function tool calls by routing them to ANFClient methods.

    Usage:
        executor = ToolExecutor(anf_client)
        result_json = executor.execute("create_snapshot", {
            "volume_name": "trading-data",
            "snapshot_name": "pre-batch-20250126"
        })
    """

    def __init__(self, anf_client: ANFClient):
        self.anf_client = anf_client

    def execute(self, function_name: str, arguments: dict[str, Any]) -> str:
        """
        Execute a function tool call and return the result as JSON.

        Args:
            function_name: Name of the function to call.
            arguments: Dictionary of function arguments.

        Returns:
            JSON string containing the function result.

        Raises:
            ValueError: If the function name is not recognized.
        """
        if function_name not in FUNCTION_REGISTRY:
            error_msg = f"Unknown function: {function_name}. Available: {sorted(FUNCTION_REGISTRY)}"
            logger.error(error_msg)
            return json.dumps({"error": error_msg})

        logger.info("Executing tool: %s with args: %s", function_name, arguments)

        try:
            result = self._dispatch(function_name, arguments)
            return self._serialize(result)
        except Exception as e:
            logger.error("Tool execution failed: %s — %s", function_name, str(e))
            return json.dumps(
                {
                    "error": str(e),
                    "function": function_name,
                    "arguments": arguments,
                }
            )

    def _dispatch(self, function_name: str, args: dict[str, Any]) -> Any:
        """Route the function call to the appropriate ANFClient method."""

        if function_name == "list_capacity_pools":
            return self.anf_client.list_capacity_pools()

        elif function_name == "list_volumes":
            return self.anf_client.list_volumes(
                pool_name=args.get("pool_name"),
            )

        elif function_name == "get_volume":
            return self.anf_client.get_volume(
                volume_name=args["volume_name"],
                pool_name=args.get("pool_name"),
            )

        elif function_name == "delete_volume":
            return self.anf_client.delete_volume(
                volume_name=args["volume_name"],
                pool_name=args.get("pool_name"),
            )

        elif function_name == "create_snapshot":
            return self.anf_client.create_snapshot(
                volume_name=args["volume_name"],
                snapshot_name=args["snapshot_name"],
                pool_name=args.get("pool_name"),
            )

        elif function_name == "list_snapshots":
            return self.anf_client.list_snapshots(
                volume_name=args["volume_name"],
                pool_name=args.get("pool_name"),
            )

        elif function_name == "delete_snapshot":
            return self.anf_client.delete_snapshot(
                volume_name=args["volume_name"],
                snapshot_name=args["snapshot_name"],
                pool_name=args.get("pool_name"),
            )

        elif function_name == "revert_volume":
            return self.anf_client.revert_volume(
                volume_name=args["volume_name"],
                snapshot_id=args["snapshot_id"],
                pool_name=args.get("pool_name"),
            )

        elif function_name == "resize_volume":
            return self.anf_client.resize_volume(
                volume_name=args["volume_name"],
                new_size_gib=args["new_size_gib"],
                pool_name=args.get("pool_name"),
            )

        elif function_name == "get_account_info":
            return self.anf_client.get_account_info()

        elif function_name == "create_volume":
            return self.anf_client.create_volume(
                volume_name=args["volume_name"],
                size_gib=args["size_gib"],
                pool_name=args.get("pool_name"),
                protocol=args.get("protocol", "NFSv4.1"),
            )

        elif function_name == "check_volume_health":
            return self.anf_client.check_volume_health(
                volume_name=args["volume_name"],
                pool_name=args.get("pool_name"),
            )

        elif function_name == "get_quota_limits":
            return self.anf_client.get_quota_limits()

        else:
            raise ValueError(f"Unhandled function: {function_name}")

    @staticmethod
    def _serialize(result: Any) -> str:
        """Serialize the result to JSON, handling Pydantic models and lists."""
        if isinstance(result, list):
            return json.dumps(
                [item.model_dump(mode="json") for item in result],
                indent=2,
                default=str,
            )
        elif hasattr(result, "model_dump"):
            return json.dumps(result.model_dump(mode="json"), indent=2, default=str)
        else:
            return json.dumps(result, indent=2, default=str)
