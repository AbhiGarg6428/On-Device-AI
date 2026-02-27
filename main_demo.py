import os
import requests
import pyttsx3

# ===== SETTINGS =====
MODEL = "gemma:2b"
engine = pyttsx3.init()

# ===== SPEAK =====
def speak(text):
    print("AI:", text)
    engine.say(text)
    engine.runAndWait()

# ===== AI =====
def ask_ai(prompt):
    try:
        res = requests.post("http://localhost:11434/api/generate", json={
            "model": MODEL,
            "prompt": f"Answer shortly: {prompt}",
            "stream": False
        })
        return res.json()["response"].strip()
    except:
        return "AI not responding"

# ===== COMMANDS =====
def open_chrome():
    os.system("start chrome")
    return "Opening Chrome"

def search_google(query):
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    os.system(f'start chrome "{url}"')
    return f"Searching {query}"

# ===== HANDLER =====
def handle_command(text):
    text = text.lower()

    if "search" in text:
        query = text.split("search")[-1].strip()
        if query:
            speak(search_google(query))
        return

    if "open chrome" in text:
        speak(open_chrome())
        return

    # AI fallback
    speak(ask_ai(text))

# ===== MAIN =====
def main():
    print("🔥 JARVIS DEMO 🔥")
    print("Type 'exit' to quit\n")

    while True:
        cmd = input("You: ")
        if cmd.lower() == "exit":
            break
        handle_command(cmd)

if __name__ == "__main__":
    main()