import re
import json
import functools
import browser
import global_settings
import memory_management
from pathlib import Path
from datetime import datetime
from client.gemini import GeminiClient

gemini_cli = GeminiClient(global_settings)
TOOLS = { }
def tool_handler(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        return result
    doc_dict = json.loads(func.__doc__) if func.__doc__ else {}
    doc_dict["name"] = func.__name__
    TOOLS[func.__name__] = {
        "doc": doc_dict,
        "func": wrapper,
    }
    return wrapper

def get_tool_definitions_claude_style():
    return [tool['doc'] for tool in TOOLS.values()]

def get_tool_definitions_openai_style():
    tool_definitions = []
    for tool in TOOLS.values():
        doc = tool['doc']
        doc['input_schema']['additionalProperties'] = False
        tool_definitions.append({
            "type": "function",
            "name": doc["name"],
            "description": doc.get("description", ""),
            "parameters": doc.get("input_schema", {})
        })
    return tool_definitions

def run_tool(tool_name, tool_input):
    handler = TOOLS.get(tool_name)
    if handler is None:
        return f"Error: No handler found for tool '{tool_name}'"
    return handler['func'](tool_input)

@tool_handler
def glob(tool_input):
    """ {
        "description": "List files in a specified directory",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory path, e.g., ~/Downloads"
                },
                "pattern": {
                    "type": "string",
                    "description": "File name matching pattern, supports wildcards, e.g., *.txt"
                },
                "with_details": {
                    "type": "boolean",
                    "description": "Whether to include file details such as size and creation date, default is false"
                }
            },
            "required": ["directory", "pattern", "with_details"]
        }
    } """
    directory = tool_input.get("directory")
    pattern = tool_input.get("pattern", "*")
    with_details = tool_input.get("with_details", False)
    p = Path(directory).expanduser()
    l = []
    for file_path in p.glob(pattern):
        stats = file_path.stat()
        size = stats.st_size  # In bytes
        create_date = datetime.fromtimestamp(stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
        update_date = datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        fp = str(file_path).replace(str(p) + "/", "")
        if with_details:
            l.append(f'{fp} | {"file" if file_path.is_file() else "folder"} | created at {create_date} | last updated at {update_date} | size {size} bytes')
        else:
            l.append(f'{fp} | {"file" if file_path.is_file() else "folder"}')
    return "\n".join(l)

@tool_handler
def mkdir(tool_input):
    """ {
        "description": "Create a new directory",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory path to create, e.g., ~/Documents/NewFolder"
                }
            },
            "required": ["directory"]
        }
    } """
    directory = tool_input.get("directory")
    p = Path(directory).expanduser().resolve()
    workdir = global_settings.working_directory
    if workdir is None:
        return "Error: No working directory set in settings."
    workdir = Path(workdir).expanduser().resolve()
    if not p.is_relative_to(workdir):
        return f"Error: Folder path {p} is outside of the working directory {workdir}. You are only permitted to create folders within the working directory."

    try:
        p.mkdir(parents=True, exist_ok=True)
        return f"Successfully created directory: {p}"
    except Exception as e:
        return f"Error creating directory: {str(e)}"

@tool_handler
def tail(tool_input):
    """ {
        "description": "Read the last few lines of a specified file",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "File path, e.g., ~/Documents/notes.txt"
                },
                "lines": {
                    "type": "integer",
                    "description": "Number of lines to read, default is 10"
                }
            },
            "required": ["file_path", "lines"]
        }
    } """
    file_path = tool_input.get("file_path")
    lines = tool_input.get("lines", 10)
    try:
        file_path = Path(file_path).expanduser()
        with open(file_path, 'r') as f:
            content = f.readlines()[-lines:]
        return "\n".join(content)
    except Exception as e:
        return f"Error reading file: {str(e)}"

@tool_handler
def count_lines(tool_input):
    """ {
        "description": "Count the number of lines in a specified file",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "File path, e.g., ~/Documents/notes.txt"
                }
            },
            "required": ["file_path"]
        }
    } """
    file_path = tool_input.get("file_path")
    try:
        file_path = Path(file_path).expanduser()
        with open(file_path, 'r') as f:
            line_count = sum(1 for _ in f)
        return f"{file_path} has {line_count} lines."
    except Exception as e:
        return f"Error reading file: {str(e)}"

@tool_handler
def grep(tool_input):
    """ {
        "description": "Search for matching lines in a specified file",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "File path, e.g., ~/Documents/notes.txt"
                },
                "pattern": {
                    "type": "string",
                    "description": "Text or regular expression to search for"
                },
                "show_line_num": {
                    "type": "boolean",
                    "description": "Whether to show line numbers in the results, default is true"
                }          
            },
            "required": ["file_path", "pattern", "show_line_num"]
        }
    } """
    file_path = tool_input.get("file_path")
    pattern = tool_input.get("pattern")
    show_line_num = tool_input.get("show_line_num", True)

    regex = re.compile(pattern)
    results = []
    try:
        file_path = Path(file_path).expanduser()
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f, 1):
                if regex.search(line):
                    line_content = line.strip()
                    prefix = f"{file_path}:{i}:" if show_line_num else f"{file_path}:"
                    results.append(f"{prefix} {line_content}")
        return "\n".join(results)
    except Exception as e:
        return f"Error reading file: {str(e)}"

@tool_handler
def read_file(tool_input):
    """ {
        "description": "Read the content of a specified file",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "File path, e.g., ~/Documents/notes.txt"
                },
                "lines": {
                    "type": "integer",
                    "description": "Number of lines to read from the beginning of the file, default is 10"
                },
                "offset": {
                    "type": "integer",
                    "description": "Number of lines to skip from the beginning of the file, default is 0"
                }
            },
            "required": ["file_path", "lines", "offset"]
        }
    } """
    file_path = tool_input.get("file_path")
    lines = tool_input.get("lines", 10)
    offset = tool_input.get("offset", 0)
    try:
        file_path = Path(file_path).expanduser()
        with open(file_path, 'r') as f:
            for _ in range(offset):
                next(f, None)
            return "".join([next(f, "") for _ in range(lines)])
    except Exception as e:
        return f"Error reading file: {str(e)}"

@tool_handler
def write_file(tool_input):
    """ {
        "description": "Write content to the specified file",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "File path, e.g., ~/Documents/notes.txt"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                },
                "append": {
                    "type": "boolean",
                    "description": "Whether to append to the file, default is false"
                }
            },
            "required": ["file_path", "content", "append"]
        }
    } """
    file_path = tool_input.get("file_path")
    content = tool_input.get("content")
    append = tool_input.get("append", False)
    try:
        file_path = Path(file_path).expanduser().resolve()
        workdir = global_settings.working_directory
        if workdir is None:
            return "Error: No working directory set in settings."
        workdir = Path(workdir).expanduser().resolve()
        if not file_path.is_relative_to(workdir):
            return f"Error: File path {file_path} is outside of the working directory {workdir}. You are only permitted to write files within the working directory."

        mode = 'a' if append else 'w'
        with open(file_path, mode) as f:
            f.write(content)
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Error writing to file: {str(e)}"
    
@tool_handler
def replace_in_file(tool_input):
    """ {
        "description": "Replace content in a file",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "File path, e.g., ~/Documents/notes.txt"
                },
                "search": {
                    "type": "string",
                    "description": "Text or regular expression to search for"
                },
                "replace": {
                    "type": "string",
                    "description": "Text to replace with"
                },
                "max_replacements": {
                    "type": "integer",
                    "description": "Maximum number of replacements, default is all"
                }
            },
            "required": ["file_path", "search", "replace", "max_replacements"]
        }
    } """
    file_path = tool_input.get("file_path")
    search = tool_input.get("search")
    replace = tool_input.get("replace")
    max_replacements = tool_input.get("max_replacements", -1)

    try:
        file_path = Path(file_path).expanduser().resolve()
        workdir = global_settings.working_directory
        if workdir is None:
            return "Error: No working directory set in settings."
        workdir = Path(workdir).expanduser().resolve()
        if not file_path.is_relative_to(workdir):
            return f"Error: File path {file_path} is outside of the working directory {workdir}. You are only permitted to edit files within the working directory."

        with open(file_path, 'r') as f:
            content = f.read()
        new_content, num_replacements = re.subn(search, replace, content, count=max_replacements)
        with open(file_path, 'w') as f:
            f.write(new_content)
        return f"Replaced {num_replacements} occurrences in {file_path}"
    except Exception as e:
        return f"Error replacing content in file: {str(e)}"

@tool_handler
def ask_gemini(tool_input):
    """ {
        "description": "Ask the Gemini a question. Google Search is integrated in Gemini. You can use Gemini as a search engine. Please describe your question as specifically and clearly as possible. ",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to ask"
                }
            },
            "required": ["question"]
        }
    } """
    question = tool_input.get("question") + "\nFor any URLs in the answer, please double check their validity."
    try:
        # model = "gemini-2.5-flash"
        model = "gemini-3-flash-preview"
        answer = gemini_cli.generate(model, question, enable_search=True)
        return answer
    except Exception as e:
        return f"Error asking Gemini: {str(e)}"

@tool_handler
def open_web_page(tool_input):
    """ {
        "description": "Use a browser to open a specified URL and retrieve the web page content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL of the web page to open"
                }
            },
            "required": ["url"]
        }
    } """
    url = tool_input.get("url")
    url_pattern = re.compile(r'^(https?://)?([a-zA-Z0-9.-]+)(:[0-9]+)?(/.*)?$')
    if not url_pattern.match(url):
        return f"Error: Invalid URL '{url}'. Reminder: Don't use open_web_page tool to open local files."

    workdir = global_settings.working_directory
    page_id, file_path, file_path2  = browser.open_url(url, workdir)
    summary = browser.summarize_page(page_id)
    return f"Opened {url} in browser with page ID {page_id}.\nRaw html content saved to {file_path}.\nCleaned html content saved to {file_path2}.\nPage summary: {summary}"

@tool_handler
def login_web_page(tool_input):
    """ {
        "description": "This is a powerful tool that can login to an opened web page. This tool have access to user's credentials for different websites, only page id is needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "The ID of the web page, returned by the open_web_page tool"
                }
            },
            "required": ["page_id"]
        }
    } """
    page_id = tool_input.get("page_id")
    success, msg = browser.login_page(page_id)
    if success:
        return f"Successfully logged in to page {page_id}"
    else:
        return f"Error: Failed to log in to page {page_id}: {msg}"

@tool_handler
def download_file(tool_input):
    """ {
        "description": "Download a file or picture from a specified URL and save to local.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL of the file to download"
                },
                "save_folder": {
                    "type": "string",
                    "description": "The local folder to save the downloaded file, e.g., ~/Downloads"
                },                
                "file_name": {
                    "type": "string",
                    "description": "The name to save the downloaded file as, e.g., picture.jpg."
                }
            },
            "required": ["url", "save_folder", "file_name"]
        }
    } """
    url = tool_input.get("url")
    save_folder = tool_input.get("save_folder")
    file_name = tool_input.get("file_name")
    file_path = browser.download_file(url, save_folder, file_name)
    if file_path:
        return f"Successfully downloaded file from {url} to {file_path}"
    else:
        return f"Error: Failed to download file from {url}"

@tool_handler
def record_fact_to_memory(tool_input):
    """ {
        "description": "Record a fact to memory. This is a tool for recording important information that may be useful for future questions. The recorded facts will be stored in a long-term memory system and can be retrieved later when needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fact_category": {
                    "type": "string", 
                    "description": "The category of the fact to be recorded, Value must be one of user_preference, agent_identity, common_fact."
                },
                "content": {
                    "type": "string", 
                    "description": "detailed content of the fact to be recorded"
                },
                "confidence": {
                    "type": "integer", 
                    "description": "confidence level, value from 1 to 10, with 10 being the most confident, default is 5"
                }
            },
            "required": ["fact_category", "content", "confidence"]
        }
    } """
    fact_category = tool_input.get("fact_category")
    content = tool_input.get("content")
    confidence = tool_input.get("confidence")
    memory_management.record_memory(fact_category, content, confidence)
    return f"Successfully recorded fact to memory."

@tool_handler
def search_memory(tool_input):
    """ {
        "description": "Search for relevant facts in memory based on a query. This tool allows you to retrieve information that has been previously recorded in the long-term memory system. You can use this tool to find relevant facts that may help answer a question or provide context for a task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string", 
                    "description": "The search query to find relevant facts in memory"
                }
            },
            "required": ["query"]
        }
    } """
    query = tool_input.get("query")
    results = memory_management.query_memory(query)
    if results:
        return "Found the following relevant facts in memory:\n" + "\n".join(f"{i}. {fact}" for i, fact in enumerate(results, 1))
    else:
        return "No relevant facts found in memory."
