import asyncio
from backend.services.llm_service import llm_service

async def main():
    async for chunk in llm_service.stream_generate("Tell me a story with a lot of emojis like fire and water.", max_tokens=30):
        print(repr(chunk))

asyncio.run(main())
