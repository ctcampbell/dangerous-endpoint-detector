# 🔍 XBOW Dangerous Endpoint Detector

A command-line tool that scans a source tree for potentially dangerous API endpoints using Claude.

**⚠️ DO NOT USE THIS AGAINST CUSTOMER CODE ON YOUR LOCAL MACHINE. IF USING LOCALLY ONLY SCAN OPEN SOURCE PROJECTS DOWNLOADED FROM THE OPEN SOURCE REPOSITORY. FOR EXAMPLE, IF A CUSTOMER CONFIRMS THEY ARE TESTING A NON-MODIFIED VERSION OF WEBGOAT, DOWNLOAD FROM THE RELEVANT GITHUB REPOSITORY.**

It detects endpoints that:

1. **Log a user in** — authentication, session creation, token generation
2. **Log a user out** — session termination, token revocation
3. **Change/delete user passwords**
4. **Change user permissions or roles**
5. **Perform dangerous upsert/overwrite operations** that could clobber existing user data

## Installation

```bash
pip install .
```

Or install it as an isolated CLI with [pipx](https://pipx.pypa.io/):

```bash
pipx install .
```

This installs a `dangerous-endpoints` executable. Alternatively, install dependencies and run as a module:

```bash
pip install -r requirements.txt
python -m dangerous_endpoints
```

## Usage

Run from the source root of the target application:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
cd /path/to/target/app
dangerous-endpoints
```

You can also pass a path explicitly:

```bash
dangerous-endpoints /path/to/target/app
```

The tool walks the directory, extracts endpoint definitions from common frameworks (Flask, FastAPI, Express, Spring, Laravel, etc.), and asks Claude to classify each one. Findings are printed to the terminal; the exit code is non-zero when dangerous endpoints are found.

### Options

```
dangerous-endpoints [PATH] [options]

  --model MODEL          Anthropic model to use (default: claude-sonnet-4-6)
  --concurrency N        Max concurrent LLM requests (default: 8)
  --extensions .py .js   Override the file extensions to scan
  --ignore DIR [DIR...]  Additional directory names to ignore
  --json FILE            Write a JSON report to FILE
  --no-color             Disable ANSI colors
  -v, --verbose          Print safe endpoints as well as dangerous ones
```

### Environment

`ANTHROPIC_API_KEY` is required. A `.env` file in the working directory is loaded automatically if `python-dotenv` is installed.

## How it works

1. **Discovery** — recursively walks the target directory, skipping common build/dependency folders (`node_modules`, `.venv`, `dist`, etc.).
2. **Endpoint extraction** — regex patterns identify route definitions across Flask, FastAPI, Express, Spring, Laravel, and similar frameworks.
3. **Context gathering** — 30 lines of surrounding code are collected per endpoint.
4. **AI classification** — Claude inspects each endpoint and returns `is_dangerous`, action type, confidence, and explanation.
5. **Reporting** — findings are grouped by file and printed; optionally written to JSON.

## Exit codes

- `0` — no dangerous endpoints found
- `1` — dangerous endpoints found
- `2` — usage / configuration error
- `130` — interrupted

## Security notes

- This tool is intended for security auditing and code review.
- Always ensure you have permission to analyze the source code.
- AI classification can produce false positives or negatives — verify findings manually.
