import os
import requests

name = "summarize_file"
description = "Summarize the content of a text or document file"

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
    
    ext = os.path.splitext(file_path)[1].lower()
    content = ""
    
    if ext in ['.txt', '.py', '.md', '.json', '.csv']:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    elif ext == '.pdf':
        try:
            import PyPDF2
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                content = "".join([page.extract_text() + "\n" for page in reader.pages])
        except ImportError:
            return "Error: PyPDF2 is not installed."
        except Exception as e:
            return f"Error reading PDF: {e}"
    else:
        return f"Error: Unsupported format {ext}."

    # Truncate content to avoid exploding context limits
    content = content[:3000]

    try:
        res = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "mistral",
                "prompt": f"Please provide a concise but highly detailed summary of the following file content:\n\n{content}",
                "stream": False
            },
            timeout=45
        )
        return "Summary of file:\n" + res.json().get("response", "No summary generated.")
    except Exception as e:
        return f"LLM Error during summarization: {e}"
