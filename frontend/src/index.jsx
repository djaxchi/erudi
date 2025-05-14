import * as React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './index.css';

setTimeout(() => {
  const loader = document.getElementById('loader');
  const body = document.body;

  if (loader) {
    loader.style.opacity = '0';
    loader.style.transition = 'opacity 0.5s ease';

    setTimeout(() => {
      loader.style.display = 'none';
      const root = createRoot(body);
      root.render(<App />);
    }, 0); // Wait for fade-out
  } else {
    const root = createRoot(body);
    root.render(<App />);
  }
}, 0); // Delay in ms
