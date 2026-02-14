"""GRACE AI Service — Local Ollama integration for explanations and rule suggestions."""

import httpx

from app.config import settings


class GraceService:
    """
    GRACE AI Assistant — communicates with local Ollama instance only.
    Never sends raw datasets; only receives summarized data.
    """

    def __init__(self):
        self.base_url = settings.ollama_base_url
        self.model = settings.ollama_model

    async def _query(self, prompt: str, system_prompt: str = "") -> str:
        """Send a prompt to Ollama and return the response text."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt or (
                "You are GRACE, the AI assistant for Apeiron Data Sentinel — "
                "a data validation and governance system for freight audit. "
                "Provide concise, actionable answers. "
                "Never ask the user to provide raw data externally."
            ),
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            return response.json().get("response", "")

    async def explain_failure(
        self, record_summary: str, rule_name: str, rule_description: str
    ) -> str:
        """Explain why a record failed validation."""
        prompt = (
            f"A record failed the validation rule '{rule_name}'.\n"
            f"Rule description: {rule_description}\n"
            f"Record summary: {record_summary}\n\n"
            "Explain clearly why this record failed and what the user should "
            "check or fix. Be specific and concise."
        )
        return await self._query(prompt)

    async def summarize_trends(self, validation_summary: dict) -> str:
        """Summarize validation trends from run results."""
        summary_text = "\n".join(
            f"- {k}: {v}" for k, v in validation_summary.items()
        )
        prompt = (
            f"Here is a validation run summary:\n{summary_text}\n\n"
            "Analyze these results and provide:\n"
            "1. Key patterns or concerns\n"
            "2. Areas that need attention\n"
            "3. Recommendations for improvement\n"
            "Be concise and actionable."
        )
        return await self._query(prompt)

    async def suggest_rule(self, natural_language: str) -> dict:
        """Convert natural language rule description into a structured rule JSON draft."""
        prompt = (
            f"Convert this natural language rule description into a JSON rule definition:\n"
            f'"{natural_language}"\n\n'
            "Return ONLY valid JSON with these fields:\n"
            "{\n"
            '  "name": "rule name",\n'
            '  "rule_type": "duplicate|match|existence|numeric_compare",\n'
            '  "primary_field": "column_name",\n'
            '  "secondary_field": "column_name or null",\n'
            '  "operator": "eq|ne|gt|lt|gte|lte|contains|in or null",\n'
            '  "tolerance": 0.0,\n'
            '  "severity": "error|warning"\n'
            "}\n"
            "Return ONLY the JSON, no explanation."
        )
        response = await self._query(prompt)

        # Try to parse the JSON from the response
        import json

        try:
            # Find JSON in the response (Ollama may include extra text)
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            pass

        return {"raw_response": response, "parse_error": True}

    async def is_available(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False


# Singleton instance
grace_service = GraceService()
