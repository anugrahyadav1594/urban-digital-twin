import json

import httpx
from pydantic import BaseModel


class LLMClient:
    """Client for interacting with a local Ollama LLM."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen3:8b",
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str) -> str:
        """Generate a text response from the configured LLM."""

        response = httpx.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
            },
            timeout=self.timeout,
        )

        response.raise_for_status()

        data = response.json()

        return data["response"]

    def generate_structured(
        self,
        prompt: str,
        response_model: type[BaseModel],
    ) -> BaseModel:
        """Generate and validate structured JSON using Ollama's native format."""

        schema = response_model.model_json_schema()
        
        # Inject schema description and constraints into the prompt to guide simple JSON mode
        schema_instruction = (
            f"\n\nYou must respond with a JSON object that matches the structure of the schema below.\n"
            f"Do NOT return the schema definition itself. Return a JSON object with actual values representing the request details.\n"
            f"JSON Schema:\n"
            f"{json.dumps(schema, indent=2)}\n\n"
            f"Do not include any conversational filler, markdown formatting (like ```json), or preambles. "
            f"Return only the raw JSON object containing the extracted data."
        )
        full_prompt = prompt + schema_instruction

        response = httpx.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": full_prompt,
                "stream": False,
                "format": "json",
            },
            timeout=self.timeout,
        )

        response.raise_for_status()

        data = response.json()

        raw_response = data["response"].strip()

        parsed_data = json.loads(raw_response)

        return response_model.model_validate(parsed_data)

