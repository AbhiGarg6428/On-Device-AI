"""
UI Utilities for GcoreX terminal interface.
"""

from colorama import Fore, Style

def log_dev(module, message):
    """Prints a colored developer log."""
    colors = {
        "router":     Fore.CYAN,
        "validator":  Fore.YELLOW,
        "correction": Fore.MAGENTA,
        "tool":       Fore.BLUE,
        "reasoning":  Fore.LIGHTBLUE_EX,
        "planner":    Fore.LIGHTGREEN_EX,
        "error":      Fore.RED
    }
    color = colors.get(module, Fore.WHITE)
    print(color + f"[DEV-{module.upper()}] {message}" + Style.RESET_ALL)
