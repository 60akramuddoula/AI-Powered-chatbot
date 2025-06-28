from fastapi import FastAPI
from fastapi.responses import StreamingResponse, RedirectResponse
from pydantic import BaseModel
import ollama
import gradio as gr
import asyncio
import requests
import uvicorn

app = FastAPI()

# Store simple in-memory session history
sessions = {}

class ChatRequest(BaseModel):
    message: str
    session_id: str


@app.get("/")
def root():
    return RedirectResponse(url="/gradio")


@app.post("/chat")
async def chat_post(request: ChatRequest):
    if request.session_id not in sessions:
        sessions[request.session_id] = []

    sessions[request.session_id].append({"role": "user", "content": request.message})

    response = ollama.chat(
        model="gemma3-chat",
        messages=sessions[request.session_id]
    )

    sessions[request.session_id].append({"role": "assistant", "content": response["message"]})
    return {"response": response["message"]}


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    if request.session_id not in sessions:
        sessions[request.session_id] = []

    sessions[request.session_id].append({"role": "user", "content": request.message})

    async def generate():
        stream = ollama.chat(
            model="gemma3-chat",
            messages=sessions[request.session_id],
            stream=True
        )
        buffer = ""
        for chunk in stream:
            piece = chunk["message"]["content"]
            buffer += piece
            yield piece
            await asyncio.sleep(0)

        sessions[request.session_id].append({"role": "assistant", "content": buffer})

    return StreamingResponse(generate(), media_type="text/plain")


# Gradio UI
def create_gradio():
    def chat(user_message, history):
        session_id = "demo-session"
        with requests.post(
            "http://127.0.0.1:8000/chat/stream",
            json={"message": user_message, "session_id": session_id},
            stream=True
        ) as r:
            buffer = ""
            for chunk in r.iter_content(chunk_size=None):
                if chunk:
                    buffer += chunk.decode()
                    yield buffer

    return gr.ChatInterface(
        fn=chat,
        title="Gemma3 Chatbot",
        description="FastAPI + Gradio + Streaming"
    )

gr.mount_gradio_app(app, create_gradio(), path="/gradio")


if __name__ == "__main__":
    uvicorn.run("chatbot_api:app", host="127.0.0.1", port=8000, reload=True)
