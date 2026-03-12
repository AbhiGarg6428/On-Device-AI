import os
import requests

name = "analyze_code"
description = "Analyze code files to explain purpose and identify issues"

def run(file_path):
    try:
        project_root = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        abs_path = os.path.abspath(file_path)
        if not abs_path.startswith(project_root):
            return f"Error: Access denied. Sandbox protection prevents reading files outside of {project_root}"
    except Exception as e:
        return f"Error resolving path: {e}"

    if not os.path.exists(file_path):
        return f"Error: File '{file_path}' not found."
    
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Truncate content to avoid exploding context limits
    content = content[:4000]

    try:
        res = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "mistral",
                "prompt": f"You are a Senior Software Engineer. Analyze the following code. Explain its purpose, identify any potential bugs, bugs, or security issues, and suggest improvements natively:\n\n{content}",
                "stream": False
            },
            timeout=45
        )
        return "Code Analysis:\n" + res.json().get("response", "No analysis generated.")
    except Exception as e:
        return f"LLM Error during analysis: {e}"
