import React, { createContext, useState, useEffect, useContext } from 'react';
import { login as apiLogin, register as apiRegister } from '../api';

const AuthContext = createContext();

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('access_token'));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // If we had a /me endpoint, we would fetch user details here.
    // For now, if token exists, we consider them logged in.
    if (token) {
      setUser({ username: localStorage.getItem('username') || 'User' });
    } else {
      setUser(null);
    }
    setLoading(false);
  }, [token]);

  const login = async (username, password) => {
    const data = await apiLogin(username, password);
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('username', data.username);
    setToken(data.access_token);
    setUser({ username: data.username });
  };

  const register = async (username, password) => {
    const data = await apiRegister(username, password);
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('username', data.username);
    setToken(data.access_token);
    setUser({ username: data.username });
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('username');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout }}>
      {!loading && children}
    </AuthContext.Provider>
  );
};
