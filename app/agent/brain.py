from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import InMemorySaver  
from app.agent.state import AgentState
from app.tools.stock_tool import TOOLS
from app.agent.router import classify_intent, route_by_intent
from app.agent.nodes import (
    run_tool_call,
    generate_final_answer,
    direct_answer,
    ask_clarification,
    route_after_tool,
)


tool_node = ToolNode(TOOLS)
checkpointer = InMemorySaver()  


def build_agent_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    # Nodes
    workflow.add_node("classify_intent",       classify_intent)
    workflow.add_node("ask_clarification",     ask_clarification)
    workflow.add_node("run_tool_call",         run_tool_call)
    workflow.add_node("tools",                 tool_node)
    workflow.add_node("generate_final_answer", generate_final_answer)
    workflow.add_node("direct_answer",         direct_answer)
    workflow.add_node("route_after_tool",      route_after_tool)

    # Edges
    workflow.add_edge(START, "classify_intent")

    workflow.add_conditional_edges("classify_intent", route_by_intent, {
        "ask_clarification": "ask_clarification",
        "run_tool_call":     "run_tool_call",
        "direct_answer":     "direct_answer",
    })

    workflow.add_conditional_edges("run_tool_call", tools_condition, {
        "tools": "tools",
        END:     END
    })

    workflow.add_edge("tools",               "generate_final_answer")
    workflow.add_edge("ask_clarification",   END)
    workflow.add_edge("generate_final_answer", END)
    workflow.add_edge("direct_answer",       END)

    return workflow.compile(checkpointer=checkpointer)  
