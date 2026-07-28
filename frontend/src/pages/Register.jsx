import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/useAuth';

const Register = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const { register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (confirmPassword && password !== confirmPassword) {
      setError('Mật khẩu xác nhận không khớp.');
      return;
    }

    try {
      await register(username, password);
      navigate('/');
    } catch (err) {
      setError(err.message || 'Đăng ký thất bại. Vui lòng thử lại.');
    }
  };

  return (
    <div className="bg-surface font-body-md text-on-surface min-h-screen flex flex-col items-center justify-center py-8">
      <div className="w-full max-w-md px-margin-mobile flex flex-col items-center">
        {/* Header */}
        <header className="mb-stack-lg flex flex-col items-center text-center">
          <div className="mb-stack-md shrink-0 flex items-center justify-center">
            <span className="material-symbols-outlined text-secondary" style={{ fontSize: '80px' }}>balance</span>
          </div>
          <h1 className="font-headline-lg text-[32px] font-bold text-on-surface tracking-tight">Lexora</h1>
        </header>

        {/* Main Content */}
        <main className="w-full">
          <div className="flex flex-col w-full relative">
            {/* Ambient Background Decoration */}
            <div className="absolute -top-24 -right-24 w-64 h-64 bg-primary/10 rounded-full blur-[100px] pointer-events-none"></div>
            <div className="absolute -bottom-24 -left-24 w-64 h-64 bg-secondary/10 rounded-full blur-[100px] pointer-events-none"></div>
            
            <div className="w-full flex flex-col">
              {error && (
                <div className="mb-4 p-3 bg-error-container/20 border border-error/30 text-error rounded-xl text-sm flex items-center gap-2">
                  <span className="material-symbols-outlined text-base">error</span>
                  <span>{error}</span>
                </div>
              )}

              {/* Register Form */}
              <form className="space-y-stack-md" onSubmit={handleSubmit}>
                {/* Email/Username Field */}
                <div className="group flex flex-col space-y-2 focus-within:scale-[1.01] transition-transform">
                  <label className="font-label-md text-label-md text-on-surface-variant px-1 transition-colors group-focus-within:text-secondary" htmlFor="identity">Tên đăng nhập</label>
                  <div className="relative flex items-center">
                    <span className="material-symbols-outlined absolute left-4 text-on-surface-variant group-focus-within:text-secondary transition-colors">person</span>
                    <input 
                      className="w-full h-14 bg-surface-container-lowest border border-white/5 rounded-xl pl-12 pr-4 text-on-surface font-body-md focus:border-secondary/50 focus:ring-1 focus:ring-secondary/50 transition-all outline-none" 
                      id="identity" 
                      placeholder="Nhập tên đăng nhập" 
                      type="text" 
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      required
                    />
                  </div>
                </div>

                {/* Password Field */}
                <div className="group flex flex-col space-y-2 focus-within:scale-[1.01] transition-transform">
                  <label className="font-label-md text-label-md text-on-surface-variant px-1 transition-colors group-focus-within:text-secondary" htmlFor="password">Mật khẩu</label>
                  <div className="relative flex items-center">
                    <span className="material-symbols-outlined absolute left-4 text-on-surface-variant group-focus-within:text-secondary transition-colors">lock</span>
                    <input 
                      className="w-full h-14 bg-surface-container-lowest border border-white/5 rounded-xl pl-12 pr-12 text-on-surface font-body-md focus:border-secondary/50 focus:ring-1 focus:ring-secondary/50 transition-all outline-none" 
                      id="password" 
                      placeholder="••••••••" 
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      minLength={8}
                    />
                    <button 
                      className="absolute right-4 text-on-surface-variant hover:text-on-surface transition-colors focus:outline-none cursor-pointer" 
                      onClick={() => setShowPassword(!showPassword)} 
                      type="button"
                    >
                      <span className="material-symbols-outlined">{showPassword ? 'visibility_off' : 'visibility'}</span>
                    </button>
                  </div>
                </div>

                {/* Confirm Password Field */}
                <div className="group flex flex-col space-y-2 focus-within:scale-[1.01] transition-transform">
                  <label className="font-label-md text-label-md text-on-surface-variant px-1 transition-colors group-focus-within:text-secondary" htmlFor="confirm-password">Xác nhận mật khẩu</label>
                  <div className="relative flex items-center">
                    <span className="material-symbols-outlined absolute left-4 text-on-surface-variant group-focus-within:text-secondary transition-colors">lock</span>
                    <input 
                      className="w-full h-14 bg-surface-container-lowest border border-white/5 rounded-xl pl-12 pr-4 text-on-surface font-body-md focus:border-secondary/50 focus:ring-1 focus:ring-secondary/50 transition-all outline-none" 
                      id="confirm-password" 
                      placeholder="••••••••" 
                      type={showPassword ? 'text' : 'password'}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      required
                      minLength={8}
                    />
                  </div>
                </div>

                <button 
                  type="submit"
                  className="w-full h-14 bg-secondary text-on-secondary font-label-md text-label-md rounded-xl shadow-lg hover:bg-secondary-fixed hover:scale-[1.02] active:scale-[0.98] transition-all flex items-center justify-center gap-2 group cursor-pointer mt-4"
                >
                  <span>ĐĂNG KÝ</span>
                </button>
              </form>

              <div className="text-center mt-6">
                <p className="font-body-sm text-body-sm text-on-surface-variant">
                  Đã có tài khoản? 
                  <Link className="text-secondary font-label-md hover:underline decoration-secondary/30 underline-offset-4 ml-1" to="/login">
                    Đăng nhập ngay
                  </Link>
                </p>
              </div>

            </div>
          </div>
        </main>
      </div>
    </div>
  );
};

export default Register;
