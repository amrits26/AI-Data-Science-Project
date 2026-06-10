import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import { ModeProvider } from './context/ModeContext'
import './globals.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ModeProvider>
      <App />
    </ModeProvider>
  </React.StrictMode>,
)
