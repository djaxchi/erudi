// src/contexts/DownloadModalContext.jsx
import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
} from 'react'
import ReactDOM from 'react-dom'
import ConfirmationModal from '../components/modals/ConfirmationModal'
import SpinnerDots from '../components/Spinner'
import { X, ChevronLeft, ChevronRight } from 'lucide-react'

const DownloadModalContext = createContext()
const API_BASE = 'http://127.0.0.1:8000'

export function DownloadModalProvider({ children }) {
  const [model, setModel] = useState(null)
  const [isConfirmOpen, setIsConfirmOpen] = useState(false)
  const [isDownloading, setIsDownloading] = useState(false)
  const [isCollapsed, setIsCollapsed] = useState(true)
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState('idle')
  const [timeLeft, setTimeLeft] = useState(null)
  const [errorMessage, setErrorMessage] = useState('')

  const intervalRef = useRef(null)
  const callbacksRef = useRef({ onComplete: null, onError: null })

  const toggleCollapse = useCallback(() => {
    setIsCollapsed(c => !c)
  }, [])

  const open = useCallback((selectedModel, { onComplete, onError } = {}) => {
    setModel(selectedModel)
    callbacksRef.current = { onComplete, onError }
    setErrorMessage('')
    setIsConfirmOpen(true)
  }, [])

  const cancelConfirm = useCallback(() => setIsConfirmOpen(false), [])

  const checkDownloadStatus = useCallback(async id => {
    try {
      const res = await fetch(`${API_BASE}/main_window/downloads/${id}/status`)
      if (!res.ok) throw new Error('status fetch failed')
      const data = await res.json()
      setProgress(data.progress)
      setStatus(data.status)
      setTimeLeft(data.time_left)
     

      if (data.status === 'completed' || data.status === 'failed') {
        clearInterval(intervalRef.current)
        setIsDownloading(false)
        if (data.status === 'completed') {
          callbacksRef.current.onComplete?.()
        } else {
          setErrorMessage(data.error_message || 'Download Failed')
          callbacksRef.current.onError?.(data.error_message)
        }
      }
    } catch (err) {
      clearInterval(intervalRef.current)
      setIsDownloading(false)
      setErrorMessage('Error checking download status.')
      callbacksRef.current.onError?.(err)
    }
  }, [])

  const handleConfirm = useCallback(async () => {
    setIsConfirmOpen(false)
    setIsDownloading(true)
    setStatus('pending')
    setProgress(0)
    setErrorMessage('')

    setTimeout(() => setIsCollapsed(false), 2000)

    try {
      const res = await fetch(
        `${API_BASE}/main_window/llms/${model.id}/download`,
        { method: 'POST' }
      )
      if (!res.ok) throw new Error('Failed to start download.')
      const job = await res.json()

      intervalRef.current = setInterval(() => {
        checkDownloadStatus(job.id)
      }, 2000)
    } catch (err) {
      setErrorMessage(err.message ?? err)
      setIsDownloading(false)
      callbacksRef.current.onError?.(err)
    }
  }, [model, checkDownloadStatus])

  const cancelDownload = useCallback(() => {
    clearInterval(intervalRef.current)
    setIsDownloading(false)
    setProgress(0)
    setStatus('cancelled')
    callbacksRef.current.onError?.('cancelled')
  }, [])

  return (
    <DownloadModalContext.Provider value={{ open }}>
      {children}

      {(isConfirmOpen || isDownloading) &&
        ReactDOM.createPortal(
          <>
            {isConfirmOpen && (
              <ConfirmationModal
                isOpen
                onCancel={cancelConfirm}
                onConfirm={handleConfirm}
                text={model?.name}
              />
            )}
            {isDownloading && (
              <>
                <div className="fixed bottom-7 left-[1.5%]">
                  <SpinnerDots className="w-6 h-6 text-emerald-400 animate-spin" />
                </div>
                <div
                  className={`fixed bottom-0 bg-[#121212]/50 p-4 flex items-center rounded-r-3xl z-50 ${
                    isCollapsed
                      ? 'left-[6%] w-0 bg-transparent'
                      : 'left-[6%] w-[35%] sm:w-[38%] xl:w-[28%] gap-3'
                  }`}
                >
                  <div className="flex-1">
                    {!isCollapsed && (
                      <>
                        <div className="flex items-center justify-between w-full">
                          <p className="text-white font-semibold truncate">
                            Downloading: {model?.name}
                          </p>
                          <X
                            className="w-5 h-5 cursor-pointer text-red-400 hover:text-red-600"
                            onClick={cancelDownload}
                          />
                        </div>
                        <div className="flex gap-4 text-sm text-gray-300 mt-2">
                          <span>
                            Time Left:{' '}
                            <span className="font-medium">
                              {status === 'running'
                                ? `${timeLeft}s left`
                                : '--'}
                            </span>
                          </span>
                          <span>
                            Progress:{' '}
                            <span className="font-medium">
                              {status === 'running'
                                ? `${(progress)}%`
                                : '--'}
                            </span>
                          </span>
                        </div>
                        <div className="absolute left-0 bottom-0 bg-gray-700 overflow-hidden w-full mt-2">
                          <div
                            className="absolute inset-0 bg-gradient-to-r from-emerald-500 to-emerald-300 transition-all duration-200"
                            style={{ width: `${progress}%` }}
                          />
                        </div>
                      </>
                    )}
                  </div>
                  <button
                    className="absolute bottom-8 right-0"
                    onClick={toggleCollapse}
                    aria-label={isCollapsed ? 'Expand' : 'Collapse'}
                  >
                    {isCollapsed ? (
                      <ChevronRight className="w-6 h-6 text-gray-300 hover:text-white" />
                    ) : (
                      <ChevronLeft className="w-6 h-6 text-gray-300 hover:text-white" />
                    )}
                  </button>
                </div>
              </>
            )}
          </>,
          document.getElementById('modal-root')
        )}
    </DownloadModalContext.Provider>
  )
}

export function useDownloadModal() {
  return useContext(DownloadModalContext)
}