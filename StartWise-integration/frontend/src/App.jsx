// src/App.jsx
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { AppProvider } from './context/AppContext'
import Dashboard from './pages/Dashboard'
import AgentPage from './pages/AgentPage'
import SecurityToast from './components/SecurityToast'

function App() {
  return (
    <AppProvider>
      <Router>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/agent/:agentId" element={<AgentPage />} />
        </Routes>
      </Router>
      <SecurityToast />
    </AppProvider>
  )
}

export default App
