import os
import sys
import psutil

def already_running():
    current = psutil.Process().pid
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        if proc.pid != current and 'python' in proc.name() and 'bot.py' in str(proc.cmdline()):
            return True
    return False

if already_running():
    print("⚠️ Bot already running, exiting duplicate instance.")
    sys.exit(0)
    sys.exit(0)
