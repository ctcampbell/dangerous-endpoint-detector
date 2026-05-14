import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

import anthropic

logger = logging.getLogger(__name__)

SOURCE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".php",
    ".rb", ".go", ".cs", ".cpp", ".c", ".h",
}

ENDPOINT_PATTERNS = [
    r'@app\.(get|post|put|patch|delete)\s*\(["\']([^"\']+)',     # Flask/FastAPI
    r'@(Get|Post|Put|Patch|Delete)Mapping\s*\(["\']([^"\']+)',   # Spring
    r'router\.(get|post|put|patch|delete)\s*\(["\']([^"\']+)',   # Express.js
    r'Route::?(get|post|put|patch|delete)\s*\(["\']([^"\']+)',   # Laravel
    r'def\s+(\w+).*@route',                                       # Flask function routes
    r'app\.(get|post|put|patch|delete)\(["\']([^"\']+)',         # Express/Koa
]

ACTION_LABELS = {
    "login": "Logs user in",
    "logout": "Logs user out",
    "password_change": "Changes/deletes user password",
    "permission_change": "Changes user permissions",
    "dangerous_upsert": "Dangerous upsert/overwrite operation",
}


@dataclass
class EndpointResult:
    file_path: str
    endpoint: str
    line_number: int
    dangerous_action: str
    confidence: str
    explanation: str

    def to_dict(self) -> Dict:
        return {
            "file_path": self.file_path,
            "endpoint": self.endpoint,
            "line_number": self.line_number,
            "dangerous_action": self.dangerous_action,
            "confidence": self.confidence,
            "explanation": self.explanation,
        }


def extract_endpoints_from_code(code: str, file_path: str = "unknown") -> List[Dict]:
    """Extract potential API endpoints from code with line numbers."""
    endpoints: List[Dict] = []
    lines = code.split("\n")

    for i, line in enumerate(lines, 1):
        for pattern in ENDPOINT_PATTERNS:
            for match in re.finditer(pattern, line, re.IGNORECASE):
                start = max(0, i - 5)
                end = min(len(lines), i + 30)
                context = "\n".join(lines[start:end])
                endpoint_path = match.group(2) if len(match.groups()) > 1 else match.group(1)
                endpoints.append({
                    "file_path": file_path,
                    "endpoint": endpoint_path,
                    "line_number": i,
                    "context": context,
                })
    return endpoints


async def analyze_endpoint_with_llm(
    endpoint_data: Dict,
    client: anthropic.AsyncAnthropic,
    model: str = "claude-sonnet-4-6",
    semaphore: Optional[asyncio.Semaphore] = None,
) -> Optional[EndpointResult]:
    """Use Claude to analyze if an endpoint performs dangerous actions."""
    prompt = f"""Analyze this API endpoint code to determine if it performs any of these dangerous actions:

1. Logs a user IN (login, sign in, authentication, session creation, token generation, etc.)
2. Logs a user OUT (logout, sign out, session termination, revoke tokens, etc.)
3. Changes or deletes a user password (password update, password reset, password deletion, etc.)
4. Changes user permissions or roles (permission updates, role changes, access control modifications, etc.)
5. Dangerous upsert/overwrite operations (creates or updates user accounts where existing user data like passwords could be accidentally overwritten, blind PUT operations that replace entire user objects, merge operations that don't properly validate existing data, etc.)

Endpoint: {endpoint_data['endpoint']}
Code Context:
```
{endpoint_data['context']}
```

Respond with a JSON object in this exact format:
{{
  "is_dangerous": true/false,
  "action": "login" | "logout" | "password_change" | "permission_change" | "dangerous_upsert" | "none",
  "confidence": "high" | "medium" | "low",
  "explanation": "Brief explanation of why this endpoint is or isn't dangerous"
}}

Only respond with the JSON object, nothing else."""

    async def _call():
        return await client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

    try:
        if semaphore is not None:
            async with semaphore:
                message = await _call()
        else:
            message = await _call()

        response_text = message.content[0].text.strip()
        if response_text.startswith("```"):
            response_text = re.sub(r"^```json?\s*|\s*```$", "", response_text, flags=re.MULTILINE)
        result = json.loads(response_text)

        if not result.get("is_dangerous", False):
            return None

        return EndpointResult(
            file_path=endpoint_data.get("file_path", "unknown"),
            endpoint=endpoint_data["endpoint"],
            line_number=endpoint_data["line_number"],
            dangerous_action=ACTION_LABELS.get(result["action"], result["action"]),
            confidence=result["confidence"],
            explanation=result["explanation"],
        )

    except Exception as e:
        logger.error("Error analyzing endpoint %s: %s", endpoint_data.get("endpoint"), e)
        return None
