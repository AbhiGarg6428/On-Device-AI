import os
import pyautogui


def control_pc(command):

    command = command.lower()

    if command.startswith("open "):

        app = command.replace("open ", "")
        os.system(f"start {app}")
        return f"Opening {app}"

    elif command.startswith("close "):

        app = command.replace("close ", "")
        os.system(f"taskkill /im {app}.exe /f")
        return f"Closing {app}"

    elif "shutdown" in command:

        os.system("shutdown /s /t 1")
        return "Shutting down"

    elif "restart" in command:

        os.system("shutdown /r /t 1")
        return "Restarting"

    elif "lock" in command:

        os.system("rundll32.exe user32.dll,LockWorkStation")
        return "Locking system"

    elif "move mouse up" in command:

        pyautogui.moveRel(0, -100)
        return "Moving mouse up"

    elif "move mouse down" in command:

        pyautogui.moveRel(0, 100)
        return "Moving mouse down"

    elif "move mouse left" in command:

        pyautogui.moveRel(-100, 0)
        return "Moving mouse left"

    elif "move mouse right" in command:

        pyautogui.moveRel(100, 0)
        return "Moving mouse right"

    elif "click" in command:

        pyautogui.click()
        return "Clicking"

    elif command.startswith("type "):

        text = command.replace("type ", "")
        pyautogui.write(text)
        return f"Typing {text}"

    elif "press enter" in command:

        pyautogui.press("enter")
        return "Pressed enter"

    return None