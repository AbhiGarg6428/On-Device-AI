import queue
import sounddevice as sd
import vosk
import json
import pyttsx3
import requests

# Load Vosk model
model = vosk.Model("model")
q = queue.Queue()

def callback(indata, frames, time, status):
    if status:
        print(status)
    q.put(bytes(indata))

# Text to speech
engine = pyttsx3.init()

def speak(text):
    print("AI:", text)
    engine.say(text)
    engine.runAndWait()

# Chat function (Phi model)
def chat(prompt):
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "phi",
            "prompt": prompt,
            "stream": False
        }
    )
    return response.json()["response"]

# 🎤 Change mic index if needed (0,1,2...)
MIC_DEVICE = None

# Speech recognition
with sd.RawInputStream(
    samplerate=16000,
    blocksize=8000,
    dtype='int16',
    channels=1,
    callback=callback,
    device=MIC_DEVICE
):

    rec = vosk.KaldiRecognizer(model, 16000)

    print("🎤 Listening... Speak something (Ctrl+C to stop)\n")

    while True:
        data = q.get()

        if rec.AcceptWaveform(data):
            print("🎧 Processing...")   # Optional debug (clean)

            result = json.loads(rec.Result())
            text = result.get("text", "")

            if text:
                print("You:", text)

                reply = chat(text)
                speak(reply)