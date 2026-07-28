import { useState, useEffect } from 'react';
import {
  clearAccessToken,
  getStoredAccessToken,
  login as apiLogin,
  register as apiRegister,
  storeAccessToken,
} from '../api';
import { AuthContext } from './auth-context';

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(getStoredAccessToken());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // If we had a /me endpoint, we would fetch user details here.
    // For now, if token exists, we consider them logged in.
    if (token) {
      setUser({ username: localStorage.getItem('username') || 'Người dùng' });
    } else {
      setUser(null);
    }
    setLoading(false);
  }, [token]);

  const login = async (username, password) => {
    try {
      const data = await apiLogin(username, password);
      storeAccessToken(data.access_token);
      localStorage.setItem('username', data.username);
      setToken(data.access_token);
      setUser({ username: data.username });
    } catch (error) {
      if (error.message === 'Incorrect username or password') {
        throw new Error('Tên đăng nhập hoặc mật khẩu không chính xác');
      }
      throw error;
    }
  };

  const register = async (username, password) => {
    try {
      const data = await apiRegister(username, password);
      storeAccessToken(data.access_token);
      localStorage.setItem('username', data.username);
      setToken(data.access_token);
      setUser({ username: data.username });
    } catch (error) {
      if (error.message === 'Username already registered') {
        throw new Error('Tên đăng nhập đã tồn tại');
      }
      throw error;
    }
  };

  const logout = () => {
    clearAccessToken();
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
