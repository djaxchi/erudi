import React, { useEffect, useState } from "react";
import erudiLogo from "../img/erudi.png";

export default function LoadingScreen() {
  const [status, setStatus] = useState("Starting");
  const [dotCount, setDotCount] = useState(1);
  const [issues, setIssues] = useState([]);
  const [error, setError] = useState(null);
  const [ready, setReady] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  const [logLines, setLogLines] = useState([]);
  const [copyStatus, setCopyStatus] = useState("idle"); // 'idle', 'copying', 'copied', 'error'
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [userEmail, setUserEmail] = useState("");
  const [userCompany, setUserCompany] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [sendStatus, setSendStatus] = useState("idle"); // 'idle', 'sending', 'success', 'error'
  const [showReportForm, setShowReportForm] = useState(false);
  const [isPackaged, setIsPackaged] = useState(null);
  const [emailError, setEmailError] = useState("");

  // Check if we're in development mode
  const isDevelopment = isPackaged === false;

  // Google Apps Script URL for error reports (same as contact form)
  const CONTACT_GOOGLE_SCRIPT_URL =
    "https://script.google.com/macros/s/AKfycbyYoZEv3cOw6HWhKhFxaSY6TPnaKF72yr9WfJUxquroxW2J3elrJP-SGfAeiGcGQ4hizA/exec";

  const getErrorInfo = (errorCode, errorMessage) => {
    switch (errorCode) {
      case "DEV_SETUP_MISSING":
        return {
          title: "Development Environment Issue",
          message:
            "Required development files are missing (this should not happen in the packaged version).",
          solution:
            "If you are seeing this error in the installed version, please reinstall Erudi from the official website.",
        };
      case "SPAWN_FAIL":
        return {
          title: "Backend Launch Failed",
          message: "Could not start the application backend process.",
          solution:
            "Try running Erudi as administrator, or temporarily disable antivirus software during startup. If the issue persists, reinstall Erudi.",
        };
      case "STARTUP_TIMEOUT":
        return {
          title: "Startup Taking Too Long",
          message:
            "The application is taking longer than expected to start (>35 seconds).",
          solution:
            "Try closing other applications to free up system resources, or restart your computer. If you have antivirus software, try temporarily disabling it.",
        };
      case "EXIT_BEFORE_READY":
        return {
          title: "Application Startup Failed",
          message: `The application backend stopped unexpectedly during startup.`,
          solution:
            "Check the technical details below for specific error information. This usually indicates a system compatibility issue or missing system requirements.",
        };
      case "PORT_IN_USE":
        return {
          title: "Port Already in Use",
          message: "Port 8000 is already being used by another application.",
          solution:
            "Close any other applications using port 8000, or restart your computer to free up the port.",
        };
      case "CRASH_BEFORE_READY":
        return {
          title: "Application Startup Crash",
          message: "The application crashed before it could start properly.",
          solution:
            "This usually indicates missing system requirements or incompatible hardware. Check the technical details for specific errors, or contact support.",
        };
      case "PORT_TIMEOUT":
        return {
          title: "Network Service Timeout",
          message:
            "The internal network service could not start within 25 seconds.",
          solution:
            "Check if your firewall or antivirus is blocking the application. Try temporarily disabling them or adding Erudi to your exceptions list.",
        };
      case "UNEXPECTED_ERROR":
        return {
          title: "Application Crashed",
          message:
            "The application encountered an unexpected error and crashed.",
          solution:
            "Try restarting your computer. If the issue persists, check the technical details or contact support for assistance.",
        };
      case "POLLING_ERROR":
        return {
          title: "System Monitoring Error",
          message: "The application monitoring system encountered an error.",
          solution:
            "This is a rare system-level error. Try restarting your computer or contact support if the issue persists.",
        };
      case "PYNVML_MISSING":
        return {
          title: "NVIDIA Management Library Missing",
          message:
            "A required component for GPU monitoring is missing from the application.",
          solution:
            "This indicates an incomplete installation. Please reinstall Erudi from the official website to restore all required components.",
        };
      case "PYTORCH_MISSING":
        return {
          title: "AI Framework Missing",
          message:
            "A core AI framework required by Erudi is not properly installed.",
          solution:
            "Please reinstall Erudi from the official website. This will ensure all AI components are properly included.",
        };
      case "BITSANDBYTES_MISSING":
        return {
          title: "Model Optimization Library Missing",
          message:
            "A library required for efficient model processing is not installed.",
          solution:
            "Please reinstall Erudi from the official website to restore all optimization components.",
        };
      case "TRANSFORMERS_MISSING":
        return {
          title: "AI Model Library Missing",
          message:
            "The Hugging Face AI model library is not properly installed.",
          solution:
            "Please reinstall Erudi from the official website to ensure all AI libraries are included.",
        };
      case "MISSING_DEPENDENCY":
        return {
          title: "Missing Application Components",
          message:
            "Essential application files or libraries are missing from the installation.",
          solution:
            "Please reinstall Erudi from the official website to restore all required components.",
        };
      case "IMPORT_ERROR":
        return {
          title: "Component Loading Failed",
          message: "A critical application component failed to load properly.",
          solution:
            "This indicates a corrupted installation. Please reinstall Erudi from the official website.",
        };
      case "CUDA_VERSION_MISMATCH":
        return {
          title: "CUDA Version Incompatible",
          message:
            "Your CUDA installation is not compatible with this version of Erudi.",
          solution:
            "Please update to NVIDIA CUDA Toolkit 12.1 or later from the official NVIDIA website, then restart Erudi.",
        };
      case "CUDA_NOT_FOUND":
        return {
          title: "CUDA Not Installed",
          message:
            "NVIDIA CUDA is required for AI processing but not found on your system.",
          solution:
            "Please install NVIDIA CUDA Toolkit 12.1 from nvidia.com/cuda-downloads. Ensure you have a compatible NVIDIA GPU.",
        };
      case "GPU_DRIVER_MISSING":
        return {
          title: "NVIDIA GPU Drivers Missing",
          message:
            "NVIDIA GPU drivers are not installed or not functioning properly.",
          solution:
            "Please install the latest NVIDIA GPU drivers from nvidia.com/drivers and restart your computer.",
        };
      case "NO_NVIDIA_GPU":
        return {
          title: "NVIDIA GPU Required",
          message:
            "This application requires an NVIDIA graphics card but none was detected.",
          solution:
            "Erudi requires an NVIDIA GPU with CUDA support. Please use a computer with a compatible NVIDIA graphics card.",
        };
      case "GPU_INIT_FAILED":
        return {
          title: "GPU Initialization Failed",
          message: "The application could not initialize your NVIDIA GPU.",
          solution:
            "Update your NVIDIA GPU drivers from nvidia.com/drivers and restart your computer. Ensure no other GPU-intensive applications are running.",
        };
      case "EXIT":
        return {
          title: "Application Stopped Unexpectedly",
          message: "The application stopped running after it was working.",
          solution:
            "Try restarting Erudi. If this happens repeatedly, restart your computer or contact support.",
        };
      default:
        return {
          title: "Startup Error",
          message: errorMessage || `An unknown error occurred (${errorCode}).`,
          solution:
            "Try restarting the application. If the problem persists, contact support with the error details below.",
        };
    }
  };

  useEffect(() => {
    const api = window.electron;
    if (!api) return;

    // Get packaging status
    api
      .isPackaged()
      .then(setIsPackaged)
      .catch(() => setIsPackaged(false));

    const detachEvent = api.onBackendEvent((evt) => {
      if (!evt || !evt.event) return;
      switch (evt.event) {
        case "starting":
          setStatus("Initializing");
          break;
        case "preflight_issue":
          setIssues((prev) => [...prev, evt]);
          break;
        case "ready":
          setStatus("Ready! Loading interface...");
          setReady(true);
          break;
        case "startup_error":
          setError(evt);
          setStatus("Startup failed");
          break;
        case "backend_exit":
          if (!ready && !error) {
            setError({ code: "EXIT", message: "Backend exited unexpectedly" });
            setStatus("Backend stopped");
          }
          break;
        default:
          break;
      }
    });

    const detachLog = api.onBackendLog((line) => {
      setLogLines((prev) => [...prev.slice(-199), line.trim()]);
    });
    const detachErr = api.onBackendLogError((line) => {
      setLogLines((prev) => [...prev.slice(-199), "[ERR] " + line.trim()]);
    });

    return () => {
      detachEvent && detachEvent();
      detachLog && detachLog();
      detachErr && detachErr();
    };
  }, [ready, error]);

  const retry = () => {
    setStatus("Restarting backend");
    setIssues([]);
    setError(null);
    setReady(false);
    setShowLogs(false);
    setCopyStatus("idle");
    window.electron?.restartBackend();
  };

  const copyLogsToClipboard = async () => {
    if (!error || copyStatus === "copying") return;

    setCopyStatus("copying");

    try {
      const errorDetails = {
        timestamp: new Date().toISOString(),
        errorCode: error?.code || "UNKNOWN",
        errorMessage: error?.message || "No error message",
        logs: logLines.slice(-100), // Last 100 log lines
      };

      const logText = `Erudi Error Report
Generated: ${errorDetails.timestamp}
Error Code: ${errorDetails.errorCode}
Error Message: ${errorDetails.errorMessage}

Technical Logs:
${errorDetails.logs.join("\n")}`;

      await navigator.clipboard.writeText(logText);
      setCopyStatus("copied");

      // Reset after 2 seconds
      setTimeout(() => {
        setCopyStatus("idle");
      }, 2000);
    } catch (err) {
      console.error("Failed to copy logs:", err);
      setCopyStatus("error");

      // Reset after 2 seconds
      setTimeout(() => {
        setCopyStatus("idle");
      }, 2000);
    }
  };

  const sendErrorReport = async () => {
    if (isSending) return;
    setIsSending(true);
    setSendStatus("sending");

    try {
      const errorDetails = {
        timestamp: new Date().toISOString(),
        errorCode: error?.code || "UNKNOWN",
        errorMessage: error?.message || "No error message",
        logs: logLines.slice(-100).join("\n"), // Last 100 log lines as string
      };

      const logReport = `Erudi Error Report
Generated: ${errorDetails.timestamp}
Error Code: ${errorDetails.errorCode}
Error Message: ${errorDetails.errorMessage}

Technical Logs:
${errorDetails.logs}`;

      const formDataToSend = new FormData();
      formDataToSend.append("name", "Erudi User");
      formDataToSend.append("email", userEmail);
      formDataToSend.append("company", userCompany || "No company provided");
      formDataToSend.append("reason", "support");
      formDataToSend.append("message", logReport);
      formDataToSend.append("timestamp", errorDetails.timestamp);
      formDataToSend.append("type", "error_report"); // Distinguish from regular contact submissions

      const response = await fetch(CONTACT_GOOGLE_SCRIPT_URL, {
        method: "POST",
        body: formDataToSend,
      });

      if (response.ok) {
        setSendStatus("success");
        setTimeout(() => {
          if (isDevelopment) {
            setIsModalOpen(false);
          } else {
            setShowReportForm(false);
          }
          setUserEmail("");
          setUserCompany("");
          setSendStatus("idle");
        }, 2000);
      } else {
        throw new Error("Failed to send error report");
      }
    } catch (err) {
      console.error("Error sending report:", err);
      setSendStatus("error");
      setTimeout(() => setSendStatus("idle"), 3000);
    } finally {
      setIsSending(false);
    }
  };

  const openContactPage = () => {
    window.open("https://erudi.app/contact", "_blank", "noopener,noreferrer");
  };

  const validateEmail = (email) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  const handleEmailChange = (e) => {
    const email = e.target.value;
    setUserEmail(email);

    if (email && !validateEmail(email)) {
      setEmailError("Please enter a valid email address");
    } else {
      setEmailError("");
    }
  };

  const errorInfo = error ? getErrorInfo(error.code, error.message) : null;

  useEffect(() => {
    if (ready || error) return;
    const interval = setInterval(() => {
      setDotCount((prev) => (prev % 3) + 1);
    }, 500);
    return () => clearInterval(interval);
  }, [ready, error]);

  return (
    <div
      className="fixed inset-0 flex flex-col items-center justify-center z-[9999] px-6"
      style={{ backgroundColor: "#02130e" }}
    >
      <img
        src={erudiLogo}
        alt="erudi Logo"
        className="w-auto h-24 mb-2 object-contain"
      />

      {/* Loading State */}
      {!ready && !error && (
        <div className="flex flex-col items-center">
          <div className="w-12 h-12 border-4 border-gray-200/20 border-t-green-500 rounded-full animate-spin mb-4" />
          <div className="text-gray-300 text-lg flex items-center">
            {status}
            <span className="inline-block" style={{ width: "1.5em" }}>
              {".".repeat(dotCount)}
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
          <div
            className="border border-gray-700 rounded-lg p-5 mb-4"
            style={{ backgroundColor: "#0a1612" }}
          >
            <div className="flex items-start mb-3">
              <div className="text-xl mr-3 mt-0.5" style={{ color: "#ff6b6b" }}>
                ⚠
              </div>
              <div>
                <h3
                  className="text-lg font-semibold mb-2"
                  style={{ color: "#e0e0e0" }}
                >
                  {errorInfo.title}
                </h3>
                <p className="text-gray-300 mb-3 leading-relaxed">
                  {errorInfo.message}
                </p>
                <div
                  className="border-l-3 border-gray-600 pl-4"
                  style={{ borderLeftColor: "#00c978" }}
                >
                  <p className="text-sm text-gray-300">{errorInfo.solution}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Console-style Error Log - Only in Development */}
          {isDevelopment && (
            <div
              className="border border-gray-700 rounded-lg overflow-hidden"
              style={{ backgroundColor: "#0a1612" }}
            >
              <div
                className="flex items-center justify-between px-4 py-2 border-b border-gray-700"
                style={{ backgroundColor: "#061009" }}
              >
                <div className="flex items-center space-x-2">
                  <div className="text-xs font-mono text-gray-400">
                    ERROR LOG
                  </div>
                  <div className="text-xs text-gray-500">•</div>
                  <div className="text-xs text-gray-500">
                    {error?.code || "UNKNOWN"}
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => setShowLogs(!showLogs)}
                    className="text-xs text-gray-400 hover:text-gray-200 transition-colors px-2 py-1 rounded hover:bg-gray-800"
                  >
                    {showLogs ? "COLLAPSE" : "EXPAND"}
                  </button>
                  <button
                    onClick={copyLogsToClipboard}
                    disabled={copyStatus === "copying"}
                    className="flex items-center text-xs text-gray-400 hover:text-gray-200 transition-colors px-2 py-1 rounded hover:bg-gray-800 disabled:opacity-50"
                  >
                    {copyStatus === "copying" && (
                      <div className="w-3 h-3 border border-gray-400 border-t-transparent rounded-full animate-spin mr-1" />
                    )}
                    {copyStatus === "copied" && (
                      <div className="mr-1" style={{ color: "#00c978" }}>
                        ✓
                      </div>
                    )}
                    {copyStatus === "error" && (
                      <div className="mr-1 text-red-400">✗</div>
                    )}
                    {copyStatus === "idle" && "COPY"}
                    {copyStatus === "copying" && "COPYING"}
                    {copyStatus === "copied" && "COPIED"}
                    {copyStatus === "error" && "FAILED"}
                  </button>
                </div>
              </div>

              {/* Console Content */}
              <div className="p-4">
                <div className="text-xs font-mono text-gray-300 mb-3 leading-relaxed">
                  <span className="text-red-400">error:</span>{" "}
                  {error?.message || "Unknown error occurred"}
                </div>

                <div
                  className={`border-t border-gray-700 pt-3 mt-3 transition-all duration-500 overflow-hidden ${
                    showLogs ? "max-h-64 opacity-100" : "max-h-0 opacity-0"
                  }`}
                  aria-hidden={!showLogs}
                >
                  <div className="text-xs font-mono text-gray-500 mb-2">
                    Stack trace:
                  </div>
                  <div className="bg-black/30 rounded p-3 max-h-40 overflow-auto">
                    <pre className="text-xs text-gray-400 whitespace-pre-wrap">
                      {logLines.slice(-50).join("\n") ||
                        "No detailed logs available"}
                    </pre>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Report Form - Only in Production */}
          {!isDevelopment && (
            <div
              className={`border border-gray-700 rounded-lg mt-4 overflow-hidden transition-all duration-500 ease-in-out ${
                showReportForm
                  ? "max-h-[500px] opacity-100 p-6"
                  : "max-h-0 opacity-0 p-0"
              }`}
              style={{ backgroundColor: "#0a1612" }}
            >
              <div
                className={`transition-opacity duration-300 ${
                  showReportForm ? "opacity-100" : "opacity-0"
                }`}
              >
                <h4 className="text-lg font-semibold text-white mb-4">
                  Report Issue
                </h4>
                <p className="text-sm text-gray-300 mb-6 leading-relaxed">
                  This will automatically send the error details to our team.
                  We'll need your email to follow up with a solution.
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                  <div className="transform transition-all duration-300 delay-100">
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Email <span className="text-emerald-400">*</span>
                    </label>
                    <input
                      type="email"
                      placeholder="your@email.com"
                      value={userEmail}
                      onChange={handleEmailChange}
                      required
                      className={`w-full px-4 py-3 bg-black/50 border rounded-xl text-white placeholder-gray-400 focus:outline-none focus:ring-2 transition-all duration-200 text-sm hover:bg-black/60 ${
                        emailError
                          ? "border-red-400 focus:border-red-400 focus:ring-red-400/20"
                          : "border-white/20 focus:border-emerald-400 focus:ring-emerald-400/20"
                      }`}
                    />
                    {emailError && (
                      <p className="text-red-400 text-xs mt-1 flex items-center">
                        <svg
                          className="w-3 h-3 mr-1"
                          fill="currentColor"
                          viewBox="0 0 20 20"
                        >
                          <path
                            fillRule="evenodd"
                            d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                            clipRule="evenodd"
                          />
                        </svg>
                        {emailError}
                      </p>
                    )}
                  </div>
                  <div className="transform transition-all duration-300 delay-200">
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Company (Optional)
                    </label>
                    <input
                      type="text"
                      placeholder="Your company"
                      value={userCompany}
                      onChange={(e) => setUserCompany(e.target.value)}
                      className="w-full px-4 py-3 bg-black/50 border border-white/20 rounded-xl text-white placeholder-gray-400 focus:outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-400/20 transition-all duration-200 text-sm hover:bg-black/60"
                    />
                  </div>
                </div>

                <div className="flex gap-3 transform transition-all duration-300 delay-300">
                  <button
                    onClick={() => {
                      setShowReportForm(false);
                      setTimeout(() => {
                        setUserEmail("");
                        setUserCompany("");
                        setEmailError("");
                        setSendStatus("idle");
                      }, 300);
                    }}
                    disabled={isSending}
                    className="px-6 py-3 border border-gray-600 text-gray-300 hover:bg-gray-800 hover:border-gray-500 rounded-xl font-medium transition-all duration-200 disabled:opacity-50 text-sm hover:scale-[1.02]"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={sendErrorReport}
                    disabled={
                      isSending ||
                      !userEmail.trim() ||
                      emailError ||
                      !validateEmail(userEmail)
                    }
                    className="px-6 py-3 bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-600/50 text-white rounded-xl font-medium transition-all duration-200 shadow-lg hover:shadow-emerald-600/25 flex items-center space-x-2 text-sm hover:scale-[1.02] disabled:hover:scale-100 disabled:opacity-50"
                  >
                    {isSending ? (
                      <>
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                        <span>Sending Report...</span>
                      </>
                    ) : (
                      <>
                        <svg
                          className="w-4 h-4"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                          />
                        </svg>
                        <span>Send Report</span>
                      </>
                    )}
                  </button>
                </div>

                {sendStatus === "success" && (
                  <div className="mt-6 p-4 bg-emerald-600/20 border border-emerald-600/30 rounded-xl animate-in slide-in-from-bottom-4 duration-500">
                    <p className="text-emerald-400 text-sm text-center flex items-center justify-center space-x-2">
                      <svg
                        className="w-5 h-5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M5 13l4 4L19 7"
                        />
                      </svg>
                      <span>
                        Report sent successfully! We'll look into this issue.
                      </span>
                    </p>
                  </div>
                )}
                {sendStatus === "error" && (
                  <div className="mt-6 p-4 bg-red-600/20 border border-red-600/30 rounded-xl animate-in slide-in-from-bottom-4 duration-500">
                    <p className="text-red-400 text-sm text-center">
                      Failed to send report. Please try again or contact us
                      directly at erudipro@gmail.com
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-3 mt-4">
            <button
              onClick={retry}
              className="px-4 py-2 rounded-md font-medium transition-all duration-200 hover:scale-105"
              style={{
                backgroundColor: "#00c978",
                color: "#02130e",
              }}
            >
              Retry Startup
            </button>

            {!isDevelopment && (
              // Production mode - Report Issue button (inline form)
              <button
                onClick={() => setShowReportForm(true)}
                disabled={showReportForm}
                className="px-4 py-2 rounded-md border border-gray-600 text-gray-300 hover:bg-gray-800 font-medium transition-colors disabled:opacity-50"
              >
                Report Issue
              </button>
            )}
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

      {/* Modal for Sending Error Report - Not used anymore */}
      {false && isDevelopment && isModalOpen && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 px-4">
          <div className="bg-[#272727]/90 backdrop-blur-lg p-8 rounded-2xl shadow-2xl w-full max-w-md border border-white/10">
            <h3 className="text-xl font-semibold text-white mb-4">
              Send Error Report
            </h3>
            <p className="text-sm text-gray-300 mb-6 leading-relaxed">
              This will automatically send the error details to our team.
              Providing your email is optional but helps us follow up if needed.
            </p>

            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Email (Optional)
              </label>
              <input
                type="email"
                placeholder="your@email.com"
                value={userEmail}
                onChange={(e) => setUserEmail(e.target.value)}
                className="w-full px-4 py-3 bg-black/50 border border-white/20 rounded-xl text-white placeholder-gray-400 focus:outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-400/20 transition"
              />
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => {
                  setIsModalOpen(false);
                  setUserEmail("");
                  setSendStatus("idle");
                }}
                disabled={isSending}
                className="flex-1 px-4 py-3 border border-gray-600 text-gray-300 hover:bg-gray-800 rounded-xl font-medium transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={sendErrorReport}
                disabled={isSending}
                className="flex-1 bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-600/50 text-white px-4 py-3 rounded-xl font-medium transition-colors shadow-lg flex items-center justify-center space-x-2"
              >
                {isSending ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    <span>Sending...</span>
                  </>
                ) : (
                  <span>Send Report</span>
                )}
              </button>
            </div>

            {sendStatus === "success" && (
              <div className="mt-4 p-3 bg-emerald-600/20 border border-emerald-600/30 rounded-lg">
                <p className="text-emerald-400 text-sm text-center">
                  ✓ Report sent successfully! We'll look into this issue.
                </p>
              </div>
            )}
            {sendStatus === "error" && (
              <div className="mt-4 p-3 bg-red-600/20 border border-red-600/30 rounded-lg">
                <p className="text-red-400 text-sm text-center">
                  Failed to send report. Please try again or contact us directly
                  at erudipro@gmail.com
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
