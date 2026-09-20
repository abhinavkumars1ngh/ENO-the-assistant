from backend.services.llm_service import llm_service
import asyncio

async def main():
    print("Testing stream...")
    try:
        async for chunk in llm_service.stream_generate("hi", max_tokens=10):
            print("CHUNK:", chunk)
    except Exception as e:
        print("ERROR:", e)

asyncio.run(main())
