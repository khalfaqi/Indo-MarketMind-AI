import asyncio
import uvicorn
from main import app
from app.services.user_interface_service import run_bot

async def run_api():
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    await asyncio.gather(
        run_api(),
        run_bot(),
    )

if __name__ == "__main__":
    asyncio.run(main())
