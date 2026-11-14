import json
import os

from dotenv import load_dotenv

load_dotenv()


def ollama_backend(system: str, user: str, json_schema: dict | None = None) -> str:
    import ollama  # imported here, so other backends work without it

    response = ollama.chat(
        model=os.getenv("OLLAMA_MODEL", "qwen3.5:4b"),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        format=json_schema,  # None means ordinary free text
    )
    return response.message.content


def anthropic_backend(system: str, user: str, json_schema: dict | None = None) -> str:
    import anthropic  # needs: pip install anthropic, and ANTHROPIC_API_KEY in .env

    if json_schema is not None:
        system += (
            "\n\nReply with a single JSON object only, matching this JSON schema. "
            "No other text.\n" + json.dumps(json_schema)
        )
    client = anthropic.Anthropic()
    message = client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5"),
        max_tokens=1000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(block.text for block in message.content if block.type == "text")


BACKENDS = {"ollama": ollama_backend, "anthropic": anthropic_backend}


def get_backend():
    name = os.getenv("LLM_BACKEND", "ollama")
    try:
        return BACKENDS[name]
    except KeyError:
        raise ValueError(f"Unknown LLM_BACKEND '{name}'. Choose from: {sorted(BACKENDS)}")