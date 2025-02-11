import requests
from fastapi import FastAPI, Response
from fastapi.responses import StreamingResponse

app = FastAPI()


@app.get("/tts")
async def text_to_speech(text: str):
    # ElevenLabs API endpoint (replace with actual endpoint)
    url = "https://api.elevenlabs.io/v1/text-to-speech/:voice_id/stream"

    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": "YOUR_API_KEY",
    }

    data = {"text": text, "voice_settings": {"stability": 0, "similarity_boost": 0}}

    async def generate():
        with requests.post(url, json=data, headers=headers, stream=True) as response:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk

    return StreamingResponse(generate(), media_type="audio/mpeg")
