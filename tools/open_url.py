name = "open_url"
description = "Opens a specific URL exactly as provided in the default browser."

def run(url):
    import webbrowser
    webbrowser.open(str(url))
    return f"Opened URL: {url}"
