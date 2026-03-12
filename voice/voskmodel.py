import queue
import sounddevice as sd
import vosk
import json
import pyttsx3
import requests
import os
import threading
import pyautogui
from PIL import Image
import tkinter as tk
from tkinter import filedialog
import webbrowser
import time

# ================= GLOBAL MODE =================
MODE = "both"

# ================= MODE SELECT =================
def choose_mode():
    global MODE

    print("\nSelect Mode:")
    print("1. Voice Only 🎤")
    print("2. Type Only ⌨️")
    print("3. Both 🔥")

    choice = input("Enter (1/2/3): ").strip()

    if choice == "1":
        MODE = "voice"
    elif choice == "2":
        MODE = "type"
    else:
        MODE = "both"

    print(f"\n✅ Mode Selected: {MODE.upper()}\n")

# ================= SPEECH =================
speech_queue = queue.Queue()
engine = pyttsx3.init()

def speak(text):
    print("AI:", text)
    speech_queue.put(text)

def speech_worker():
    while True:
        text = speech_queue.get()
        engine.say(text)
        engine.runAndWait()

# ================= VOICE =================
model = vosk.Model("model")
audio_queue = queue.Queue()

def callback(indata, frames, time_, status):
    audio_queue.put(bytes(indata))

# ================= AI =================
def chat(prompt):
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "mistral", "prompt": prompt, "stream": False}
        )
        return response.json()["response"].strip()
    except:
        return "AI not responding"

# ================= IMAGE → PDF =================
def image_to_pdf():
    root = tk.Tk()
    root.withdraw()

    file_path = filedialog.askopenfilename(
        filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")]
    )

    if not file_path:
        return "No file selected"

    img = Image.open(file_path)
    if img.mode == "RGBA":
        img = img.convert("RGB")

    output = file_path.rsplit(".", 1)[0] + ".pdf"
    img.save(output, "PDF")

    return f"PDF created: {output}"

# ================= INDEX =================
app_index = {}

def build_index():
    paths = [
        "C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs",
        os.path.expanduser("~\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs"),
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        os.path.expanduser("~\\Desktop"),
        os.path.expanduser("~\\Documents"),
        os.path.expanduser("~\\Downloads")
    ]

    print("🔍 Building index...")

    for path in paths:
        for root, dirs, files in os.walk(path):
            for name in files + dirs:
                app_index[name.lower()] = os.path.join(root, name)

    print(f"✅ Indexed {len(app_index)} items\n")

# ================= CLEAN =================
def clean_query(q):
    remove = ["app", "application", "software", "program", "folder", "directory"]
    return " ".join([w for w in q.lower().split() if w not in remove])

# ================= SMART OPEN =================
def open_from_index(query):
    query = clean_query(query)
    words = query.split()

    if not words:
        return None

    main = words[0]

    best_score = -999
    best = None

    for name, path in app_index.items():
        n = name.lower()

        if main not in n:
            continue

        score = 0

        base = n.replace(".exe", "").replace(".lnk", "")
        if base == main:
            score += 15

        for w in words:
            if w in n:
                score += 3

        if n.endswith(".lnk"):
            score += 6

        if n.endswith(".exe"):
            score += 5

        if any(x in n for x in ["error", "report", "helper", "setup", "update", "uninstall"]):
            score -= 10

        if score > best_score:
            best_score = score
            best = (name, path)

    if best:
        os.startfile(best[1])
        return f"Opening {best[0]}"

    return None

# ================= WEBSITE =================
def open_website(query):
    query = query.replace("website", "").strip()
    domain = query.replace(" ", "") + ".com"
    url = "https://www." + domain

    try:
        webbrowser.open(url)
        return f"Opening {url}"
    except:
        webbrowser.open(f"https://www.google.com/search?q={query}")
        return f"Searching {query}"

# ================= CONTROL =================
def control_pc(cmd):
    cmd = cmd.lower()

    if "convert image to pdf" in cmd:
        return image_to_pdf()

    if cmd.startswith("open "):
        name = cmd.replace("open ", "")
        result = open_from_index(name)
        if result:
            return result
        return f"Could not find {name}"

    return None

# ================= PROCESS =================
def process_command(text):
    print("You:", text)
    cmd = text.lower()

    # 🌐 WEBSITE
    if "chrome" in cmd or "browser" in cmd:
        clean = cmd.replace("open", "").replace("on chrome", "").replace("in chrome", "")
        result = open_website(clean)
        speak(result)
        print("AI:", result)
        print("✅ Done\n")
        return

    # ⚡ FAST OPEN
    if cmd.startswith("open "):
        result = control_pc(cmd)
        if result:
            speak(result)
            print("AI:", result)
            print("✅ Done\n")
            return

    # 🧠 AI
    reply = chat(text)
    speak(reply)
    print("AI:", reply)
    print("✅ Done\n")

# ================= THREADS =================
def voice_loop():
    with sd.RawInputStream(samplerate=16000, blocksize=8000,
                           dtype='int16', channels=1,
                           callback=callback):
        rec = vosk.KaldiRecognizer(model, 16000)

        while True:
            data = audio_queue.get()
            if rec.AcceptWaveform(data):
                txt = json.loads(rec.Result()).get("text", "")
                if txt:
                    process_command(txt)

def text_loop():
    while True:
        cmd = input("\nYou: ").strip()

        if not cmd:
            continue

        if cmd == "exit":
            os._exit(0)

        process_command(cmd)

# ================= MAIN =================
if __name__ == "__main__":
    print("🔥 JARVIS STARTING 🔥")

    choose_mode()  # ✅ FIXED

    build_index()

    if MODE == "voice":
        threading.Thread(target=voice_loop, daemon=True).start()

    elif MODE == "type":
        threading.Thread(target=text_loop).start()

    else:
        threading.Thread(target=voice_loop, daemon=True).start()
        threading.Thread(target=text_loop).start()

    threading.Thread(target=speech_worker, daemon=True).start()