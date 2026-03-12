import queue
import sounddevice as sd
import vosk
import json
import pyttsx3
import requests
import os
import threading

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

# PC Control
def control_pc(command):
    command = command.lower()

    if "open chrome" in command:
        os.system("start chrome")
        return "Opening Chrome"

    elif "open vscode" in command:
        os.system("code")
        return "Opening VS Code"

    elif "shutdown" in command:
        os.system("shutdown /s /t 1")
        return "Shutting down system"

    elif "restart" in command:
        os.system("shutdown /r /t 1")
        return "Restarting system"

    elif "lock" in command:
        os.system("rundll32.exe user32.dll,LockWorkStation")
        return "Locking system"

    elif "open youtube" in command:
        os.system("start https://youtube.com")
        return "Opening YouTube"

    return None

# Handle input (voice or text)
def process_command(text):
    print("You:", text)

    action = control_pc(text)

    if action:
        speak(action)
    else:
        reply = chat(text)
        speak(reply)

# 🎤 Voice Thread
def voice_loop():
    with sd.RawInputStream(
        samplerate=16000,
        blocksize=8000,
        dtype='int16',
        channels=1,
        callback=callback,
        device=None
    ):
        rec = vosk.KaldiRecognizer(model, 16000)
        print("🎤 Voice mode active...")

        while True:
            data = q.get()

            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text = result.get("text", "")

                if text:
                    process_command(text)

# ⌨️ Text Input Thread
def text_loop():
    print("⌨️ Type mode active... (type 'exit' to quit)\n")

    while True:
        user_input = input("You (type): ")

        if user_input.lower() == "exit":
            os._exit(0)

        process_command(user_input)

# 🚀 Start both threads
if __name__ == "__main__":
    print("🔥 JARVIS STARTED (Voice + Typing Mode)\n")

    t1 = threading.Thread(target=voice_loop)
    t2 = threading.Thread(target=text_loop)

    t1.start()
    t2.start()