import os
import global_settings

user_preferences = """---
name: User Preferences
description: A markdown file to store user preferences, which can be read by the agent at the beginning of each session. When any new preferences are found, the agent should update this file.
---
"""

def init():
    working_directory = global_settings.working_directory
    if working_directory:
        working_directory = os.path.expanduser(working_directory)
        if not working_directory.endswith("/"):
            working_directory += "/"
        if not os.path.exists(working_directory):
            os.makedirs(working_directory)
        tmp = working_directory + "tmp/"
        if not os.path.exists(tmp):
            os.makedirs(tmp)
        sop = working_directory + "sop/" 
        if not os.path.exists(sop):
            os.makedirs(sop)
        work_logs = working_directory + "work_logs/" 
        if not os.path.exists(work_logs):
            os.makedirs(work_logs)
        user_pref = working_directory + "user_preferences.md"
        if not os.path.exists(user_pref):
            with open(user_pref, "w") as f:
                f.write(user_preferences)