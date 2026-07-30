# Eno AI: The Offline Engineering Professor

> **Built for the Gemma 4 Hackathon Sprint**
> **Track:** AI off the Grid

Eno AI is a privacy-first, fully local AI engineering assistant designed to run completely offline on Apple Silicon. By leveraging Google DeepMind's `gemma-2-2b-it` model via Apple MLX, Eno acts as a highly competent, low-latency mentor without ever transmitting your proprietary code or conversations to the cloud.

## Key Features

- **100% Offline Intelligence:** Core reasoning is powered by Gemma 2 running locally via MLX, completely eliminating cloud dependencies.
- **Hands-Free Voice Interactions:** Integrated local Whisper models transcribe your voice in real-time, allowing you to brainstorm architectures or dictate code aloud.
- **Context-Aware Memory (RAG):** Built-in Qdrant vector database stores your historical conversations and documents, meaning Eno naturally remembers your coding style, previous bugs, and project context.
- **Agentic Workflows:** Integrated Model Context Protocol (MCP) support allows Eno to read local files, execute terminal commands, and perform semantic searches within your IDE.

## Architecture

Eno is built on a modern, decoupled stack to ensure maximum performance on edge devices:
1. **Frontend:** A responsive, interactive UI built with Next.js (React) and Tailwind CSS.
2. **Backend:** A high-throughput async Python server using FastAPI.
3. **AI Engine:** `mlx_lm` running `mlx-community/gemma-2-2b-it`.
4. **Database:** SQLite for chat history, Redis for task queuing, and Qdrant for vector embeddings.
5. **Orchestrator:** A custom Python script (`start_project.py`) automatically spins up the entire stack (including Docker containers) concurrently.

## Local Setup

### Prerequisites
- macOS (Apple Silicon M1/M2/M3 highly recommended for MLX)
- Python 3.12+
- Node.js & npm
- Docker (for Qdrant & Redis)

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/abhinavkumars1ngh/ENO-the-assistant.git
   cd ENO-the-assistant
   ```

2. Download the Gemma model:
   ```bash
   hf download mlx-community/gemma-2-2b-it
   ```

3. Start the entire pipeline:
   ```bash
   python3 start_project.py
   ```
   
This will automatically launch the backend, the Celery workers, the Qdrant instance, and the Next.js frontend at `http://localhost:3000`.

## Hackathon Context
This project was developed rapidly during the 1-day **Gemma 4 Hackathon Sprint**. The primary technical challenge was managing the memory and compute overhead of running an LLM, a TTS engine, a Whisper transcriber, and a Vector DB concurrently on edge hardware. Using MLX's unified memory and FastAPI's async event loop was critical in achieving a fluid, sub-second response time off the grid.
