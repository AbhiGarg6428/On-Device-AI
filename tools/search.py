name = "search"
description = "Search Google for information"

def run(query):
    import urllib.parse
    import webbrowser
    url = f"https://www.google.com/search?q={urllib.parse.quote(str(query))}"
    webbrowser.open(url)
    return "Search opened in browser."
