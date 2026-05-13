import { useState, useEffect } from 'react'

function App() {
  const [selectedFiles, setSelectedFiles] = useState([])
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [copied, setCopied] = useState(false)
  const [copiedEndpoints, setCopiedEndpoints] = useState(false)
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('darkMode')
    return saved ? JSON.parse(saved) : false
  })

  useEffect(() => {
    localStorage.setItem('darkMode', JSON.stringify(darkMode))
    if (darkMode) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [darkMode])

  const toggleDarkMode = () => {
    setDarkMode(!darkMode)
  }

  const handleFileSelect = async (event) => {
    const files = Array.from(event.target.files)

    // Filter for code files
    const codeExtensions = ['.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.php', '.rb', '.go', '.cs', '.cpp', '.c', '.h']
    const codeFiles = files.filter(file =>
      codeExtensions.some(ext => file.name.toLowerCase().endsWith(ext))
    )

    if (codeFiles.length === 0) {
      setError('No code files found in the selected folder')
      return
    }

    // Read file contents
    const filePromises = codeFiles.map(file => {
      return new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = (e) => resolve({
          name: file.webkitRelativePath || file.name,
          content: e.target.result
        })
        reader.onerror = reject
        reader.readAsText(file)
      })
    })

    try {
      const filesWithContent = await Promise.all(filePromises)
      setSelectedFiles(filesWithContent)
      setError(null)
    } catch (err) {
      setError('Error reading files: ' + err.message)
    }
  }

  const analyzeFiles = async () => {
    if (selectedFiles.length === 0) {
      setError('Please select a folder to analyze')
      return
    }

    setLoading(true)
    setError(null)
    setResults(null)

    try {
      const response = await fetch('http://localhost:8000/analyze-batch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          files: selectedFiles
        })
      })

      if (!response.ok) {
        throw new Error('Failed to analyze code')
      }

      const data = await response.json()
      setResults(data)
    } catch (err) {
      setError(err.message || 'An error occurred while analyzing the code')
    } finally {
      setLoading(false)
    }
  }

  const copyResults = () => {
    if (!results || !results.files || results.files.length === 0) return

    let text = ''
    results.files.forEach(file => {
      if (file.results.length > 0) {
        text += `\n=== ${file.file_path} ===\n`
        file.results.forEach((result, index) => {
          text += `${index + 1}. ${result.endpoint} (Line ${result.line_number})
   Action: ${result.dangerous_action}
   Confidence: ${result.confidence}
   Explanation: ${result.explanation}\n\n`
        })
      }
    })

    navigator.clipboard.writeText(text.trim()).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const copyEndpoints = () => {
    if (!results || !results.files || results.files.length === 0) return

    const endpoints = []
    results.files.forEach(file => {
      file.results.forEach(result => {
        endpoints.push(result.endpoint)
      })
    })

    navigator.clipboard.writeText(endpoints.join('\n')).then(() => {
      setCopiedEndpoints(true)
      setTimeout(() => setCopiedEndpoints(false), 2000)
    })
  }

  const getConfidenceBadgeColor = (confidence) => {
    switch (confidence.toLowerCase()) {
      case 'high':
        return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
      case 'medium':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
      case 'low':
        return 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
    }
  }

  const getActionBadgeColor = (action) => {
    const lowerAction = action.toLowerCase()
    if (lowerAction.includes('login') || lowerAction.includes('logs user in')) {
      return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
    } else if (lowerAction.includes('logout')) {
      return 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'
    } else if (lowerAction.includes('password')) {
      return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
    } else if (lowerAction.includes('permission')) {
      return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
    } else if (lowerAction.includes('upsert') || lowerAction.includes('overwrite')) {
      return 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200'
    }
    return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 transition-colors duration-200">
      <div className="container mx-auto px-4 py-8 max-w-6xl">
        <div className="text-center mb-8 relative">
          <button
            onClick={toggleDarkMode}
            className="absolute right-0 top-0 p-3 rounded-lg bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors duration-200 shadow-md hover:shadow-lg cursor-pointer"
            aria-label="Toggle dark mode"
            title="Toggle dark mode"
          >
            {darkMode ? (
              <svg className="w-6 h-6 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            ) : (
              <svg className="w-6 h-6 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
              </svg>
            )}
          </button>
          <h1 className="text-4xl font-bold text-gray-900 dark:text-white mb-2">
            🔍 Dangerous Endpoint Detector
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            XBOW Endpoint Analysis - Analyze source code for dangerous endpoint actions
          </p>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 mb-6 transition-colors duration-200">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Select Folder to Analyze
          </label>

          <div className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-8 text-center hover:border-blue-500 dark:hover:border-blue-400 transition-colors duration-200">
            <input
              type="file"
              id="folder-input"
              webkitdirectory="true"
              directory="true"
              multiple
              onChange={handleFileSelect}
              className="hidden"
            />
            <label htmlFor="folder-input" className="cursor-pointer">
              <svg className="mx-auto h-12 w-12 text-gray-400 dark:text-gray-500 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
              </svg>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                <span className="font-semibold text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300">
                  Click to select a folder
                </span>
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-500">
                Supports: Python, JavaScript, TypeScript, Java, PHP, Ruby, Go, C#, C/C++
              </p>
            </label>
          </div>

          {selectedFiles.length > 0 && (
            <div className="mt-4 p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                📁 Selected: {selectedFiles.length} code file{selectedFiles.length !== 1 ? 's' : ''}
              </p>
              <div className="max-h-32 overflow-y-auto text-xs text-gray-600 dark:text-gray-400 space-y-1">
                {selectedFiles.map((file, index) => (
                  <div key={index} className="truncate">• {file.name}</div>
                ))}
              </div>
            </div>
          )}

          <button
            onClick={analyzeFiles}
            disabled={loading || selectedFiles.length === 0}
            className="mt-4 w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-semibold py-3 px-6 rounded-lg transition-colors duration-200 flex items-center justify-center"
          >
            {loading ? (
              <>
                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Analyzing {selectedFiles.length} file{selectedFiles.length !== 1 ? 's' : ''}...
              </>
            ) : (
              `🔍 Analyze ${selectedFiles.length > 0 ? selectedFiles.length + ' File' + (selectedFiles.length !== 1 ? 's' : '') : 'Folder'}`
            )}
          </button>
        </div>

        {error && (
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded-lg mb-6">
            <div className="flex items-center">
              <span className="text-xl mr-2">⚠️</span>
              <span>{error}</span>
            </div>
          </div>
        )}

        {results && (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 transition-colors duration-200">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
                Analysis Results
              </h2>
              <div className="flex items-center gap-3">
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  {results.total_files_analyzed} file{results.total_files_analyzed !== 1 ? 's' : ''} • {results.total_endpoints_analyzed} endpoint{results.total_endpoints_analyzed !== 1 ? 's' : ''}
                </span>
                {results.total_dangerous_endpoints > 0 && (
                  <button
                    onClick={copyResults}
                    className="bg-green-600 hover:bg-green-700 text-white font-medium py-2 px-4 rounded-lg transition-colors duration-200 flex items-center gap-2"
                  >
                    {copied ? (
                      <>
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                        Copied!
                      </>
                    ) : (
                      <>
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                        </svg>
                        Copy Results
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>

            {results.total_dangerous_endpoints === 0 ? (
              <div className="text-center py-8">
                <div className="text-6xl mb-4">✅</div>
                <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                  No Dangerous Endpoints Found
                </h3>
                <p className="text-gray-600 dark:text-gray-400">
                  All analyzed endpoints appear to be safe.
                </p>
              </div>
            ) : (
              <div className="space-y-6">
                {results.files.map((file, fileIndex) => (
                  file.results.length > 0 && (
                    <div key={fileIndex} className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
                      <div className="bg-gray-100 dark:bg-gray-700 px-4 py-3 border-b border-gray-200 dark:border-gray-600">
                        <h3 className="font-mono text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                          {file.file_path}
                          <span className="ml-auto text-xs font-normal text-gray-600 dark:text-gray-400">
                            {file.results.length} issue{file.results.length !== 1 ? 's' : ''}
                          </span>
                        </h3>
                      </div>
                      <div className="p-4 space-y-4">
                        {file.results.map((result, resultIndex) => (
                          <div
                            key={resultIndex}
                            className="border border-gray-200 dark:border-gray-600 rounded-lg p-4 hover:shadow-md transition-shadow duration-200 bg-white dark:bg-gray-800/50"
                          >
                            <div className="flex justify-between items-start mb-3">
                              <div className="flex-1">
                                <h4 className="text-base font-semibold text-gray-900 dark:text-white font-mono">
                                  {result.endpoint}
                                </h4>
                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                                  Line {result.line_number}
                                </p>
                              </div>
                              <div className="flex gap-2">
                                <span className={`px-3 py-1 rounded-full text-xs font-semibold ${getActionBadgeColor(result.dangerous_action)}`}>
                                  {result.dangerous_action}
                                </span>
                                <span className={`px-3 py-1 rounded-full text-xs font-semibold ${getConfidenceBadgeColor(result.confidence)}`}>
                                  {result.confidence.toUpperCase()}
                                </span>
                              </div>
                            </div>
                            <p className="text-gray-700 dark:text-gray-300 text-sm">
                              {result.explanation}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )
                ))}
              </div>
            )}
          </div>
        )}

        {results && results.total_dangerous_endpoints > 0 && (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 mt-6 transition-colors duration-200">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
                Endpoint List
              </h2>
              <button
                onClick={copyEndpoints}
                className="bg-green-600 hover:bg-green-700 text-white font-medium py-2 px-4 rounded-lg transition-colors duration-200 flex items-center gap-2"
              >
                {copiedEndpoints ? (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    Copied!
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                    Copy List
                  </>
                )}
              </button>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Simple list of all dangerous endpoints for easy copy/paste
            </p>
            <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
              <pre className="font-mono text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap break-all max-h-96 overflow-y-auto">
                {results.files.map((file, fileIndex) =>
                  file.results.map((result, resultIndex) => (
                    <div key={`${fileIndex}-${resultIndex}`} className="py-1">
                      {result.endpoint}
                    </div>
                  ))
                )}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default App
