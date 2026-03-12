🤖 GcoreX AI

GcoreX is a modular AI assistant built in Python that runs locally using Ollama + Mistral.

It is designed as a terminal-based autonomous AI agent capable of reasoning, planning, tool execution, and maintaining long-term memory.

GcoreX focuses on speed, modular architecture, and local execution, allowing advanced AI capabilities to run on consumer hardware.

✨ Features
🧠 Intelligent Routing

A BrainRouter analyzes user input and decides whether to use:

Fast conversational response

Reasoning engine

Tool execution

Autonomous planning

This improves speed by avoiding unnecessary model calls.

⚡ Optimized LLM Engine

GcoreX uses Ollama models with:

streaming responses

token budgeting

reasoning routes

fast chat mode

This makes the AI more responsive and efficient.

🧰 Plugin-Based Tool System

The AI supports external tools/plugins which allow it to perform real actions.

Examples include:

Search queries

Open applications

Run commands

File analysis

Calculations

Tools can be added without modifying the core AI system.

🧠 Long-Term Memory

The system includes multiple memory layers:

conversation memory

vector knowledge memory

compressed memory summaries

tool success tracking

This allows GcoreX to remember useful knowledge across sessions.

🤖 Autonomous Planning

GcoreX can automatically break complex goals into tasks.

Example:

auto research electric vehicles

The AI will:

break the goal into tasks

queue tasks

execute them step-by-step

🔍 Research Agent

The built-in research agent can:

collect information

summarize results

store research in memory

🛠 Developer Mode

Developer mode displays internal logs such as:

routing decisions

reasoning output

tool execution

validation results

Enable it with:

dev mode on
🧠 Architecture Overview

The internal architecture follows a modular AI pipeline.

User Input
   ↓
Brain Router
   ↓
Reasoning Engine
   ↓
Planner / Tool Manager
   ↓
Memory Systems
   ↓
Response

Key components include:

BrainRouter

LLMEngine

ReasoningEngine

ToolManager

Vector Memory

Planner System

Learning Engine

📦 Requirements

Before running GcoreX you need the following:

Python

Python 3.10 or newer

Ollama

Download and install Ollama:

https://ollama.com
Model

Install the Mistral model:

ollama pull mistral
⚙️ Installation Guide
1️⃣ Clone the repository
git clone https://github.com/yourusername/GcoreX.git
cd GcoreX
2️⃣ Install Python dependencies
pip install colorama pyttsx3 requests

or if a requirements file exists:

pip install -r requirements.txt
3️⃣ Start Ollama

Make sure Ollama is running.

Example:

ollama serve
▶️ How to Run GcoreX

⚠️ Important

This AI is designed to run in the terminal / command line.

Do not run it through GUI launchers or by double-clicking the file.

Run it using:

python GcoreX.py

After launching, the AI will display a startup banner and wait for user input.

Example:

You: hello
GcoreX: Hello! How can I help you today?
🖥 Running in Terminal Only

GcoreX currently works as a CLI (Command Line Interface) AI.

✔ Run from terminal
✔ Works on Windows, Linux, and Mac

❌ Do not run through GUI launchers
❌ Do not double-click the file

Correct method:

python GcoreX.py
🧠 Available Commands

Inside the terminal you can use the following commands:

dev mode on
dev mode off
sys monitor
tool health
research <topic>
remember <text>
forget <text>
knowledge search <query>
goals
clear goals
auto <goal>
exit

These commands allow you to interact with internal systems such as memory, planner, and monitoring.

🖥 Tested On System

GcoreX has been tested on the following hardware configuration.

Laptop Configuration

CPU: AMD Ryzen 5 5500U
RAM: 8 GB
GPU: Integrated Radeon Graphics
OS: Windows 11
Python: 3.12
Model: Mistral (Ollama)

The system runs completely locally without requiring a dedicated GPU.

⚡ Performance

On the above system configuration:

Fast chat responses: ~1–3 seconds

Reasoning tasks: ~3–8 seconds

Autonomous tasks: depends on tool execution

Performance may vary depending on:

selected model

system resources

background processes

⚠️ Notes

Ollama must be running before starting GcoreX.

The default AI model used is Mistral.

Some tools may require internet access.

Memory files are automatically created during execution.

🚀 Future Improvements

Planned improvements include:

Web interface

Desktop GUI

Android version

Voice assistant support

Multi-agent collaboration

Expanded tool ecosystem

#it is in development phase so you my face bugs
