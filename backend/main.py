from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic
import os
import re
from typing import List, Dict
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(dotenv_path="../.env")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    code: str
    file_path: str = "unknown"

class FileInput(BaseModel):
    name: str
    content: str

class AnalyzeBatchRequest(BaseModel):
    files: List[FileInput]

class EndpointResult(BaseModel):
    endpoint: str
    line_number: int
    dangerous_action: str
    confidence: str
    explanation: str

class AnalyzeResponse(BaseModel):
    results: List[EndpointResult]
    total_endpoints_analyzed: int

class FileResult(BaseModel):
    file_path: str
    results: List[EndpointResult]
    total_endpoints_analyzed: int

class AnalyzeBatchResponse(BaseModel):
    files: List[FileResult]
    total_files_analyzed: int
    total_endpoints_analyzed: int
    total_dangerous_endpoints: int

def extract_endpoints_from_code(code: str) -> List[Dict[str, any]]:
    """Extract potential API endpoints from code with line numbers"""
    endpoints = []
    lines = code.split('\n')

    # Common patterns for API endpoints across languages
    patterns = [
        r'@app\.(get|post|put|patch|delete)\s*\(["\']([^"\']+)',  # Flask/FastAPI
        r'@(Get|Post|Put|Patch|Delete)Mapping\s*\(["\']([^"\']+)',  # Spring
        r'router\.(get|post|put|patch|delete)\s*\(["\']([^"\']+)',  # Express.js
        r'Route::?(get|post|put|patch|delete)\s*\(["\']([^"\']+)',  # Laravel
        r'def\s+(\w+).*@route',  # Flask function-based routes
        r'app\.(get|post|put|patch|delete)\(["\']([^"\']+)',  # Express/Koa
    ]

    for i, line in enumerate(lines, 1):
        for pattern in patterns:
            matches = re.finditer(pattern, line, re.IGNORECASE)
            for match in matches:
                # Extract relevant context (the endpoint definition and surrounding code)
                start = max(0, i - 5)
                end = min(len(lines), i + 30)
                context = '\n'.join(lines[start:end])

                endpoint_path = match.group(2) if len(match.groups()) > 1 else match.group(1)
                endpoints.append({
                    'endpoint': endpoint_path,
                    'line_number': i,
                    'context': context
                })

    return endpoints

async def analyze_endpoint_with_llm(endpoint_data: Dict, client: anthropic.Anthropic) -> EndpointResult:
    """Use Claude to analyze if an endpoint performs dangerous actions"""

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

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        response_text = message.content[0].text.strip()

        # Parse JSON response
        # Remove markdown code blocks if present
        if response_text.startswith('```'):
            response_text = re.sub(r'^```json?\s*|\s*```$', '', response_text, flags=re.MULTILINE)

        result = json.loads(response_text)

        if result.get('is_dangerous', False):
            action_map = {
                'login': 'Logs user in',
                'logout': 'Logs user out',
                'password_change': 'Changes/deletes user password',
                'permission_change': 'Changes user permissions',
                'dangerous_upsert': 'Dangerous upsert/overwrite operation',
            }

            return EndpointResult(
                endpoint=endpoint_data['endpoint'],
                line_number=endpoint_data['line_number'],
                dangerous_action=action_map.get(result['action'], result['action']),
                confidence=result['confidence'],
                explanation=result['explanation']
            )

        return None

    except Exception as e:
        print(f"Error analyzing endpoint: {e}")
        return None

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_code(request: AnalyzeRequest):
    """Analyze source code for dangerous endpoints"""

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)

    # Extract endpoints from code
    endpoints = extract_endpoints_from_code(request.code)

    if not endpoints:
        return AnalyzeResponse(
            results=[],
            total_endpoints_analyzed=0
        )

    # Analyze each endpoint with Claude
    dangerous_endpoints = []
    for endpoint_data in endpoints:
        result = await analyze_endpoint_with_llm(endpoint_data, client)
        if result:
            dangerous_endpoints.append(result)

    return AnalyzeResponse(
        results=dangerous_endpoints,
        total_endpoints_analyzed=len(endpoints)
    )

@app.post("/analyze-batch", response_model=AnalyzeBatchResponse)
async def analyze_batch(request: AnalyzeBatchRequest):
    """Analyze multiple source code files for dangerous endpoints"""

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)

    file_results = []
    total_endpoints = 0
    total_dangerous = 0

    for file_input in request.files:
        # Extract endpoints from this file
        endpoints = extract_endpoints_from_code(file_input.content)
        total_endpoints += len(endpoints)

        # Analyze each endpoint with Claude
        dangerous_endpoints = []
        for endpoint_data in endpoints:
            result = await analyze_endpoint_with_llm(endpoint_data, client)
            if result:
                dangerous_endpoints.append(result)
                total_dangerous += 1

        file_results.append(FileResult(
            file_path=file_input.name,
            results=dangerous_endpoints,
            total_endpoints_analyzed=len(endpoints)
        ))

    return AnalyzeBatchResponse(
        files=file_results,
        total_files_analyzed=len(request.files),
        total_endpoints_analyzed=total_endpoints,
        total_dangerous_endpoints=total_dangerous
    )

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
