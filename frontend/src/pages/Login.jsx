import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Lock, User } from 'lucide-react';

const Login = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await login(username, password);
      navigate('/');
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="flex-center-screen min-h-screen bg-[var(--bg-main)]">
      <div className="glass-panel p-8 rounded-[var(--radius-xl)] w-full max-w-md shadow-[var(--shadow-lg)] m-4">
        <h2 className="text-2xl font-semibold mb-6 text-center text-[var(--text-primary)]">
          Welcome to <span className="header-title-highlight">Legal RAG</span>
        </h2>
        {error && <div className="bg-[var(--warning)] bg-opacity-20 text-[var(--warning)] p-3 rounded-md mb-4 text-sm">{error}</div>}
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="relative">
            <User className="absolute left-3 top-3 text-[var(--text-muted)]" size={20} />
            <input 
              type="text" 
              placeholder="Username" 
              className="input-field pl-10" 
              value={username} 
              onChange={e => setUsername(e.target.value)}
              required 
            />
          </div>
          <div className="relative">
            <Lock className="absolute left-3 top-3 text-[var(--text-muted)]" size={20} />
            <input 
              type="password" 
              placeholder="Password" 
              className="input-field pl-10" 
              value={password} 
              onChange={e => setPassword(e.target.value)}
              required 
            />
          </div>
          <button type="submit" className="btn-primary mt-2">Sign In</button>
        </form>
        <p className="mt-6 text-center text-[var(--text-muted)] text-sm">
          Don't have an account? <Link to="/register" className="text-[var(--accent-primary)] hover:underline">Register</Link>
        </p>
      </div>
    </div>
  );
};

export default Login;
