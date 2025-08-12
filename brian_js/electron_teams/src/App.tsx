import React from 'react'
import { Routes, Route } from 'react-router-dom'
import Index from '@/pages/index'

function App() {
  return (
    <div className="h-screen w-full bg-background text-foreground">
      <Routes>
        <Route path="/" element={<Index />} />
      </Routes>
    </div>
  )
}

export default App