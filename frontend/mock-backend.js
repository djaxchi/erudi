const express = require('express');
const cors = require('cors');
const path = require('path');

const app = express();
const PORT = 8000;

// Middleware
app.use(cors());
app.use(express.json());

// Mock data
const mockConversations = [
  {
    id: 1,
    title: "Welcome to Erudi",
    llm_id: "1",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  }
];

const mockMessages = [
  {
    id: 1,
    conversation_id: 1,
    role: "assistant",
    content: "Hello! Welcome to Erudi. I'm here to help you with your questions.",
    created_at: new Date().toISOString()
  }
];

const mockLlms = [
  {
    id: "1",
    name: "Mistral 7B Instruct",
    model_name: "mistralai/Mistral-7B-Instruct-v0.3",
    size: "7B",
    status: "ready",
    description: "A powerful 7B parameter instruction-following model",
    is_local: true
  },
  {
    id: "2", 
    name: "Gemma 2B",
    model_name: "google/gemma-2b-it",
    size: "2B",
    status: "available",
    description: "Google's lightweight conversational AI model",
    is_local: false
  }
];

const mockHardwareInfo = {
  cpu: "Apple M1 Pro",
  memory: "16 GB",
  gpu: "Apple M1 Pro GPU",
  storage: "512 GB SSD",
  recommended_max_model_size: "7B"
};

// Health check endpoint
app.get('/main_window/health', (req, res) => {
  res.json({ status: 'ok', message: 'Mock backend is running' });
});

// Welcome popup
app.get('/main_window/welcome-popup', (req, res) => {
  res.json({ show_popup: false });
});

// Hardware endpoints
app.get('/hardware/app_startup', (req, res) => {
  res.json(mockHardwareInfo);
});

app.get('/hardware/training', (req, res) => {
  res.json(mockHardwareInfo);
});

// LLM endpoints
app.get('/main_window/llms/local', (req, res) => {
  const localLlms = mockLlms.filter(llm => llm.is_local);
  res.json(localLlms);
});

app.get('/main_window/llms/remote', (req, res) => {
  const remoteLlms = mockLlms.filter(llm => !llm.is_local);
  res.json(remoteLlms);
});

app.delete('/main_window/llms/:id', (req, res) => {
  res.json({ success: true, message: 'Model deleted successfully' });
});

app.post('/main_window/llms/local', (req, res) => {
  // Mock download progress
  const newModel = {
    id: Date.now().toString(),
    name: req.body.name || "New Model",
    model_name: req.body.model_name || "unknown/model",
    size: req.body.size || "Unknown",
    status: "downloading",
    is_local: true
  };
  
  // Simulate download progress
  let progress = 0;
  const interval = setInterval(() => {
    progress += 10;
    if (progress >= 100) {
      clearInterval(interval);
      newModel.status = "ready";
    }
  }, 1000);
  
  res.json(newModel);
});

// Conversation endpoints
app.get('/conversations', (req, res) => {
  res.json(mockConversations);
});

app.post('/conversations', (req, res) => {
  const newConversation = {
    id: Date.now(),
    title: req.body.title || "New Conversation",
    llm_id: req.body.llm_id || "1",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  };
  mockConversations.push(newConversation);
  res.json(newConversation);
});

app.put('/conversations/:id', (req, res) => {
  const id = parseInt(req.params.id);
  const conversation = mockConversations.find(c => c.id === id);
  if (conversation) {
    Object.assign(conversation, req.body);
    conversation.updated_at = new Date().toISOString();
    res.json(conversation);
  } else {
    res.status(404).json({ error: 'Conversation not found' });
  }
});

app.get('/conversations/:id/fetch_messages', (req, res) => {
  const conversationId = parseInt(req.params.id);
  const messages = mockMessages.filter(m => m.conversation_id === conversationId);
  res.json(messages);
});

app.post('/conversations/:id/query', (req, res) => {
  const conversationId = parseInt(req.params.id);
  const userMessage = req.body.message;
  
  // Add user message
  const newUserMessage = {
    id: Date.now(),
    conversation_id: conversationId,
    role: "user",
    content: userMessage,
    created_at: new Date().toISOString()
  };
  mockMessages.push(newUserMessage);
  
  // Create a streaming response
  res.setHeader('Content-Type', 'text/plain');
  res.setHeader('Transfer-Encoding', 'chunked');
  
  const responses = [
    "Hello! This is a mock response from the backend. ",
    "I'm simulating the streaming behavior you'd expect from a real LLM. ",
    "Each chunk is sent progressively to demonstrate the typing effect. ",
    "This allows you to test the frontend without a real backend running!"
  ];
  
  let index = 0;
  const interval = setInterval(() => {
    if (index < responses.length) {
      res.write(responses[index]);
      index++;
    } else {
      clearInterval(interval);
      
      // Add assistant message to mock storage
      const assistantMessage = {
        id: Date.now() + 1,
        conversation_id: conversationId,
        role: "assistant", 
        content: responses.join(''),
        created_at: new Date().toISOString()
      };
      mockMessages.push(assistantMessage);
      
      res.end();
    }
  }, 500);
});

app.post('/conversations/:id/generate_title', (req, res) => {
  const titles = [
    "General Discussion",
    "Technical Questions", 
    "Project Planning",
    "Code Review",
    "Feature Discussion"
  ];
  const randomTitle = titles[Math.floor(Math.random() * titles.length)];
  res.json({ title: randomTitle });
});

app.post('/conversations/:id/store_error_message', (req, res) => {
  res.json({ success: true });
});

app.delete('/conversations/delete_bulk', (req, res) => {
  res.json({ success: true, deleted_count: req.body.conversation_ids?.length || 0 });
});

// Arena endpoints
app.post('/arena/:llmId/query', (req, res) => {
  res.setHeader('Content-Type', 'text/plain');
  res.setHeader('Transfer-Encoding', 'chunked');
  
  const arenaResponse = `This is a mock arena response from model ${req.params.llmId}. The arena feature allows you to compare different models side by side.`;
  
  // Simulate streaming
  const words = arenaResponse.split(' ');
  let wordIndex = 0;
  
  const interval = setInterval(() => {
    if (wordIndex < words.length) {
      res.write(words[wordIndex] + ' ');
      wordIndex++;
    } else {
      clearInterval(interval);
      res.end();
    }
  }, 200);
});

// Training endpoints
app.get('/training/:id/status', (req, res) => {
  res.json({ 
    status: 'completed',
    progress: 100,
    eta: null
  });
});

// Knowledge base endpoints (basic responses)
app.use('/knowledge_base', (req, res) => {
  res.json({ success: true, data: [], message: 'Knowledge base endpoint' });
});

// Start server
const server = app.listen(PORT, '127.0.0.1', () => {
  console.log(`Mock backend server running on http://127.0.0.1:${PORT}`);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('Shutting down mock backend server...');
  server.close(() => {
    console.log('Mock backend server stopped');
    process.exit(0);
  });
});

process.on('SIGINT', () => {
  console.log('Shutting down mock backend server...');
  server.close(() => {
    console.log('Mock backend server stopped');
    process.exit(0);
  });
});

module.exports = app;