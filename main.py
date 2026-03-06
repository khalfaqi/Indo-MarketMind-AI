import uuid
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from typing import Optional
from fastapi import FastAPI, HTTPException
from app.agent.brain import build_agent_graph

agent_graph = build_agent_graph()

app = FastAPI(title="Welcome to MarketMind")

class ChatRequest(BaseModel):
    question: str                         
    thread_id: Optional[str] = None  

class ChatResponse(BaseModel):
    answer: str
    thread_id: str

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):

    thread_id = request.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    try:
        response = await agent_graph.ainvoke(
            {"messages": [HumanMessage(content=request.question)]},  
            config=config
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    last_message = response["messages"][-1] 

    return ChatResponse(
        answer=last_message.content if last_message else "Maaf, tidak ada jawaban.",
        thread_id=thread_id  
    )
