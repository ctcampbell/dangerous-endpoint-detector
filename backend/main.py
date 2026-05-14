from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic
import os
import re
from typing import List, Dict
import json
from dotenv import load_dotenv
import logging
import asyncio

# Load environment variables from .env file
load_dotenv(dotenv_path="../.env")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

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

def extract_endpoints_from_code(code: str, file_path: str = "unknown") -> List[Dict[str, any]]:
    """Extract potential API endpoints from code with line numbers"""
    logger.info(f"Extracting endpoints from {file_path}")
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

    logger.info(f"Found {len(endpoints)} endpoints in {file_path}")
    return endpoints

async def analyze_endpoint_with_llm(endpoint_data: Dict, client: anthropic.Anthropic) -> EndpointResult:
    """Use Claude to analyze if an endpoint performs dangerous actions"""
    logger.info(f"Analyzing endpoint: {endpoint_data['endpoint']} (line {endpoint_data['line_number']})")

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

            logger.info(f"⚠️  DANGEROUS endpoint found: {endpoint_data['endpoint']} - {action_map.get(result['action'], result['action'])} (confidence: {result['confidence']})")
            return EndpointResult(
                endpoint=endpoint_data['endpoint'],
                line_number=endpoint_data['line_number'],
                dangerous_action=action_map.get(result['action'], result['action']),
                confidence=result['confidence'],
                explanation=result['explanation']
            )

        logger.info(f"✓ Endpoint {endpoint_data['endpoint']} is safe")
        return None

    except Exception as e:
        logger.error(f"Error analyzing endpoint {endpoint_data['endpoint']}: {e}")
        return None

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_code(request: AnalyzeRequest):
    """Analyze source code for dangerous endpoints"""
    logger.info(f"Starting analysis for file: {request.file_path}")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)

    # Extract endpoints from code
    endpoints = extract_endpoints_from_code(request.code, request.file_path)

    if not endpoints:
        logger.info(f"No endpoints found in {request.file_path}")
        return AnalyzeResponse(
            results=[],
            total_endpoints_analyzed=0
        )

    # Analyze all endpoints concurrently with Claude
    logger.info(f"Starting concurrent analysis of {len(endpoints)} endpoints")
    tasks = [analyze_endpoint_with_llm(endpoint_data, client) for endpoint_data in endpoints]
    results = await asyncio.gather(*tasks)

    # Filter out None results (safe endpoints)
    dangerous_endpoints = [r for r in results if r is not None]

    logger.info(f"Analysis complete: {len(dangerous_endpoints)} dangerous endpoints found out of {len(endpoints)} total")
    return AnalyzeResponse(
        results=dangerous_endpoints,
        total_endpoints_analyzed=len(endpoints)
    )

@app.post("/analyze-batch", response_model=AnalyzeBatchResponse)
async def analyze_batch(request: AnalyzeBatchRequest):
    """Analyze multiple source code files for dangerous endpoints"""
    logger.info(f"Starting batch analysis for {len(request.files)} files")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)

    file_results = []
    total_endpoints = 0
    total_dangerous = 0

    for idx, file_input in enumerate(request.files, 1):
        logger.info(f"Processing file {idx}/{len(request.files)}: {file_input.name}")

        # Extract endpoints from this file
        endpoints = extract_endpoints_from_code(file_input.content, file_input.name)
        total_endpoints += len(endpoints)

        # Analyze all endpoints concurrently with Claude
        if endpoints:
            logger.info(f"Starting concurrent analysis of {len(endpoints)} endpoints in {file_input.name}")
            tasks = [analyze_endpoint_with_llm(endpoint_data, client) for endpoint_data in endpoints]
            results = await asyncio.gather(*tasks)

            # Filter out None results (safe endpoints)
            dangerous_endpoints = [r for r in results if r is not None]
            total_dangerous += len(dangerous_endpoints)

            logger.info(f"File {file_input.name}: {len(dangerous_endpoints)} dangerous endpoints found")
        else:
            dangerous_endpoints = []

        file_results.append(FileResult(
            file_path=file_input.name,
            results=dangerous_endpoints,
            total_endpoints_analyzed=len(endpoints)
        ))

    logger.info(f"Batch analysis complete: {total_dangerous} dangerous endpoints found in {total_endpoints} total endpoints across {len(request.files)} files")
    return AnalyzeBatchResponse(
        files=file_results,
        total_files_analyzed=len(request.files),
        total_endpoints_analyzed=total_endpoints,
        total_dangerous_endpoints=total_dangerous
    )

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
