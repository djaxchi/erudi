# Exception Handling Guide

Complete guide for working with Erudi's exception system, covering both backend (Python/FastAPI) and frontend (React/Electron) development.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Backend: Python Exception Handling](#backend-python-exception-handling)
3. [Frontend: Error Handling](#frontend-error-handling)
4. [Exception Flow](#exception-flow)
5. [Best Practices](#best-practices)
6. [Testing Exceptions](#testing-exceptions)

---

## Architecture Overview

Erudi uses a **hierarchical exception system** that provides:

- ✅ **Type-safe error handling** with custom exception classes
- ✅ **Structured error responses** with HTTP status codes and custom error codes
- ✅ **Automatic logging** via structured logger
- ✅ **FastAPI integration** for JSON error responses
- ✅ **Client-friendly error messages** with remediation hints

### Exception Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Backend Service/Repository                              │
│    └─> Raises domain-specific exception                    │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. FastAPI Exception Handler                               │
│    └─> Catches AppBaseException                            │
│    └─> Logs error with structured logger                   │
│    └─> Returns JSON response                               │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Frontend API Service                                     │
│    └─> Receives error response                             │
│    └─> Extracts detail message                             │
│    └─> Displays to user or handles programmatically        │
└─────────────────────────────────────────────────────────────┘
```

---

## Backend: Python Exception Handling

### Exception Hierarchy

All custom exceptions inherit from `AppBaseException`:

```python
AppBaseException (base class)
├── ModelNotFoundException (404, MODEL_NOT_FOUND)
├── InvalidInputException (422, INVALID_INPUT)
├── DatabaseException (500, DATABASE_ERROR)
├── FileSystemException (500, FILESYSTEM_ERROR)
├── FAISSException (500, FAISS_ERROR)
├── HuggingFaceAPIException (503, HUGGINGFACE_API_ERROR)
├── ModelLoadingException (500, MODEL_LOADING_ERROR)
├── QuantizationException (500, QUANTIZATION_ERROR)
├── GenerationException (500, GENERATION_ERROR)
├── KnowledgeBaseNotFoundException (404, KB_NOT_FOUND)
├── KnowledgeBaseCorruptedException (500, KB_CORRUPTED)
├── ConversationNotFoundException (404, CONVERSATION_NOT_FOUND)
├── MessageNotFoundException (404, MESSAGE_NOT_FOUND)
├── InsufficientMemoryException (507, INSUFFICIENT_MEMORY)
├── UnsupportedPlatformException (501, UNSUPPORTED_PLATFORM)
├── DownloadJobNotFoundException (404, DOWNLOAD_JOB_NOT_FOUND)
├── TokenizationException (500, TOKENIZATION_ERROR)
├── ConfigurationException (500, CONFIGURATION_ERROR)
├── EngineException (500, LLM_ENGINE_FAILURE)
└── EmbeddingError (500, EMBEDDING_FAILURE)
```

### Using Exceptions in Code

#### 1. Import Required Exceptions

```python
from src.core.exceptions import (
    ModelNotFoundException,
    DatabaseException,
    InvalidInputException,
)
```

#### 2. Raise Exceptions with Context

**Resource Not Found (404):**
```python
llm = db.query(Llm).filter(Llm.id == llm_id).first()
if not llm:
    raise ModelNotFoundException(f"LLM {llm_id}")
```

**Invalid User Input (422):**
```python
if not payload.question or not payload.question.strip():
    raise InvalidInputException("question")
```

**Database Errors (500):**
```python
try:
    db.add(conversation)
    db.commit()
except SQLAlchemyError as e:
    raise DatabaseException(
        "Failed to create conversation",
        trace=str(e)
    )
```

**File System Errors (500):**
```python
try:
    with open(model_path, 'r') as f:
        config = json.load(f)
except (FileNotFoundError, PermissionError, OSError) as e:
    raise FileSystemException(
        f"Cannot load model config from {model_path}",
        trace=str(e)
    )
```

#### 3. Catch and Re-raise Specific Exceptions

**Always catch specific exceptions, never bare `except:`**

```python
# ✅ GOOD: Catch specific exceptions
try:
    llm = self.get_llm_by_id(llm_id)
    self.update_metadata(llm)
except ModelNotFoundException:
    raise  # Let it bubble up
except DatabaseException:
    raise  # Let it bubble up
except Exception as e:
    # Catch unexpected errors and wrap
    raise DatabaseException(
        "Unexpected error during update",
        trace=str(e)
    )

# ❌ BAD: Bare except catches everything
try:
    dangerous_operation()
except:
    pass  # NEVER DO THIS
```

#### 4. Exception Parameters

Most exceptions accept these parameters:

```python
class ModelNotFoundException(AppBaseException):
    def __init__(self, model_id: str, trace: Optional[str] = None):
        super().__init__(
            message=f"Model {model_id} not found",
            status_code=status.HTTP_404_NOT_FOUND,
            erudi_code="MODEL_NOT_FOUND",
            trace=trace
        )
```

- `message`: Human-readable error description
- `status_code`: HTTP status code (use `fastapi.status` constants)
- `erudi_code`: Custom error code for client-side handling
- `trace`: Optional stack trace or additional context

### Exception Categories by Use Case

#### Resource Not Found (404)
Use when a requested entity doesn't exist:
```python
# Models
raise ModelNotFoundException(f"LLM {llm_id}")

# Conversations
raise ConversationNotFoundException(conversation_id)

# Messages
raise MessageNotFoundException(message_id)

# Knowledge Bases
raise KnowledgeBaseNotFoundException(kb_id)

# Download Jobs
raise DownloadJobNotFoundException(job_id)
```

#### Client Input Validation (422)
Use for invalid or missing user input:
```python
# Missing required field
raise InvalidInputException("model_name")

# Invalid format
raise InvalidInputException("temperature (must be 0.0-2.0)")

# Invalid state
raise InvalidInputException("Cannot delete LLM while downloading")
```

#### Server Errors (500)
Use for internal failures:

**Database:**
```python
raise DatabaseException(
    "Could not save conversation",
    trace=str(e)
)
```

**File System:**
```python
raise FileSystemException(
    f"Cannot write to {path}",
    trace=str(e)
)
```

**Model Operations:**
```python
# Loading
raise ModelLoadingException(
    model_path=model_path,
    trace=str(e)
)

# Quantization
raise QuantizationException(
    f"4-bit quantization failed for {model_path}",
    trace=str(e)
)

# Generation
raise GenerationException(
    message="Token generation failed",
    trace=str(e)
)

# Tokenization
raise TokenizationException(
    f"Cannot tokenize input: {text[:50]}...",
    trace=str(e)
)
```

**Vector Operations:**
```python
# FAISS index
raise FAISSException(
    "Failed to build FAISS index",
    trace=str(e)
)

# Embeddings
raise EmbeddingError(
    "Embedding model initialization failed",
    trace=str(e)
)

# Knowledge base corruption
raise KnowledgeBaseCorruptedException(kb_id)
```

#### Service Unavailable (503)
Use when external services fail:
```python
raise HuggingFaceAPIException(
    "Cannot fetch model from HuggingFace Hub",
    trace=str(e)
)
```

#### Not Implemented (501)
Use for unsupported operations:
```python
raise UnsupportedPlatformException("Windows", "MLX engine")
```

#### Insufficient Resources (507)
Use when system runs out of memory:
```python
raise InsufficientMemoryException(
    "model loading",
    trace=str(e)
)
```

### Repository Pattern

In repositories, raise exceptions but **don't commit/rollback**:

```python
class ConversationRepository:
    def get_conversation_by_id(self, conversation_id: int) -> Conversation:
        try:
            conversation = self.db.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            
            if not conversation:
                raise ConversationNotFoundException(conversation_id)
                
            return conversation
            
        except ConversationNotFoundException:
            raise  # Let caller handle
        except SQLAlchemyError as e:
            raise DatabaseException(
                "Could not retrieve conversation",
                trace=str(e)
            )
```

### Service Pattern

In services, handle transaction control:

```python
class ConversationService:
    def create_conversation(self, llm_id: int, name: str) -> Conversation:
        try:
            conversation = self.conv_repo.create_conversation(
                llm_id=llm_id,
                name=name
            )
            self.db.commit()
            return conversation
            
        except (ModelNotFoundException, DatabaseException):
            self.db.rollback()
            raise  # Re-raise to endpoint
        except Exception as e:
            self.db.rollback()
            raise DatabaseException(
                "Unexpected error creating conversation",
                trace=str(e)
            )
```

### Endpoint Pattern

In endpoints, let exceptions bubble to FastAPI handler:

```python
@router.get("/{llm_id}", response_model=LLMResponse)
async def get_llm_by_id(
    llm_id: int,
    llm_repo: Llm_Repository = Depends(get_llm_repository)
):
    """Get LLM details by ID.
    
    Raises:
        ModelNotFoundException: If LLM not found.
        DatabaseException: If database error occurs.
    """
    # No try/except needed - FastAPI handler catches exceptions
    llm = llm_repo.get_by_id(llm_id)
    if not llm:
        raise ModelNotFoundException(f"LLM {llm_id}")
    return llm
```

### Logging

All exceptions are **automatically logged** by the FastAPI exception handler:

```python
# In src/core/exceptions.py
async def app_base_exception_handler(request: Request, exc: AppBaseException):
    logger.error(
        f"AppBaseException: {exc.message}",
        extra={
            "error_code": exc.erudi_code,
            "status_code": exc.status_code,
            "trace": exc.trace,
            "path": request.url.path,
        }
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message}
    )
```

**You don't need to log manually** unless you want additional context:

```python
# ✅ Exception auto-logged by handler
raise DatabaseException("Could not save model")

# ✅ Add extra context if needed
logger.error(f"Database error for model {model_id}")
raise DatabaseException("Could not save model")
```

---

## Frontend: Error Handling

### Error Response Format

Backend returns errors in this format:

```json
{
  "detail": "Model with ID 42 not found"
}
```

HTTP status codes match exception types:
- `404`: Resource not found
- `422`: Invalid input
- `500`: Server error
- `503`: Service unavailable
- `507`: Insufficient memory

### Handling Errors in API Services

#### Basic Pattern

```javascript
// src/services/llmService.js

export const getLLMById = async (llmId) => {
  try {
    const response = await fetch(`${API_BASE_URL}/llms/${llmId}`);
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to fetch LLM');
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error fetching LLM:', error);
    throw error; // Re-throw for component to handle
  }
};
```

#### Advanced Pattern with Error Types

```javascript
// src/utils/apiErrors.js

export class APIError extends Error {
  constructor(message, statusCode, errorCode) {
    super(message);
    this.statusCode = statusCode;
    this.errorCode = errorCode;
    this.name = 'APIError';
  }
  
  isNotFound() {
    return this.statusCode === 404;
  }
  
  isValidationError() {
    return this.statusCode === 422;
  }
  
  isServerError() {
    return this.statusCode >= 500;
  }
}

export const handleAPIError = async (response) => {
  const error = await response.json();
  throw new APIError(
    error.detail || 'An error occurred',
    response.status,
    error.error_code
  );
};

// Usage in service
export const deleteLLM = async (llmId) => {
  const response = await fetch(`${API_BASE_URL}/llms/${llmId}`, {
    method: 'DELETE',
  });
  
  if (!response.ok) {
    await handleAPIError(response);
  }
  
  return await response.json();
};
```

### Handling Errors in React Components

#### Using Toast Notifications

```javascript
import { toast } from 'react-toastify';
import { getLLMById } from '../services/llmService';

function LLMDetails({ llmId }) {
  const [llm, setLLM] = useState(null);
  
  useEffect(() => {
    const fetchLLM = async () => {
      try {
        const data = await getLLMById(llmId);
        setLLM(data);
      } catch (error) {
        // Display user-friendly error
        toast.error(error.message || 'Failed to load model details');
      }
    };
    
    fetchLLM();
  }, [llmId]);
  
  return llm ? <div>{llm.name}</div> : <div>Loading...</div>;
}
```

#### Error States in UI

```javascript
function LLMList() {
  const [llms, setLLMs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    const fetchLLMs = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await getAllLLMs();
        setLLMs(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    
    fetchLLMs();
  }, []);
  
  if (loading) return <Spinner />;
  if (error) return <ErrorMessage message={error} />;
  
  return (
    <div>
      {llms.map(llm => <LLMCard key={llm.id} llm={llm} />)}
    </div>
  );
}
```

#### Specific Error Handling

```javascript
import { APIError } from '../utils/apiErrors';

async function handleDeleteLLM(llmId) {
  try {
    await deleteLLM(llmId);
    toast.success('Model deleted successfully');
    navigate('/llms');
  } catch (error) {
    if (error instanceof APIError) {
      if (error.isNotFound()) {
        toast.error('Model not found');
      } else if (error.isValidationError()) {
        toast.warning('Cannot delete model while downloading');
      } else if (error.isServerError()) {
        toast.error('Server error. Please try again later.');
      }
    } else {
      toast.error('Network error. Please check your connection.');
    }
  }
}
```

### Error Boundaries (React)

Catch rendering errors:

```javascript
// src/components/ErrorBoundary.jsx

import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('React Error Boundary caught:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-container">
          <h2>Something went wrong</h2>
          <p>{this.state.error?.message}</p>
          <button onClick={() => window.location.reload()}>
            Reload Application
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;

// Usage in App.jsx
<ErrorBoundary>
  <YourApp />
</ErrorBoundary>
```

---

## Exception Flow

### Example: Creating a Conversation

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Frontend Component                                       │
│    onClick={() => createConversation(llmId, name)}          │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Frontend Service (conversationService.js)               │
│    POST /erudi/conversations/                               │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. FastAPI Endpoint (conversations/endpoints.py)           │
│    @router.post("/")                                        │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Service Layer (ConversationService)                     │
│    create_conversation(llm_id, name)                        │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Repository Layer (ConversationRepository)               │
│    get_llm_by_id(llm_id) → NOT FOUND                        │
│    raise ModelNotFoundException(llm_id)                     │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. FastAPI Exception Handler                               │
│    Catches ModelNotFoundException                           │
│    Logs: "Model 42 not found"                              │
│    Returns: {"detail": "Model 42 not found"} (404)         │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. Frontend Service (catch block)                          │
│    throw new Error("Model 42 not found")                   │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│ 8. Frontend Component (catch block)                        │
│    toast.error("Model 42 not found")                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Best Practices

### Backend

#### ✅ DO:

1. **Use specific exception types**
   ```python
   raise ModelNotFoundException(f"LLM {llm_id}")
   ```

2. **Include context in error messages**
   ```python
   raise FileSystemException(
       f"Cannot read index from {index_path}",
       trace=str(e)
   )
   ```

3. **Document exceptions in docstrings**
   ```python
   def get_llm(llm_id: int) -> Llm:
       """Get LLM by ID.
       
       Raises:
           ModelNotFoundException: If LLM not found.
           DatabaseException: If database error occurs.
       """
   ```

4. **Catch and re-raise specific exceptions**
   ```python
   try:
       operation()
   except ModelNotFoundException:
       raise  # Let it bubble up
   except Exception as e:
       raise DatabaseException("Unexpected error", trace=str(e))
   ```

5. **Use trace parameter for debugging**
   ```python
   except Exception as e:
       raise DatabaseException(
           "Operation failed",
           trace=str(e)  # Include original error
       )
   ```

#### ❌ DON'T:

1. **Don't use bare except**
   ```python
   # ❌ BAD
   try:
       operation()
   except:
       pass
   ```

2. **Don't raise generic exceptions**
   ```python
   # ❌ BAD
   raise Exception("Model not found")
   
   # ✅ GOOD
   raise ModelNotFoundException(f"LLM {llm_id}")
   ```

3. **Don't catch exceptions you can't handle**
   ```python
   # ❌ BAD
   try:
       operation()
   except Exception as e:
       logger.error(f"Error: {e}")
       # What now? Error is lost!
   ```

4. **Don't log and raise (double logging)**
   ```python
   # ❌ BAD - exception handler will log again
   logger.error("Model not found")
   raise ModelNotFoundException(llm_id)
   
   # ✅ GOOD - let handler log
   raise ModelNotFoundException(llm_id)
   ```

5. **Don't include sensitive data in error messages**
   ```python
   # ❌ BAD
   raise DatabaseException(f"Connection failed: password={db_password}")
   
   # ✅ GOOD
   raise DatabaseException("Database connection failed")
   ```

### Frontend

#### ✅ DO:

1. **Handle all promise rejections**
   ```javascript
   fetchData().catch(error => {
     toast.error(error.message);
   });
   ```

2. **Show user-friendly messages**
   ```javascript
   toast.error('Failed to delete model');
   // Not: "SQLAlchemyError: constraint violation..."
   ```

3. **Use loading and error states**
   ```javascript
   const [loading, setLoading] = useState(false);
   const [error, setError] = useState(null);
   ```

4. **Provide retry mechanisms**
   ```javascript
   <button onClick={() => refetch()}>Retry</button>
   ```

5. **Log errors for debugging**
   ```javascript
   console.error('API Error:', error);
   ```

#### ❌ DON'T:

1. **Don't ignore errors silently**
   ```javascript
   // ❌ BAD
   fetchData().catch(() => {});
   ```

2. **Don't show technical error details to users**
   ```javascript
   // ❌ BAD
   toast.error(error.stack);
   ```

3. **Don't forget to handle network errors**
   ```javascript
   // ✅ GOOD
   try {
     await fetchData();
   } catch (error) {
     if (error.message === 'Failed to fetch') {
       toast.error('Network error. Check your connection.');
     }
   }
   ```

---

## Testing Exceptions

### Backend Tests

```python
import pytest
from src.core.exceptions import ModelNotFoundException, DatabaseException

def test_model_not_found():
    """Test that ModelNotFoundException is raised when model doesn't exist."""
    with pytest.raises(ModelNotFoundException) as exc_info:
        repo.get_llm_by_id(999)
    
    assert "999" in str(exc_info.value)
    assert exc_info.value.status_code == 404

def test_database_error_handling():
    """Test that database errors are properly wrapped."""
    with pytest.raises(DatabaseException) as exc_info:
        repo.create_conversation_with_invalid_data()
    
    assert "Could not create conversation" in str(exc_info.value)
    assert exc_info.value.trace is not None
```

### Frontend Tests

```javascript
import { render, screen, waitFor } from '@testing-library/react';
import { getLLMById } from './llmService';

jest.mock('./llmService');

test('displays error message when API fails', async () => {
  getLLMById.mockRejectedValue(new Error('Model not found'));
  
  render(<LLMDetails llmId={42} />);
  
  await waitFor(() => {
    expect(screen.getByText(/Model not found/i)).toBeInTheDocument();
  });
});

test('retries on network error', async () => {
  getLLMById
    .mockRejectedValueOnce(new Error('Network error'))
    .mockResolvedValueOnce({ id: 42, name: 'Test Model' });
  
  const { rerender } = render(<LLMDetails llmId={42} />);
  
  await waitFor(() => {
    expect(screen.getByText(/Network error/i)).toBeInTheDocument();
  });
  
  // Trigger retry
  fireEvent.click(screen.getByText(/Retry/i));
  
  await waitFor(() => {
    expect(screen.getByText(/Test Model/i)).toBeInTheDocument();
  });
});
```

---

## Quick Reference

### Common Exception Patterns

| Scenario | Exception | Example |
|----------|-----------|---------|
| Model not found | `ModelNotFoundException` | `raise ModelNotFoundException(f"LLM {llm_id}")` |
| Invalid input | `InvalidInputException` | `raise InvalidInputException("temperature")` |
| Database error | `DatabaseException` | `raise DatabaseException("Save failed", trace=str(e))` |
| File not found | `FileSystemException` | `raise FileSystemException(f"Cannot read {path}", trace=str(e))` |
| Model loading fails | `ModelLoadingException` | `raise ModelLoadingException(model_path, trace=str(e))` |
| Generation fails | `GenerationException` | `raise GenerationException("Token gen failed", trace=str(e))` |
| Out of memory | `InsufficientMemoryException` | `raise InsufficientMemoryException("model loading")` |
| KB not found | `KnowledgeBaseNotFoundException` | `raise KnowledgeBaseNotFoundException(kb_id)` |
| Download job missing | `DownloadJobNotFoundException` | `raise DownloadJobNotFoundException(job_id)` |

### Frontend Error Handling Checklist

- [ ] Wrap API calls in try/catch
- [ ] Display user-friendly error messages
- [ ] Implement loading and error states
- [ ] Log errors to console for debugging
- [ ] Handle network errors separately
- [ ] Provide retry mechanisms
- [ ] Use toast notifications for transient errors
- [ ] Use error boundaries for rendering errors

---

## Additional Resources

- [FastAPI Exception Handling](https://fastapi.tiangolo.com/tutorial/handling-errors/)
- [Python Exception Docs](https://docs.python.org/3/tutorial/errors.html)
- [React Error Boundaries](https://react.dev/reference/react/Component#catching-rendering-errors-with-an-error-boundary)
- Backend exceptions: `backend/src/core/exceptions.py`
- Example usage: Search for `raise` in `backend/src/domains/`

---

**Need help?** Check the exception hierarchy in `src/core/exceptions.py` or ask in the team chat!
