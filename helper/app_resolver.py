import os

def resolve_app(value):
    """Resolves human readable app names to system commands or paths."""
    if not value:
        return ""
    v = value.lower()
    
    if "chrome" in v:
        return "chrome"
    elif "this pc" in v or "my computer" in v:
        return "explorer shell:MyComputerFolder"
    elif "desktop" in v:
        return os.path.expanduser("~/Desktop")
    elif "downloads" in v:
        return os.path.expanduser("~/Downloads")
    elif "documents" in v:
        return os.path.expanduser("~/Documents")
    elif "explorer" in v or "file manager" in v:
        return "explorer"
        
    return value
