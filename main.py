import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config.settings import settings
from app.scrapers.news_scraper import CommodityNewsScraper
from app.services.db_service import QdrantService

# FastAPI

from fastapi import FastAPI
from app.agent.brain import agent_graph

app = FastAPI()

@app.post("/query")
async def handle_query(query: str):
    initial_state = {
        "messages": [{"role": "user", "content": query}]
    }
    final_state = await agent_graph.ainvoke(initial_state)
    return {"response": final_state.get("messages", [])[-1].content if final_state.get("messages") else "Maaf, saya tidak bisa menjawab pertanyaan Anda."}
