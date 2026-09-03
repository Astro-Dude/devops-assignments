import { useState } from 'react'

export default function App() {
  const [count, setCount] = useState(0)

  return (
    <div style={{
      fontFamily: 'system-ui, sans-serif',
      textAlign: 'center',
      paddingTop: '80px',
      background: '#f6f8fa',
      minHeight: '100vh',
    }}>
      <h1>Hello World</h1>
      <p>Served by a <strong>React</strong> app inside Docker</p>
      <p>Built with Vite, served as static files by Nginx</p>
      <button onClick={() => setCount(c => c + 1)} style={{
        padding: '10px 20px',
        fontSize: '16px',
        cursor: 'pointer',
        borderRadius: '6px',
        border: '1px solid #ccc',
      }}>
        Clicked {count} times
      </button>
      <p style={{ color: '#666', fontSize: '14px' }}>
        The button proves React is really running, not just static HTML.
      </p>
    </div>
  )
}
