# 🦀 PyClaw
PyClaw is a Python-based personal AI assistant that runs locally on your computer to automate your workflows and handle tasks autonomously.

![](/architecture.png)

## 🚀 Getting Started
1. Clone the repository:

```sh
git clone git@github.com:istoney/PyClaw.git
```

2. Configure settings:

Rename `settings_example.json` to `settings.json` and replace the placeholders with your actual configurations.

Currently, two LLM model provider supported, openrouter and anthropic(any model provider support anthropic SDK is supported). When model provider is set, corresponding api key must also be set. 

3. Install dependencies:

```sh
pip install -r requirements.txt
```

4. Run the assistant:

```sh
python main.py
```

## ✨ Key Features

### 📱 Telegram Integration

PyClaw is fully integrated with Telegram, allowing you to send instructions remotely. Whether you're away from your desk or on the go, your assistant is just one message away.

### 🌐 Web Browser Automation

Powered by Playwright, PyClaw can navigate the web just like a human. It can open pages, interpret content, extract specific data, and handle file downloads seamlessly.

### 🛡️ Secure File Operations

Security is a priority. While PyClaw can read files across your system, it is restricted to writing or editing files only within its designated workspace(configurable, ~ by defualt).  This "sandbox" approach ensures your sensitive system files remain protected.

### 📉 Context Compression

A token threshold can be configured; once reached, PyClaw automatically compresses the chat history into a concise summary to maintain performance and reduce costs.

### 💾 Long-term Memory

PyClaw maintains a persistent memory system:

- User Preferences(user_preferences.md): Remembers how user like things done—your favorite programming languages, preferred output formats, or specific notification settings. The user_preferences.md locate under root of working folder, user can review and modify it by self.
- Agent Identity (soul.md): Defines the "personality" and ethical boundaries of assistant, ensuring consistent behavior across different tasks. The soul.md locate under root of working folder, user can review and modify it by self.
- Common Facts: PyClaw leverage chromadb to manage common facts memory. And relevant facts will be loaded into context automatically.

### 🧠 Self-Evolving SOPs (Standard Operating Procedures)

PyClaw use a prompt "hook" to detect if task done. After completing a task complete, it will be asked to summarize the process into an SOP. When user give new task, it will automatically check if SOP exist and follow it.

- Efficiency: For recurring tasks, PyClaw follows the established SOP to save time.

- Continuous Learning: SOPs are dynamically updated as PyClaw gains new insights, making it smarter with every execution.
