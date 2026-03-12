import tkinter as tk
from tkinter import ttk
import threading
import time
import queue
import re
from GcoreX import GcoreXAgent

# ================= INIT AGENT =================
# Disable agent's internal TTS to handle it in GUI with sentence segmentation
agent = GcoreXAgent(speak_output=False)

# ================= GLOBAL STATE =================
voice_enabled = None # Initialized after root
current_ai_bubble = None
token_buffer = ""
sentence_buffer = ""

# ================= COLORS =================
BG = "#121212"
SIDEBAR = "#1e1e1e"
CHAT_BG = "#181818"
USER_BUBBLE = "#0078D4"
AI_BUBBLE = "#2D2D30"
TEXT = "#FFFFFF"
STATUS = "#00D26A"
SECONDARY_TEXT = "#AAAAAA"

# ================= WINDOW =================
root = tk.Tk()
root.title("GcoreX AI")
root.geometry("1000x700")
root.configure(bg=BG)

voice_enabled = tk.BooleanVar(value=True)

# ================= MAIN LAYOUT =================
main = tk.Frame(root, bg=BG)
main.pack(fill=tk.BOTH, expand=True)

# ================= SIDEBAR =================
sidebar = tk.Frame(main, bg=SIDEBAR, width=220)
sidebar.pack(side=tk.LEFT, fill=tk.Y)
sidebar.pack_propagate(False)

title = tk.Label(
    sidebar,
    text="GcoreX",
    bg=SIDEBAR,
    fg=TEXT,
    font=("Segoe UI", 16, "bold")
)
title.pack(pady=20)

# Voice Toggle
voice_frame = tk.Frame(sidebar, bg=SIDEBAR)
voice_frame.pack(fill=tk.X, padx=15, pady=10)

tk.Checkbutton(
    voice_frame,
    text="Enable Voice",
    variable=voice_enabled,
    bg=SIDEBAR,
    fg=TEXT,
    selectcolor=SIDEBAR,
    activebackground=SIDEBAR,
    activeforeground=TEXT,
    font=("Segoe UI", 10)
).pack(side=tk.LEFT)

# Tools Section
tk.Label(
    sidebar,
    text="AVAILABLE TOOLS",
    bg=SIDEBAR,
    fg=SECONDARY_TEXT,
    font=("Segoe UI", 8, "bold")
).pack(pady=(20, 5), padx=15, anchor="w")

tool_list_frame = tk.Frame(sidebar, bg=SIDEBAR)
tool_list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

tool_list = tk.Listbox(
    tool_list_frame,
    bg=SIDEBAR,
    fg=TEXT,
    borderwidth=0,
    highlightthickness=0,
    font=("Segoe UI", 9),
    selectbackground="#333333"
)
tool_list.pack(fill=tk.BOTH, expand=True)

for tool in sorted(agent.tools.tools):
    tool_list.insert(tk.END, f"• {tool}")

# ================= RIGHT PANEL =================
right = tk.Frame(main, bg=CHAT_BG)
right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

# ================= CHAT AREA =================
canvas = tk.Canvas(right, bg=CHAT_BG, highlightthickness=0)
scrollbar = ttk.Scrollbar(right, orient="vertical", command=canvas.yview)

chat_frame = tk.Frame(canvas, bg=CHAT_BG)
chat_frame.columnconfigure(0, weight=1)

canvas.create_window((0, 0), window=chat_frame, anchor="nw", width=750)

def on_canvas_configure(event):
    canvas.itemconfig(1, width=event.width)

canvas.bind("<Configure>", on_canvas_configure)

def update_scroll(event=None):
    canvas.configure(scrollregion=canvas.bbox("all"))
    canvas.yview_moveto(1.0)

chat_frame.bind("<Configure>", update_scroll)

canvas.configure(yscrollcommand=scrollbar.set)
canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

# ================= STATUS BAR =================
status_var = tk.StringVar(value="🟢 Ready")
status_bar = tk.Label(
    right,
    textvariable=status_var,
    bg="#202020",
    fg=STATUS,
    anchor="w",
    padx=15,
    pady=5,
    font=("Segoe UI", 9)
)
status_bar.pack(fill=tk.X)

# ================= MESSAGE RENDERING =================
def add_message(text, sender="ai"):
    global current_ai_bubble
    
    row = tk.Frame(chat_frame, bg=CHAT_BG)
    row.pack(fill=tk.X, padx=20, pady=8)
    
    if sender == "user":
        color = USER_BUBBLE
        anchor = "e"
        padx = (100, 0)
    else:
        color = AI_BUBBLE
        anchor = "w"
        padx = (0, 100)

    bubble = tk.Label(
        row,
        text=text,
        bg=color,
        fg=TEXT,
        wraplength=500,
        justify="left",
        padx=15,
        pady=10,
        font=("Segoe UI", 11)
    )
    bubble.pack(anchor=anchor, padx=padx)
    
    if sender == "ai":
        current_ai_bubble = bubble
    
    root.after(10, update_scroll)
    return bubble

def update_ai_message(new_text):
    global current_ai_bubble
    if current_ai_bubble:
        current_ai_bubble.config(text=new_text)
        root.after(10, update_scroll)

# ================= VOICE SYSTEM =================
def speak_sentence(text):
    if not voice_enabled.get():
        return
    
    def run_tts():
        try:
            # Re-init TTS for this thread to avoid issues
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print(f"TTS Thread Error: {e}")

    threading.Thread(target=run_tts, daemon=True).start()

# ================= STREAMING LOGIC =================
def handle_token(token):
    global token_buffer, sentence_buffer, current_ai_bubble
    
    token_buffer += token
    sentence_buffer += token
    
    # Update GUI in chunks to prevent lag
    if len(token_buffer) >= 5 or any(p in token for p in ".!?\n"):
        if current_ai_bubble:
            full_text = current_ai_bubble.cget("text") + token_buffer
            root.after(0, lambda t=full_text: update_ai_message(t))
            token_buffer = ""
    
    # Voice output based on sentences
    if any(p in token for p in ".!?\n"):
        sentence = sentence_buffer.strip()
        if len(sentence) > 1:
            root.after(0, lambda s=sentence: speak_sentence(s))
        sentence_buffer = ""

# ================= SEND MESSAGE =================
def send_message():
    text = entry.get().strip()
    if not text:
        return
    
    entry.delete(0, tk.END)
    add_message(text, "user")
    
    status_var.set("🧠 Thinking...")
    
    # Start AI in worker thread
    threading.Thread(target=process_ai_response, args=(text,), daemon=True).start()

def process_ai_response(text):
    global token_buffer, sentence_buffer
    token_buffer = ""
    sentence_buffer = ""
    
    # Create empty AI bubble for streaming
    root.after(0, lambda: add_message("", "ai"))
    
    try:
        # Pass the handle_token callback for live streaming
        # Re-using the same callback for all types of responses if needed
        response = agent.process(text, token_callback=handle_token)
        
        # Flush any remaining buffer
        if token_buffer:
            final_text = response # Use final response to ensure completion
            root.after(0, lambda t=final_text: update_ai_message(t))
            
        if sentence_buffer.strip():
            root.after(0, lambda s=sentence_buffer.strip(): speak_sentence(s))
            
        root.after(0, lambda: status_var.set("🟢 Ready"))
        
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        root.after(0, lambda: status_var.set("🔴 Error"))
        root.after(0, lambda: update_ai_message(error_msg))

# ================= INPUT BAR =================
input_frame = tk.Frame(right, bg="#202020", pady=10)
input_frame.pack(side=tk.BOTTOM, fill=tk.X)

entry = tk.Entry(
    input_frame,
    bg="#2D2D30",
    fg=TEXT,
    insertbackground=TEXT,
    borderwidth=0,
    font=("Segoe UI", 12),
    highlightthickness=1,
    highlightbackground="#333333",
    highlightcolor=USER_BUBBLE
)
entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(20, 10), ipady=8)
entry.focus()
entry.bind("<Return>", lambda e: send_message())

send_btn = tk.Button(
    input_frame,
    text="Send",
    command=send_message,
    bg=USER_BUBBLE,
    fg="white",
    borderwidth=0,
    padx=25,
    font=("Segoe UI", 10, "bold"),
    cursor="hand2",
    activebackground="#005A9E",
    activeforeground="white"
)
send_btn.pack(side=tk.RIGHT, padx=(0, 20))

# ================= STARTUP =================
add_message("🤖 GcoreX online. Ready for commands.", "ai")

root.mainloop()
