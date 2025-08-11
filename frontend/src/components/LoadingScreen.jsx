import React, { useEffect, useState } from 'react';
import erudiLogo from '../img/erudi.png';

export default function LoadingScreen() {
  const [status, setStatus] = useState('Starting');
  const [dotCount, setDotCount] = useState(1);
  const [issues, setIssues] = useState([]);
  const [error, setError] = useState(null);
  const [ready, setReady] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  const [logLines, setLogLines] = useState([]);
  const [copyStatus, setCopyStatus] = useState('idle'); // 'idle', 'copying', 'copied', 'error'

  const getErrorInfo = (errorCode, errorMessage) => {
    switch (errorCode) {
      case 'DEV_SETUP_MISSING':
        return {
          title: 'Development Environment Missing',
          message: 'Python virtual environment or run.py not found.',
          solution: 'Please ensure you have created the Python virtual environment in backend/venv and that run.py exists in the project root.'
        };
      case 'SPAWN_FAIL':
        return {
          title: 'Backend Launch Failed',
          message: 'Could not start the Python backend process.',
          solution: 'Check if Python is installed correctly and the virtual environment is properly configured. Try recreating the virtual environment.'
        };
      case 'STARTUP_TIMEOUT':
        return {
          title: 'Backend Startup Timeout',
          message: 'The backend took too long to start (>35 seconds).',
          solution: 'This might be due to missing dependencies or system resources. Try restarting or check if antivirus is blocking the process.'
        };
      case 'EXIT_BEFORE_READY':
        return {
          title: 'Backend Exited Early',
          message: `The backend process stopped unexpectedly during startup.`,
          solution: 'Check the technical details below for specific error messages. This usually indicates a configuration or dependency issue.'
        };
      case 'PORT_IN_USE':
        return {
          title: 'Port Already in Use',
          message: 'Port 8000 is already being used by another application.',
          solution: 'Close any other applications using port 8000, or restart your computer to free up the port.'
        };
      case 'CRASH_BEFORE_READY':
        return {
          title: 'Backend Crashed During Startup',
          message: 'The FastAPI server crashed before it could start properly.',
          solution: 'This usually indicates missing Python dependencies or configuration errors. Check the technical details for specific error messages.'
        };
      case 'PORT_TIMEOUT':
        return {
          title: 'Server Binding Timeout',
          message: 'The server could not bind to port 8000 within 25 seconds.',
          solution: 'This could be due to network issues or system overload. Try restarting the application or your computer.'
        };
      case 'UNEXPECTED_ERROR':
        return {
          title: 'Backend Crashed',
          message: 'The backend server encountered an unexpected error and crashed.',
          solution: 'This indicates a serious issue with the backend code or dependencies. Check the technical details for more information.'
        };
      case 'POLLING_ERROR':
        return {
          title: 'Monitoring System Error',
          message: 'The backend monitoring system encountered an error.',
          solution: 'This is a rare system-level error. Try restarting the application or your computer.'
        };
      case 'MISSING_DEPENDENCY':
        return {
          title: 'Missing Application Components',
          message: 'Essential application files or dependencies are missing.',
          solution: 'The application installation may be corrupted. Try reinstalling Erudi or contact support if the problem persists.'
        };
      case 'IMPORT_ERROR':
        return {
          title: 'Component Loading Failed',
          message: 'A critical application component failed to load properly.',
          solution: 'This could be due to corrupted files or incompatible system libraries. Try reinstalling the application.'
        };
      case 'CUDA_VERSION_MISMATCH':
        return {
          title: 'CUDA Version Incompatible',
          message: 'Your CUDA installation is not compatible with this application.',
          solution: 'Erudi requires CUDA 12.1. Please install NVIDIA CUDA Toolkit 12.1 from the official NVIDIA website.'
        };
      case 'CUDA_NOT_FOUND':
        return {
          title: 'CUDA Not Installed',
          message: 'NVIDIA CUDA is required but not found on your system.',
          solution: 'Please install NVIDIA CUDA Toolkit 12.1 from nvidia.com/cuda-downloads. Make sure you have an NVIDIA GPU.'
        };
      case 'GPU_DRIVER_MISSING':
        return {
          title: 'NVIDIA GPU Drivers Missing',
          message: 'NVIDIA GPU drivers are not installed or not functioning properly.',
          solution: 'Please install the latest NVIDIA GPU drivers from nvidia.com/drivers. Restart your computer after installation.'
        };
      case 'NO_NVIDIA_GPU':
        return {
          title: 'NVIDIA GPU Required',
          message: 'This application requires an NVIDIA graphics card but none was detected.',
          solution: 'Erudi requires an NVIDIA GPU with CUDA support. Please use a computer with an NVIDIA graphics card.'
        };
      case 'GPU_INIT_FAILED':
        return {
          title: 'GPU Initialization Failed',
          message: 'The application could not initialize your NVIDIA GPU.',
          solution: 'Make sure your NVIDIA GPU drivers are up to date and no other applications are using the GPU exclusively.'
        };
      case 'EXIT':
        return {
          title: 'Backend Stopped Unexpectedly',
          message: 'The backend process stopped running after it was working.',
          solution: 'This could be due to a runtime error or resource issue. Try restarting the application.'
        };
      default:
        return {
          title: 'Startup Error',
          message: errorMessage || `Unknown error occurred (${errorCode}).`,
          solution: 'Try restarting the application. If the problem persists, check the technical details or contact support.'
        };
    }
  };

  useEffect(() => {
    const api = window.electron;
    if (!api) return;

    const detachEvent = api.onBackendEvent(evt => {
      if (!evt || !evt.event) return;
      switch (evt.event) {
        case 'starting':
          setStatus('Initializing');
          break;
        case 'preflight_issue':
          setIssues(prev => [...prev, evt]);
          break;
        case 'ready':
          setStatus('Ready! Loading interface...');
          setReady(true);
          break;
        case 'startup_error':
          setError(evt);
          setStatus('Startup failed');
          break;
        case 'backend_exit':
          if (!ready && !error) {
            setError({ code: 'EXIT', message: 'Backend exited unexpectedly' });
            setStatus('Backend stopped');
          }
          break;
        default:
          break;
      }
    });

    const detachLog = api.onBackendLog(line => {
      setLogLines(prev => [...prev.slice(-199), line.trim()]);
    });
    const detachErr = api.onBackendLogError(line => {
      setLogLines(prev => [...prev.slice(-199), ('[ERR] ' + line.trim())]);
    });

    return () => { detachEvent && detachEvent(); detachLog && detachLog(); detachErr && detachErr(); };
  }, [ready, error]);

  const retry = () => {
    setStatus('Restarting backend');
    setIssues([]);
    setError(null);
    setReady(false);
    setShowLogs(false);
    setCopyStatus('idle');
    window.electron?.restartBackend();
  };

  const copyLogsToClipboard = async () => {
    if (!error || copyStatus === 'copying') return;
    
    setCopyStatus('copying');
    
    try {
      const errorDetails = {
        timestamp: new Date().toISOString(),
        errorCode: error?.code || 'UNKNOWN',
        errorMessage: error?.message || 'No error message',
        logs: logLines.slice(-100) // Last 100 log lines
      };
      
      const logText = `Erudi Error Report
Generated: ${errorDetails.timestamp}
Error Code: ${errorDetails.errorCode}
Error Message: ${errorDetails.errorMessage}

Technical Logs:
${errorDetails.logs.join('\n')}`;

      await navigator.clipboard.writeText(logText);
      setCopyStatus('copied');
      
      // Reset after 2 seconds
      setTimeout(() => {
        setCopyStatus('idle');
      }, 2000);
      
    } catch (err) {
      console.error('Failed to copy logs:', err);
      setCopyStatus('error');
      
      // Reset after 2 seconds
      setTimeout(() => {
        setCopyStatus('idle');
      }, 2000);
    }
  };

  const openContactPage = () => {
    window.open('https://erudi.app/contact', '_blank', 'noopener,noreferrer');
  };

  const errorInfo = error ? getErrorInfo(error.code, error.message) : null;

  useEffect(() => {
    if (ready || error) return;
    const interval = setInterval(() => {
      setDotCount(prev => (prev % 3) + 1);
    }, 500);
    return () => clearInterval(interval);
  }, [ready, error]);

  return (
    <div className="fixed inset-0 flex flex-col items-center justify-center z-[9999] px-6" style={{ backgroundColor: '#02130e' }}>
  <img src={erudiLogo} alt="erudi Logo" className="w-auto h-24 mb-2 object-contain" />

      {/* Loading State */}
      {!ready && !error && (
        <div className="flex flex-col items-center">
          <div className="w-12 h-12 border-4 border-gray-200/20 border-t-green-500 rounded-full animate-spin mb-4" />
          <div className="text-gray-300 text-lg flex items-center">
            {status}
            <span className="inline-block" style={{ width: '1.5em' }}>
              {'.'.repeat(dotCount)}
            </span>
          </div>
        </div>
      )}

      {/* Success State */}
      {ready && !error && (
        <div className="flex flex-col items-center">
          <div className="text-green-400 text-lg mb-2">✓ {status}</div>
          <div className="w-8 h-8 border-4 border-green-400/20 border-t-green-400 rounded-full animate-spin" />
        </div>
      )}

      {/* Error State */}
      {error && errorInfo && (
        <div className="w-full max-w-3xl">
          <div className="border border-gray-700 rounded-lg p-5 mb-4" style={{ backgroundColor: '#0a1612' }}>
            <div className="flex items-start mb-3">
              <div className="text-xl mr-3 mt-0.5" style={{ color: '#ff6b6b' }}>⚠</div>
              <div>
                <h3 className="text-lg font-semibold mb-2" style={{ color: '#e0e0e0' }}>{errorInfo.title}</h3>
                <p className="text-gray-300 mb-3 leading-relaxed">{errorInfo.message}</p>
                <div className="border-l-3 border-gray-600 pl-4" style={{ borderLeftColor: '#00c978' }}>
                  <p className="text-sm text-gray-300">{errorInfo.solution}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Console-style Error Log */}
          <div className="border border-gray-700 rounded-lg overflow-hidden" style={{ backgroundColor: '#0a1612' }}>
            <div className="flex items-center justify-between px-4 py-2 border-b border-gray-700" style={{ backgroundColor: '#061009' }}>
              <div className="flex items-center space-x-2">
                <div className="text-xs font-mono text-gray-400">ERROR LOG</div>
                <div className="text-xs text-gray-500">•</div>
                <div className="text-xs text-gray-500">{error?.code || 'UNKNOWN'}</div>
              </div>
              <div className="flex items-center space-x-2">
                <button 
                  onClick={() => setShowLogs(!showLogs)} 
                  className="text-xs text-gray-400 hover:text-gray-200 transition-colors px-2 py-1 rounded hover:bg-gray-800"
                >
                  {showLogs ? 'COLLAPSE' : 'EXPAND'}
                </button>
                <button 
                  onClick={copyLogsToClipboard}
                  disabled={copyStatus === 'copying'}
                  className="flex items-center text-xs text-gray-400 hover:text-gray-200 transition-colors px-2 py-1 rounded hover:bg-gray-800 disabled:opacity-50"
                >
                  {copyStatus === 'copying' && (
                    <div className="w-3 h-3 border border-gray-400 border-t-transparent rounded-full animate-spin mr-1" />
                  )}
                  {copyStatus === 'copied' && (
                    <div className="mr-1" style={{ color: '#00c978' }}>✓</div>
                  )}
                  {copyStatus === 'error' && (
                    <div className="mr-1 text-red-400">✗</div>
                  )}
                  {copyStatus === 'idle' && 'COPY'}
                  {copyStatus === 'copying' && 'COPYING'}
                  {copyStatus === 'copied' && 'COPIED'}
                  {copyStatus === 'error' && 'FAILED'}
                </button>
              </div>
            </div>

            {/* Console Content */}
            <div className="p-4">
              <div className="text-xs font-mono text-gray-300 mb-3 leading-relaxed">
                <span className="text-red-400">error:</span> {error?.message || 'Unknown error occurred'}
              </div>
              
              <div
                className={`border-t border-gray-700 pt-3 mt-3 transition-all duration-500 overflow-hidden ${showLogs ? 'max-h-64 opacity-100' : 'max-h-0 opacity-0'}`}
                aria-hidden={!showLogs}
              >
                <div className="text-xs font-mono text-gray-500 mb-2">Stack trace:</div>
                <div className="bg-black/30 rounded p-3 max-h-40 overflow-auto">
                  <pre className="text-xs text-gray-400 whitespace-pre-wrap">
                    {logLines.slice(-50).join('\n') || 'No detailed logs available'}
                  </pre>
                </div>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 mt-4">
            <button 
              onClick={retry} 
              className="px-4 py-2 rounded-md font-medium transition-all duration-200 hover:scale-105"
              style={{ 
                backgroundColor: '#00c978', 
                color: '#02130e'
              }}
            >
              Retry Startup
            </button>
            <button 
              onClick={openContactPage} 
              className="px-4 py-2 rounded-md border border-gray-600 text-gray-300 hover:bg-gray-800 font-medium transition-colors"
            >
              Get Help
            </button>
          </div>
        </div>
      )}

      {/* Warnings */}
      {issues.length > 0 && !error && (
        <div className="bg-yellow-900/30 border border-yellow-600/40 rounded-lg p-4 w-full max-w-2xl mt-4">
          <div className="flex items-center mb-2">
            <div className="text-yellow-400 text-xl mr-2">⚠</div>
            <div className="text-yellow-200 font-semibold">Warnings</div>
          </div>
          <ul className="text-yellow-100 text-sm space-y-1 max-h-32 overflow-auto">
            {issues.map((i, idx) => (
              <li key={idx} className="flex">
                <span className="font-medium mr-2">{i.code}:</span>
                <span>{i.message}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}