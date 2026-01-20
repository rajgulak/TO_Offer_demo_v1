"""
Agent Memory Module

Provides memory capabilities for agentic systems:
- Short-term memory: Current conversation/session context
- Long-term memory: Persistent customer interaction history
- Episodic memory: Past offer decisions and outcomes
- Semantic memory: Learned patterns and preferences

Memory Types:
1. ConversationMemory: Track current session context
2. CustomerMemory: Historical customer interactions
3. OfferMemory: Past offer decisions and conversion outcomes
4. LearningMemory: Patterns learned from successful/failed offers
"""

import os
import json
import hashlib
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from collections import defaultdict

# Try to import Redis for distributed memory
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from .logging import get_logger

logger = get_logger("memory")


# =============================================================================
# MEMORY DATA STRUCTURES
# =============================================================================

@dataclass
class MemoryEntry:
    """A single memory entry with metadata."""
    key: str
    value: Any
    timestamp: datetime = field(default_factory=datetime.now)
    ttl_seconds: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if self.ttl_seconds is None:
            return False
        age = (datetime.now() - self.timestamp).total_seconds()
        return age > self.ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "ttl_seconds": self.ttl_seconds,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        return cls(
            key=data["key"],
            value=data["value"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            ttl_seconds=data.get("ttl_seconds"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class CustomerInteraction:
    """Record of a customer interaction."""
    customer_id: str
    pnr: str
    timestamp: datetime
    offer_type: Optional[str]
    offer_price: Optional[float]
    accepted: Optional[bool]
    channel: str
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class OfferOutcome:
    """Outcome of a previous offer decision."""
    pnr: str
    customer_id: str
    offer_type: str
    offer_price: float
    expected_value: float
    actual_outcome: Optional[str]  # "accepted", "rejected", "expired", "unknown"
    conversion_time_hours: Optional[float]
    feedback: Optional[str]
    timestamp: datetime = field(default_factory=datetime.now)


# =============================================================================
# MEMORY BACKENDS
# =============================================================================

class MemoryBackend(ABC):
    """Abstract base class for memory backends."""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        pass

    @abstractmethod
    def keys(self, pattern: str = "*") -> List[str]:
        pass

    @abstractmethod
    def clear(self) -> None:
        pass


class InMemoryBackend(MemoryBackend):
    """In-memory storage backend (single instance, non-persistent)."""

    def __init__(self):
        self._store: Dict[str, MemoryEntry] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.is_expired:
            self.delete(key)
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        self._store[key] = MemoryEntry(
            key=key,
            value=value,
            ttl_seconds=ttl_seconds,
        )

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def exists(self, key: str) -> bool:
        entry = self._store.get(key)
        if entry is None:
            return False
        if entry.is_expired:
            self.delete(key)
            return False
        return True

    def keys(self, pattern: str = "*") -> List[str]:
        import fnmatch
        all_keys = list(self._store.keys())
        if pattern == "*":
            return all_keys
        return [k for k in all_keys if fnmatch.fnmatch(k, pattern)]

    def clear(self) -> None:
        self._store.clear()


class RedisBackend(MemoryBackend):
    """Redis-based storage backend (distributed, persistent)."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        prefix: str = "tailored_offers:",
    ):
        if not REDIS_AVAILABLE:
            raise ImportError("Redis not available. Install with: pip install redis")

        self.client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        self.prefix = prefix

    def _key(self, key: str) -> str:
        return f"{self.prefix}{key}"

    def get(self, key: str) -> Optional[Any]:
        value = self.client.get(self._key(key))
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        serialized = json.dumps(value) if not isinstance(value, str) else value
        if ttl_seconds:
            self.client.setex(self._key(key), ttl_seconds, serialized)
        else:
            self.client.set(self._key(key), serialized)

    def delete(self, key: str) -> None:
        self.client.delete(self._key(key))

    def exists(self, key: str) -> bool:
        return self.client.exists(self._key(key)) > 0

    def keys(self, pattern: str = "*") -> List[str]:
        full_pattern = self._key(pattern)
        keys = self.client.keys(full_pattern)
        return [k.replace(self.prefix, "") for k in keys]

    def clear(self) -> None:
        keys = self.client.keys(f"{self.prefix}*")
        if keys:
            self.client.delete(*keys)


# =============================================================================
# SPECIALIZED MEMORY TYPES
# =============================================================================

class ConversationMemory:
    """
    Short-term memory for current conversation/session context.

    Tracks:
    - Current PNR being processed
    - Agent decisions made so far
    - User preferences expressed in session
    - Context accumulated across agent calls
    """

    def __init__(self, backend: Optional[MemoryBackend] = None, session_ttl: int = 3600):
        self.backend = backend or InMemoryBackend()
        self.session_ttl = session_ttl  # 1 hour default

    def start_session(self, session_id: str, pnr: str, context: Dict[str, Any] = None) -> None:
        """Start a new conversation session."""
        self.backend.set(
            f"session:{session_id}",
            {
                "pnr": pnr,
                "started_at": datetime.now().isoformat(),
                "context": context or {},
                "agent_decisions": [],
                "messages": [],
            },
            ttl_seconds=self.session_ttl,
        )
        logger.info("session_started", session_id=session_id, pnr=pnr)

    def add_agent_decision(
        self,
        session_id: str,
        agent_name: str,
        decision: Dict[str, Any],
    ) -> None:
        """Record an agent's decision in the session."""
        session = self.backend.get(f"session:{session_id}")
        if session:
            session["agent_decisions"].append({
                "agent": agent_name,
                "decision": decision,
                "timestamp": datetime.now().isoformat(),
            })
            self.backend.set(f"session:{session_id}", session, ttl_seconds=self.session_ttl)

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Add a message to the conversation history."""
        session = self.backend.get(f"session:{session_id}")
        if session:
            session["messages"].append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
            })
            self.backend.set(f"session:{session_id}", session, ttl_seconds=self.session_ttl)

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get the current session context."""
        return self.backend.get(f"session:{session_id}")

    def get_agent_decisions(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all agent decisions from the current session."""
        session = self.backend.get(f"session:{session_id}")
        return session.get("agent_decisions", []) if session else []

    def get_conversation_summary(self, session_id: str) -> str:
        """Generate a summary of the conversation for context."""
        session = self.backend.get(f"session:{session_id}")
        if not session:
            return ""

        summary_parts = [f"Session for PNR: {session['pnr']}"]

        for decision in session.get("agent_decisions", []):
            agent = decision["agent"]
            if "selected_offer" in decision.get("decision", {}):
                summary_parts.append(
                    f"- {agent}: Selected {decision['decision']['selected_offer']}"
                )
            elif "customer_eligible" in decision.get("decision", {}):
                eligible = decision['decision']['customer_eligible']
                summary_parts.append(f"- {agent}: Customer {'eligible' if eligible else 'not eligible'}")

        return "\n".join(summary_parts)


class CustomerMemory:
    """
    Long-term memory for customer interaction history.

    Tracks:
    - Previous offers sent to this customer
    - Acceptance/rejection history
    - Preferred channels and timing
    - Lifetime value indicators
    """

    def __init__(self, backend: Optional[MemoryBackend] = None):
        self.backend = backend or InMemoryBackend()

    def record_interaction(self, interaction: CustomerInteraction) -> None:
        """Record a customer interaction."""
        key = f"customer:{interaction.customer_id}:interactions"
        interactions = self.backend.get(key) or []
        interactions.append(interaction.to_dict())

        # Keep last 100 interactions
        if len(interactions) > 100:
            interactions = interactions[-100:]

        self.backend.set(key, interactions)
        logger.info(
            "interaction_recorded",
            customer_id=interaction.customer_id,
            offer_type=interaction.offer_type,
        )

    def get_customer_history(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get customer's interaction history."""
        return self.backend.get(f"customer:{customer_id}:interactions") or []

    def get_acceptance_rate(self, customer_id: str, offer_type: Optional[str] = None) -> float:
        """Calculate customer's historical acceptance rate."""
        history = self.get_customer_history(customer_id)

        relevant = [
            h for h in history
            if h.get("accepted") is not None
            and (offer_type is None or h.get("offer_type") == offer_type)
        ]

        if not relevant:
            return 0.5  # Default for no history

        accepted = sum(1 for h in relevant if h.get("accepted"))
        return accepted / len(relevant)

    def get_preferred_channel(self, customer_id: str) -> Optional[str]:
        """Determine customer's preferred channel based on history."""
        history = self.get_customer_history(customer_id)

        channel_success = defaultdict(lambda: {"total": 0, "accepted": 0})
        for h in history:
            channel = h.get("channel")
            if channel:
                channel_success[channel]["total"] += 1
                if h.get("accepted"):
                    channel_success[channel]["accepted"] += 1

        if not channel_success:
            return None

        # Return channel with highest acceptance rate (min 2 interactions)
        best_channel = None
        best_rate = 0
        for channel, stats in channel_success.items():
            if stats["total"] >= 2:
                rate = stats["accepted"] / stats["total"]
                if rate > best_rate:
                    best_rate = rate
                    best_channel = channel

        return best_channel

    def get_customer_insights(self, customer_id: str) -> Dict[str, Any]:
        """Generate insights about a customer from their history."""
        history = self.get_customer_history(customer_id)

        if not history:
            return {
                "has_history": False,
                "total_interactions": 0,
                "insights": ["No previous interaction history"],
            }

        insights = []

        # Acceptance rate
        acceptance_rate = self.get_acceptance_rate(customer_id)
        if acceptance_rate > 0.6:
            insights.append("High historical acceptance rate - receptive to offers")
        elif acceptance_rate < 0.3:
            insights.append("Low historical acceptance rate - may need special approach")

        # Preferred channel
        preferred_channel = self.get_preferred_channel(customer_id)
        if preferred_channel:
            insights.append(f"Prefers {preferred_channel} channel based on past interactions")

        # Offer type preferences
        offer_counts = defaultdict(int)
        for h in history:
            if h.get("accepted") and h.get("offer_type"):
                offer_counts[h["offer_type"]] += 1

        if offer_counts:
            favorite = max(offer_counts.items(), key=lambda x: x[1])
            insights.append(f"Has accepted {favorite[0]} offers {favorite[1]} times")

        return {
            "has_history": True,
            "total_interactions": len(history),
            "acceptance_rate": acceptance_rate,
            "preferred_channel": preferred_channel,
            "insights": insights,
        }


class OfferMemory:
    """
    Memory for past offer decisions and outcomes.

    Tracks:
    - What offers were made
    - Expected vs actual outcomes
    - Conversion patterns
    - Time-based patterns
    """

    def __init__(self, backend: Optional[MemoryBackend] = None):
        self.backend = backend or InMemoryBackend()

    def record_offer(self, outcome: OfferOutcome) -> None:
        """Record an offer outcome."""
        # Store by PNR
        self.backend.set(
            f"offer:{outcome.pnr}",
            asdict(outcome) | {"timestamp": outcome.timestamp.isoformat()},
        )

        # Add to customer's offer history
        customer_key = f"customer:{outcome.customer_id}:offers"
        offers = self.backend.get(customer_key) or []
        offers.append(asdict(outcome) | {"timestamp": outcome.timestamp.isoformat()})
        self.backend.set(customer_key, offers[-50:])  # Keep last 50

        # Add to global offer history for learning
        self._update_offer_stats(outcome)

    def _update_offer_stats(self, outcome: OfferOutcome) -> None:
        """Update aggregate offer statistics for learning."""
        stats_key = f"stats:offer:{outcome.offer_type}"
        stats = self.backend.get(stats_key) or {
            "total": 0,
            "accepted": 0,
            "total_ev": 0,
            "total_revenue": 0,
        }

        stats["total"] += 1
        if outcome.actual_outcome == "accepted":
            stats["accepted"] += 1
            stats["total_revenue"] += outcome.offer_price
        stats["total_ev"] += outcome.expected_value

        self.backend.set(stats_key, stats)

    def get_offer_stats(self, offer_type: str) -> Dict[str, Any]:
        """Get aggregate statistics for an offer type."""
        stats = self.backend.get(f"stats:offer:{offer_type}")
        if not stats or stats["total"] == 0:
            return {
                "offer_type": offer_type,
                "total_offers": 0,
                "acceptance_rate": 0.5,  # Default
                "avg_expected_value": 0,
                "avg_actual_value": 0,
            }

        return {
            "offer_type": offer_type,
            "total_offers": stats["total"],
            "acceptance_rate": stats["accepted"] / stats["total"],
            "avg_expected_value": stats["total_ev"] / stats["total"],
            "avg_actual_revenue": stats["total_revenue"] / stats["total"] if stats["accepted"] > 0 else 0,
        }

    def get_similar_offers(
        self,
        customer_tier: str,
        offer_type: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Find similar past offers for learning."""
        # This would ideally use vector similarity search
        # For now, use simple key-based lookup
        pattern = f"offer:*"
        all_keys = self.backend.keys(pattern)

        similar = []
        for key in all_keys[:100]:  # Limit search
            offer = self.backend.get(key)
            if offer and offer.get("offer_type") == offer_type:
                similar.append(offer)
                if len(similar) >= limit:
                    break

        return similar


class LearningMemory:
    """
    Memory for learned patterns and preferences.

    Tracks:
    - Successful offer patterns
    - Failed offer patterns
    - Time-of-day patterns
    - Segment-specific insights
    """

    def __init__(self, backend: Optional[MemoryBackend] = None):
        self.backend = backend or InMemoryBackend()

    def record_pattern(
        self,
        pattern_type: str,
        pattern_key: str,
        success: bool,
        context: Dict[str, Any],
    ) -> None:
        """Record a pattern observation."""
        key = f"pattern:{pattern_type}:{pattern_key}"
        pattern = self.backend.get(key) or {
            "successes": 0,
            "failures": 0,
            "contexts": [],
        }

        if success:
            pattern["successes"] += 1
        else:
            pattern["failures"] += 1

        # Keep recent contexts for analysis
        pattern["contexts"].append({
            "success": success,
            "context": context,
            "timestamp": datetime.now().isoformat(),
        })
        pattern["contexts"] = pattern["contexts"][-20:]  # Keep last 20

        self.backend.set(key, pattern)

    def get_pattern_success_rate(self, pattern_type: str, pattern_key: str) -> float:
        """Get success rate for a specific pattern."""
        pattern = self.backend.get(f"pattern:{pattern_type}:{pattern_key}")
        if not pattern:
            return 0.5  # Default

        total = pattern["successes"] + pattern["failures"]
        if total == 0:
            return 0.5

        return pattern["successes"] / total

    def get_best_patterns(self, pattern_type: str, min_observations: int = 5) -> List[Dict[str, Any]]:
        """Get the most successful patterns of a type."""
        pattern_keys = self.backend.keys(f"pattern:{pattern_type}:*")

        patterns = []
        for key in pattern_keys:
            pattern = self.backend.get(key)
            if pattern:
                total = pattern["successes"] + pattern["failures"]
                if total >= min_observations:
                    patterns.append({
                        "key": key.split(":")[-1],
                        "success_rate": pattern["successes"] / total,
                        "total_observations": total,
                    })

        return sorted(patterns, key=lambda x: x["success_rate"], reverse=True)

    def get_recommendations(self, context: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on learned patterns."""
        recommendations = []

        # Check time-of-day patterns
        hour = datetime.now().hour
        time_key = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
        time_rate = self.get_pattern_success_rate("time_of_day", time_key)
        if time_rate > 0.6:
            recommendations.append(f"Good time to send offers ({time_key} has {time_rate:.0%} success rate)")
        elif time_rate < 0.4:
            recommendations.append(f"Consider delaying - {time_key} has lower success rate ({time_rate:.0%})")

        # Check loyalty tier patterns
        if "loyalty_tier" in context:
            tier = context["loyalty_tier"]
            tier_rate = self.get_pattern_success_rate("loyalty_tier", tier)
            if tier_rate > 0.5:
                recommendations.append(f"{tier} customers have good acceptance rate ({tier_rate:.0%})")

        return recommendations


# =============================================================================
# UNIFIED MEMORY MANAGER
# =============================================================================

class AgentMemory:
    """
    Unified memory manager for all agent memory types.

    Provides a single interface for:
    - Session/conversation memory
    - Customer history
    - Offer outcomes
    - Learned patterns
    """

    def __init__(
        self,
        backend: Optional[MemoryBackend] = None,
        use_redis: bool = False,
        redis_url: Optional[str] = None,
    ):
        # Initialize backend
        if use_redis and REDIS_AVAILABLE:
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            self.backend = RedisBackend(host=redis_host, port=redis_port)
            logger.info("memory_initialized", backend="redis")
        else:
            self.backend = backend or InMemoryBackend()
            logger.info("memory_initialized", backend="in_memory")

        # Initialize specialized memories
        self.conversation = ConversationMemory(self.backend)
        self.customer = CustomerMemory(self.backend)
        self.offers = OfferMemory(self.backend)
        self.learning = LearningMemory(self.backend)

    def get_context_for_agent(
        self,
        session_id: str,
        customer_id: str,
        agent_name: str,
    ) -> Dict[str, Any]:
        """
        Get relevant memory context for an agent.

        Returns accumulated context from all memory types.
        """
        context = {
            "session": self.conversation.get_session(session_id),
            "customer_insights": self.customer.get_customer_insights(customer_id),
            "previous_decisions": self.conversation.get_agent_decisions(session_id),
            "recommendations": self.learning.get_recommendations({"customer_id": customer_id}),
        }

        # Add agent-specific context
        if agent_name == "offer_orchestration":
            # Get offer statistics
            for offer_type in ["IU_BUSINESS", "IU_PREMIUM_ECONOMY", "MCE"]:
                context[f"{offer_type}_stats"] = self.offers.get_offer_stats(offer_type)

        return context

    def record_decision(
        self,
        session_id: str,
        customer_id: str,
        agent_name: str,
        decision: Dict[str, Any],
    ) -> None:
        """Record an agent decision in memory."""
        # Add to session
        self.conversation.add_agent_decision(session_id, agent_name, decision)

        # Record patterns for learning
        if "selected_offer" in decision:
            self.learning.record_pattern(
                pattern_type="offer_selection",
                pattern_key=decision["selected_offer"],
                success=True,  # Will be updated when outcome is known
                context={"customer_id": customer_id, "agent": agent_name},
            )

    def record_outcome(
        self,
        pnr: str,
        customer_id: str,
        offer_type: str,
        offer_price: float,
        expected_value: float,
        actual_outcome: str,
    ) -> None:
        """Record the final outcome of an offer."""
        outcome = OfferOutcome(
            pnr=pnr,
            customer_id=customer_id,
            offer_type=offer_type,
            offer_price=offer_price,
            expected_value=expected_value,
            actual_outcome=actual_outcome,
        )
        self.offers.record_offer(outcome)

        # Update learning memory
        success = actual_outcome == "accepted"
        self.learning.record_pattern(
            pattern_type="offer_outcome",
            pattern_key=offer_type,
            success=success,
            context={"pnr": pnr, "price": offer_price},
        )

        # Record customer interaction
        interaction = CustomerInteraction(
            customer_id=customer_id,
            pnr=pnr,
            timestamp=datetime.now(),
            offer_type=offer_type,
            offer_price=offer_price,
            accepted=success,
            channel="unknown",
        )
        self.customer.record_interaction(interaction)


# Global memory instance
_memory: Optional[AgentMemory] = None


def get_memory() -> AgentMemory:
    """Get the global memory instance."""
    global _memory
    if _memory is None:
        use_redis = os.getenv("USE_REDIS_MEMORY", "false").lower() == "true"
        _memory = AgentMemory(use_redis=use_redis)
    return _memory
