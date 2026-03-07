import json
import uuid
import os
import chromadb
import anthropic
import global_settings
from rich import print

piclaw_memory = None

def get_memory_collection():
    global piclaw_memory
    if piclaw_memory is None:
        mem_path = global_settings.working_directory + ".memory/"
        mem_path = os.path.expanduser(mem_path)
        client = chromadb.PersistentClient(path=mem_path)
        piclaw_memory = client.get_or_create_collection(name="piclaw_memory")
    return piclaw_memory

def record_memory(category, content, confidence_level):
    print(f"[blue]Recording memory - Category: {category}, Content: {content}, Confidence Level: {confidence_level}[/blue]")

    if category == 'user_preference':
        update_user_preference(content)
        # TODO reload user preferences
        return "Record user preference to memory successfully."
    if category == 'agent_identity':
        update_agent_identity(content)
        # TODO reload agent identity
        return "Record agent identity to memory successfully."
    # For other categories, we store them in the vector database
    record_common_fact(content, confidence_level)
    return "Record common fact to memory successfully."

def query_memory(query, n_results=5):
    return get_memory_collection().query(
        query_texts=[query],
        n_results=n_results,
        include=["metadatas", "documents"]
    )

def _llm_complete(prompt):
    if global_settings.model_provider == "openrouter":
        from client.openrouter import OpenRouterClient
        client = OpenRouterClient(global_settings)
        response = client.complete(
            model=global_settings.openrouter_model,
            messages=[{"role": "system", "content": prompt}]
        )
        messages = [chunk for chunk in response['output'] if chunk['type'] == 'message']
        if messages:
            return messages[0]['content'][0]['text']
    elif global_settings.model_provider == "anthropic":
        llm_client = anthropic.Anthropic(
            api_key=global_settings.anthropic_api_key,
            base_url=global_settings.anthropic_base_url
        )
        response = llm_client.complete(
            model=global_settings.anthropic_model,
            messages=[{"role": "system", "content": prompt}]
        )
        messages = [block for block in response.content if block.type == 'text']
        if messages:
            return messages[0].text
    return None


user_preferences_prompt = """You are a memory management system for an autonomous agent. Your task is to update the user's preferences based on new information.
Below is the existing user preferences:
```
{existing_preferences}
```

Here is the new information to update the preferences:
```
{update}
```

Now update the user preferences by incorporating the new information. If the new information contradicts existing preferences, prioritize the new information. If it adds to existing preferences, integrate it seamlessly. Output the updated user preferences in markdown format without any explanations. Keep the user preferences concise.
"""

def update_user_preference(update):
    file_path = global_settings.working_directory + "user_preferences.md"
    file_path = os.path.expanduser(file_path)
    with open(file_path, "r") as f:
        existing_preferences = f.read()
    updated_preferences = _llm_complete(user_preferences_prompt.format(existing_preferences=existing_preferences, update=update))
    with open(file_path, "w") as f:
        f.write(updated_preferences)


agent_identity_prompt = """You are a memory management system for an autonomous agent. Your task is to update the agent's core identity and guiding principles based on new information.
Below is the existing agent identity:
```
{existing_soul}
```
Here is the new information to update the agent's identity:
```
{update}
```
Now update the agent's identity by incorporating the new information. If the new information contradicts existing identity, prioritize the new information. If it adds to existing identity, integrate it seamlessly. Output the updated agent identity in markdown format without any explanations. Keep the agent identity concise.
"""

def update_agent_identity(update):
    file_path = global_settings.working_directory + "soul.md"
    file_path = os.path.expanduser(file_path)
    with open(file_path, "r") as f:
        existing_soul = f.read()
    updated_soul = _llm_complete(agent_identity_prompt.format(existing_soul=existing_soul, update=update))
    with open(file_path, "w") as f:
        f.write(updated_soul)


fact_compare_prompt = """# Role
You are a high-precision "Long-Term Memory Management Engine." Your mission is to analyze the relationship between new information and existing memories to ensure the accuracy and timeliness of the knowledge base.

# Context
- Old Fact: {old_fact}
- New Fact: {new_fact}

# Logic & Rules
Please categorize and judge the relationship based on the following logic:

1. **CONFLICT (Mutual Exclusion/Overwrite)**: 
   - Definition: The new and old information describe the same attribute of the same entity, but with different values.
   - Examples: Old "Path is /tmp" vs. New "Path changed to /home"; Old "Age 25" vs. New "Just turned 26."
   - Action: Use the new information to completely replace the old information.

2. **INCREMENT (Additive/Coexistence)**: 
   - Definition: The new and old information describe different dimensions of the same person or thing, or involve "cumulative" hobbies/skills.
   - Examples: Old "Likes Python" vs. New "Started learning Rust too"; Old "Has a cat" vs. New "Just adopted a dog."
   - Action: Retain the old memory and add the new information as an additional entry.

3. **REDUNDANT (Redundancy/Ignore)**:
   - Definition: The new information is synonymous with the old memory, or the effective information in the new input is less than or equal to the existing memory.
   - Action: Maintain the status quo; do no perform any operation.

# Output Format (JSON ONLY)
Please output strictly in the following JSON format without any explanatory text:
{{
  "decision": "CONFLICT" | "INCREMENT" | "REDUNDANT",
  "reason": "A brief explanation of the judgment",
  "updated_content": "If the decision is CONFLICT, provide the updated/fused description; otherwise, leave empty"
}}
"""

def record_common_fact(content, confidence_level):
    results = get_memory_collection().query(
        query_texts=[content],
        n_results=1,
        include=["metadatas", "documents"]
    )
    if results and results['documents'] and results['documents'][0]:
        existing_fact = results['documents'][0][0]
        existing_id = results['ids'][0][0]
        prompt = fact_compare_prompt.format(old_fact=existing_fact, new_fact=content)
        comparison_result = _llm_complete(prompt)
        comparison_result = json.loads(comparison_result)
        decision = comparison_result.get("decision")
        if decision == "CONFLICT":
            updated_content = comparison_result.get("updated_content")
            get_memory_collection().update(
                ids=[existing_id],
                documents=[updated_content],
                metadatas=[{"confidence_level": confidence_level}]
            )
            return
        if decision == "REDUNDANT":
            return
    doc_id = str(uuid.uuid4())
    get_memory_collection().add(
        ids=[doc_id],
        documents=[content],
        metadatas=[{"confidence_level": confidence_level}]
    )
