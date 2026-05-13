# 🔍 XBOW Endpoint Analysis

Analyze source code and detect potentially dangerous API endpoints that perform critical security actions like:

** DO NOT USE THIS AGAINST CUSTOMER CODE ON YOUR LOCAL MACHINE. IF USING LOCALLY ONLY SCAN OPEN SOURCE PORJECTS DOWNLOADED FROM THE OPEN SOURCE REPOSITORY. FOR EXAMPLE IF A CUSTOEMR CONFIRMS THEY ARE TESTING A NON-MODIFIED VERSION OF WEBGOAT, DOWNLOAD FROM THE RELEVANT GITHUB REPOSITORY **

1. **User Login** - Endpoints that authenticate users and create sessions
2. **User Logout** - Endpoints that terminate sessions or log users out
3. **Password Changes** - Endpoints that modify or delete user passwords
4. **Permission Changes** - Endpoints that modify user roles or permissions
5. **Dangerous Upsert/Overwrite Operations** - Endpoints that could accidentally overwrite user data (like passwords) during create-or-update operations


## Architecture

```
dangerous_endpoints/
├── backend/          # FastAPI backend with Anthropic integration
│   └── main.py
├── frontend/         # React + Vite frontend with Tailwind CSS
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css
│   └── package.json
└── requirements.txt
```

## Prerequisites

- Python 3.8+
- Node.js 18+
- Anthropic API key ([Get one here](https://console.anthropic.com/))

## Setup Instructions

### 1. Set up the Backend

```bash
# Install Python dependencies
pip install -r requirements.txt

# Set your Anthropic API key
export ANTHROPIC_API_KEY='your_api_key_here'

# Or create a .env file (recommended)
cp .env.example .env
# Then edit .env and add your API key
```

### 2. Set up the Frontend

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install
```

## Running the Application

### Start the Backend (Terminal 1)

```bash
# From the project root
cd backend
uvicorn main:app --reload --port 8000
```

The backend will be available at `http://localhost:8000`

### Start the Frontend (Terminal 2)

```bash
# From the project root
cd frontend
npm run dev
```

The frontend will be available at `http://localhost:3000`

## Usage

1. **Open the application** in your browser at `http://localhost:3000`

2. **Paste your source code** into the text area (can be from any framework)

3. **Click "Analyze Code"** to start the analysis

4. **Review results** showing:
   - Endpoint path and line number
   - Type of dangerous action detected
   - Confidence level (High/Medium/Low)
   - Detailed explanation

5. **Copy results** using the "Copy Results" button for easy sharing

## Example Code to Test

Try analyzing this Flask code:

```python
from flask import Flask, request, session

app = Flask(__name__)

@app.post('/api/logout')
def logout():
    session.clear()
    return {'message': 'Logged out'}

@app.post('/api/users/<user_id>/password')
def change_password(user_id):
    new_password = request.json.get('password')
    user = User.query.get(user_id)
    user.password = hash_password(new_password)
    db.session.commit()
    return {'message': 'Password updated'}

@app.post('/api/users/<user_id>/role')
def update_role(user_id):
    new_role = request.json.get('role')
    user = User.query.get(user_id)
    user.role = new_role
    db.session.commit()
    return {'message': 'Role updated'}
```

## How It Works

1. **Endpoint Extraction**: The backend uses regex patterns to identify API endpoint definitions across multiple frameworks

2. **Context Gathering**: For each endpoint, it extracts surrounding code context (30 lines)

3. **AI Analysis**: Claude analyzes the code context to determine:
   - If the endpoint performs dangerous actions
   - The type of action (login, logout, password change, permission change, dangerous upsert/overwrite)
   - Confidence level based on code clarity
   - Detailed explanation of the findings

4. **Results Display**: The frontend displays findings with color-coded badges and detailed explanations

## API Endpoints

### `POST /analyze`

Analyzes source code for dangerous endpoints.

**Request Body:**
```json
{
  "code": "string",
  "file_path": "string (optional)"
}
```

**Response:**
```json
{
  "results": [
    {
      "endpoint": "string",
      "line_number": number,
      "dangerous_action": "string",
      "confidence": "high|medium|low",
      "explanation": "string"
    }
  ],
  "total_endpoints_analyzed": number
}
```

### `GET /health`

Health check endpoint.

## Technologies Used

### Backend
- **FastAPI**: Modern Python web framework
- **Anthropic Python SDK**: Claude AI integration
- **Pydantic**: Data validation

### Frontend
- **React 18**: UI library
- **Vite**: Build tool and dev server
- **Tailwind CSS**: Utility-first CSS framework

## Security Notes

- This tool is designed for security auditing and code review purposes
- Always ensure you have permission to analyze the source code
- The tool uses AI which may produce false positives or negatives
- Always manually verify findings before taking action

## Troubleshooting

**Backend won't start:**
- Ensure your `ANTHROPIC_API_KEY` is set correctly
- Check that port 8000 is not already in use

**Frontend can't connect to backend:**
- Verify the backend is running on port 8000
- Check browser console for CORS errors

**No endpoints detected:**
- The tool supports common frameworks but may miss custom routing patterns
- Try code from Flask, FastAPI, Express, Spring Boot, or Laravel

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
