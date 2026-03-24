# GcoreX AI - Getting Started Guide

GcoreX AI is a modular intelligent agent powered by Ollama and local LLMs. Follow this simple guide to set it up and run it on your machine.

## Prerequisites

1. **Python 3.10+**: Ensure Python is installed on your system.
2. **Ollama**: You must have Ollama installed to run the local language models (it uses `mistral` by default).
   - Download and install from: https://ollama.com/download
   - Once installed, it is recommended to pull the `mistral` model by running the following command in your terminal:
     `ollama pull mistral`

## Installation

### Method 1: Automated Script (Linux/Debian-based systems)
You can use the provided bash script to install both the required system packages and Python dependencies:
1. Open your terminal in the `GcoreX-AI` directory.
2. Make the script executable:
   `chmod +x install_deps.sh`
3. Run the script:
   `./install_deps.sh`

### Method 2: Manual Installation
If you prefer not to use the script or are on a different OS, install the Python libraries manually using pip:
1. Open your terminal in the `GcoreX-AI` directory.
2. Run the command:
   `pip install -r requirements.txt`

## Running GcoreX

Once dependencies and Ollama are installed, you can start the application!

1. Open your terminal in the `GcoreX-AI` directory.
2. Run the main script:
   `python3 GcoreX.py`
   (or `python GcoreX.py` depending on your setup)

### Important Notes:
- The script will automatically try to start the Ollama server and load the `mistral` model if it isn't already running.
- Ensure your microphone and sound are working correctly, as GcoreX has built-in text-to-speech functionality.
