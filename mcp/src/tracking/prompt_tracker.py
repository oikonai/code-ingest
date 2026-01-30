"""Prompt usage tracking for dashboard analytics."""

from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class PromptStats:
    """Statistics for a single prompt."""
    usage_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    execution_times: List[float] = field(default_factory=list)
    last_used: Optional[datetime] = None


class PromptUsageTracker:
    """
    Singleton tracker for prompt usage statistics.

    Tracks execution counts, success rates, and execution times for all prompts.
    Statistics are session-based and reset on server restart.
    """

    _instance: Optional['PromptUsageTracker'] = None

    def __new__(cls):
        """Create or return the singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the tracker (only once)."""
        if self._initialized:
            return

        self.stats: Dict[str, PromptStats] = {}
        self._initialized = True
        logger.info("📊 Prompt usage tracker initialized")

    def record_execution(
        self,
        prompt_name: str,
        success: bool,
        duration_ms: float
    ) -> None:
        """
        Record a prompt execution.

        Args:
            prompt_name: Name of the prompt that was executed
            success: Whether the execution was successful
            duration_ms: Execution duration in milliseconds
        """
        if prompt_name not in self.stats:
            self.stats[prompt_name] = PromptStats()

        stats = self.stats[prompt_name]
        stats.usage_count += 1

        if success:
            stats.success_count += 1
        else:
            stats.failure_count += 1

        stats.execution_times.append(duration_ms)
        stats.last_used = datetime.now()

        logger.debug(
            f"📈 Recorded {prompt_name}: "
            f"success={success}, duration={duration_ms:.1f}ms"
        )

    def get_stats(self, time_window: str = "session", sort_by: str = "usage_count") -> Dict:
        """
        Get usage statistics for all prompts.

        Args:
            time_window: Time window for stats (currently only "session" is supported)
            sort_by: Sort criterion - "usage_count", "success_rate", or "avg_time"

        Returns:
            Dictionary with comprehensive prompt usage statistics
        """
        if not self.stats:
            return {
                "time_window": time_window,
                "total_prompt_executions": 0,
                "prompts": [],
                "insights": {
                    "most_popular": None,
                    "least_popular": None,
                    "highest_success_rate": None,
                    "slowest_prompt": None
                }
            }

        # Calculate metrics for each prompt
        prompt_list = []
        for prompt_name, stats in self.stats.items():
            success_rate = stats.success_count / stats.usage_count if stats.usage_count > 0 else 0.0
            avg_time = sum(stats.execution_times) / len(stats.execution_times) if stats.execution_times else 0.0

            prompt_list.append({
                "prompt_name": prompt_name,
                "usage_count": stats.usage_count,
                "success_count": stats.success_count,
                "failure_count": stats.failure_count,
                "success_rate": round(success_rate, 3),
                "avg_execution_time_ms": round(avg_time, 1),
                "last_used": stats.last_used.isoformat() if stats.last_used else None
            })

        # Sort by requested criterion
        if sort_by == "success_rate":
            prompt_list.sort(key=lambda x: x["success_rate"], reverse=True)
        elif sort_by == "avg_time":
            prompt_list.sort(key=lambda x: x["avg_execution_time_ms"])
        else:  # usage_count
            prompt_list.sort(key=lambda x: x["usage_count"], reverse=True)

        # Add popularity ranks
        for rank, prompt in enumerate(prompt_list, start=1):
            prompt["popularity_rank"] = rank

        # Calculate total executions
        total_executions = sum(p["usage_count"] for p in prompt_list)

        # Generate insights
        insights = {
            "most_popular": prompt_list[0]["prompt_name"] if prompt_list else None,
            "least_popular": prompt_list[-1]["prompt_name"] if prompt_list else None,
            "highest_success_rate": max(
                prompt_list,
                key=lambda x: x["success_rate"]
            )["prompt_name"] if prompt_list else None,
            "slowest_prompt": max(
                prompt_list,
                key=lambda x: x["avg_execution_time_ms"]
            )["prompt_name"] if prompt_list else None
        }

        return {
            "time_window": time_window,
            "total_prompt_executions": total_executions,
            "prompts": prompt_list,
            "insights": insights
        }

    def clear_stats(self) -> None:
        """Clear all statistics (useful for testing or reset)."""
        self.stats.clear()
        logger.info("🗑️  Prompt usage statistics cleared")

    def get_prompt_stat(self, prompt_name: str) -> Optional[PromptStats]:
        """
        Get statistics for a specific prompt.

        Args:
            prompt_name: Name of the prompt

        Returns:
            PromptStats object or None if prompt hasn't been executed
        """
        return self.stats.get(prompt_name)
