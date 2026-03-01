from typing import Literal
from langgraph.graph import MessagesState
from pydantic import BaseModel

class AgentState(MessagesState):
    """Extended state dengan metadata routing."""
    intent: Literal["analysis", "news", "hybrid"] | None
    ticker: str | None
    needs_clarification: bool

class IntentPlan(BaseModel):
    """Structured output untuk intent classifier."""
    intent: Literal["analysis", "news", "hybrid"]
    ticker: str | None = None
    needs_clarification: bool = False
    reasoning: str
