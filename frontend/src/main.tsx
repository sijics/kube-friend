import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'

// Mount the React app into the <div id="root"> in index.html.
// StrictMode runs extra checks in development to catch common mistakes.
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
