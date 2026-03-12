import os
import urllib.parse
import webbrowser
import time
import subprocess

name = "open_app"
description = "Open applications, folders, or system locations"

def run(value):
    try:
        query = str(value).strip().lower()
        if query.startswith("open "):
            query = query[5:].strip()
            
        if not query:
            return "Please specify what you want to open."
            
        # 1. Combined Commands (e.g., "open chrome and search epic")
        if " and search " in query:
            parts = query.split(" and search ", 1)
            app_req = parts[0].strip()
            search_query = parts[1].strip()
            
            url = f"https://www.google.com/search?q={urllib.parse.quote(search_query)}"
            try:
                # Try launching via Chrome specifically if requested
                if "chrome" in app_req:
                    try:
                        webbrowser.get('chrome').open(url)
                    except webbrowser.Error:
                        try:
                            # Fallback to direct shell execution for Chrome on Windows
                            subprocess.Popen(['start', 'chrome', url], shell=True)
                        except Exception:
                            webbrowser.open(url)
                else:
                    webbrowser.open(url)
                
                app_disp = "Chrome" if "chrome" in app_req else app_req.title()
                return f"Opening {app_disp} and searching {search_query}."
            except Exception as e:
                return f"Could not perform search: {str(e)}"
                
        # 2. Windows specific locations ("this pc" / "my computer")
        if query in ["this pc", "my computer", "this pc folder", "my computer folder"]:
            try:
                subprocess.Popen('explorer shell:MyComputerFolder', shell=True)
                return "Opening This PC."
            except Exception:
                try:
                    os.startfile("C:\\")
                    return "Opening This PC."
                except Exception as e:
                    return f"Failed to open This PC: {str(e)}"

        # 3. System Folders
        system_folders = {
            "downloads": "Downloads",
            "desktop": "Desktop",
            "documents": "Documents",
            "pictures": "Pictures",
            "videos": "Videos"
        }
        
        for key, folder_name in system_folders.items():
            if query == key or query == f"{key} folder":
                user_home = os.path.expanduser("~")
                folder_path = os.path.join(user_home, folder_name)
                if os.path.exists(folder_path):
                    try:
                        os.startfile(folder_path)
                        return f"Opening {folder_name} folder."
                    except Exception as e:
                        return f"Failed to open {folder_name} folder: {str(e)}"

        # 4. Common Applications (Direct mapping)
        known_apps = {
            "chrome": "chrome.exe",
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "paint": "mspaint.exe",
            "word": "winword.exe",
            "excel": "excel.exe",
            "powerpoint": "powerpnt.exe",
            "cmd": "cmd.exe",
            "command prompt": "cmd.exe",
            "explorer": "explorer.exe",
            "file explorer": "explorer.exe"
        }
        
        app_key = query.replace(" app", "").replace(" program", "").strip()
        if app_key in known_apps:
            try:
                os.startfile(known_apps[app_key])
                return f"Opening {app_key.title()}."
            except Exception:
                pass

        # 5. Fuzzy Folder Search
        is_folder_query = "folder" in query
        search_target = query.replace(" folder", "").replace("folder", "").strip()
        
        if is_folder_query and search_target:
            user_home = os.path.expanduser("~")
            queue = [(user_home, 0)]
            max_depth = 4
            skip_dirs = {".ms-ad", "appdata", "application data", "local settings", "ntuser", ".cache", ".config"}
            
            while queue:
                current_dir, depth = queue.pop(0)
                if depth > max_depth:
                    continue
                    
                try:
                    with os.scandir(current_dir) as entries:
                        for entry in entries:
                            if entry.is_dir(follow_symlinks=False):
                                entry_lower = entry.name.lower()
                                if entry_lower.startswith('.') or entry_lower in skip_dirs:
                                    continue
                                    
                                if search_target in entry_lower:
                                    try:
                                        os.startfile(entry.path)
                                        return f"Opening {entry.name} folder."
                                    except Exception:
                                        pass
                                        
                                queue.append((entry.path, depth + 1))
                except (PermissionError, FileNotFoundError, OSError):
                    pass

        # 6. Start Menu Application Search (Fallback)
        username = os.environ.get("USERNAME", "")
        start_menu_dirs = [
            r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"
        ]
        if username:
            start_menu_dirs.append(fr"C:\Users\{username}\AppData\Roaming\Microsoft\Windows\Start Menu\Programs")

        for sm_dir in start_menu_dirs:
            if not os.path.exists(sm_dir):
                continue
            try:
                for root, _, files in os.walk(sm_dir):
                    for file in files:
                        if file.lower().endswith(".lnk") or file.lower().endswith(".exe"):
                            name_without_ext = os.path.splitext(file)[0].lower()
                            if search_target in name_without_ext:
                                path = os.path.join(root, file)
                                try:
                                    os.startfile(path)
                                    return f"Opening {os.path.splitext(file)[0]}."
                                except Exception:
                                    pass
            except Exception:
                pass

        # 7. Smart Application Launch (Direct Command fallback)
        if search_target:
            try:
                process = subprocess.Popen(
                    search_target,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                time.sleep(0.5)
                if process.poll() is None or process.returncode == 0:
                    return f"Opening {search_target.title()}."
            except Exception:
                pass

        return f"I could not find '{query}'."

    except Exception as e:
        return f"An error occurred while trying to open: {str(e)}"
