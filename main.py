from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from googletrans import Translator
from gtts import gTTS
import speech_recognition as sr
from pydub import AudioSegment
import os
from cryptography.fernet import Fernet

app = FastAPI()
translator = Translator()

origins = [
    "https://translator-web-app-frontend-56p1se6sx.vercel.app",  # Your frontend
    "http://localhost:3000",  # Local development
]

app.add_middleware(
    CORSMiddleware,
    allow_origins= origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Encryption key setup
ENCRYPTION_KEY = Fernet.generate_key()
cipher = Fernet(ENCRYPTION_KEY)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

class TextTranslationRequest(BaseModel):
    text: str
    source_lang: str
    target_lang: str

import time  # Add this at the top to generate unique filenames

@app.post("/text-translate/")
async def translate_text(request: TextTranslationRequest):
    if not request.text or request.text.strip() == "":
        return {"error": "Text input is required"}
    
    translated_text = translator.translate(request.text, src=request.source_lang, dest=request.target_lang).text

    if not translated_text:
        return {"error": "Translation failed"}

    # Generate a unique filename using a timestamp
    timestamp = int(time.time())  # Example: 1709832000
    audio_filename = f"translated_audio_{timestamp}.mp3"
    encrypted_filename = f"translated_audio_{timestamp}.enc"

    audio_path = os.path.join(OUTPUT_FOLDER, audio_filename)
    tts = gTTS(translated_text, lang=request.target_lang)
    tts.save(audio_path)

    # Encrypt the new audio file
    with open(audio_path, "rb") as f:
        encrypted_data = cipher.encrypt(f.read())

    encrypted_path = os.path.join(OUTPUT_FOLDER, encrypted_filename)
    with open(encrypted_path, "wb") as f:
        f.write(encrypted_data)

    return {"translated_text": translated_text, "audio_file": encrypted_filename}


@app.get("/audio/{filename}")
async def get_audio(filename: str):
   
    
    encrypted_path = os.path.join(OUTPUT_FOLDER, filename)
    if not os.path.exists(encrypted_path):
        return {"error": "File not found"}

    with open(encrypted_path, "rb") as f:
        encrypted_data = f.read()

    decrypted_data = cipher.decrypt(encrypted_data)
    decrypted_path = os.path.join(OUTPUT_FOLDER, "decrypted_audio.mp3")

    with open(decrypted_path, "wb") as f:
        f.write(decrypted_data)

    return FileResponse(decrypted_path, media_type="audio/mpeg", filename="translated_audio.mp3")


@app.post("/speech-to-text/")
async def speech_to_text(file: UploadFile = File(...), lang: str = Form("en")):
    audio_path = os.path.join(UPLOAD_FOLDER, file.filename)
    with open(audio_path, "wb") as f:
        f.write(await file.read())

    recognizer = sr.Recognizer()
    audio = AudioSegment.from_file(audio_path)
    audio.export("converted.wav", format="wav")

    with sr.AudioFile("converted.wav") as source:
        audio_data = recognizer.record(source)
        try:
            text = recognizer.recognize_google(audio_data, language=lang)
            return {"transcribed_text": text}
        except sr.UnknownValueError:
            return {"error": "Could not recognize speech"}
        except sr.RequestError:
            return {"error": "Speech recognition service error"}

@app.post("/speech-translate/")
async def speech_translate(file: UploadFile = File(...), source_lang: str = Form("en"), target_lang: str = Form("en")):
    transcription = await speech_to_text(file, lang=source_lang)
    if "error" in transcription:
        return transcription

    translated_text = translator.translate(transcription["transcribed_text"], src=source_lang, dest=target_lang).text
    tts = gTTS(translated_text, lang=target_lang)
    audio_path = os.path.join(OUTPUT_FOLDER, "translated_speech.mp3")
    tts.save(audio_path)

    return {"translated_text": translated_text, "audio_file": "translated_speech.mp3"}
