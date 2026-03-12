import os

name = "read_file"
description = "Reads the content of .txt, .py, or .pdf files."

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
    
    if ext in ['.txt', '.py', '.md', '.json', '.csv']:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return f"File contents of {file_path}:\n{content}"
        except Exception as e:
            return f"Error reading text file: {e}"
            
    elif ext == '.pdf':
        try:
            import PyPDF2
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                content = ""
                for page in reader.pages:
                    content += page.extract_text() + "\n"
            return f"PDF contents of {file_path}:\n{content}"
        except ImportError:
            return "Error: PyPDF2 is not installed. Please run 'pip install PyPDF2' to read PDFs."
        except Exception as e:
            return f"Error reading PDF file: {e}"
            
    else:
        return f"Error: Unsupported file extension '{ext}'. Only .txt, .py, and .pdf are supported."
