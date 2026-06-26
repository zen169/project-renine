import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { ApiService } from './api';

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  serverUrl: string;
  login: (password: string, url: string, username?: string) => Promise<boolean>;
  logout: () => Promise<void>;
  updateServerUrl: (url: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [serverUrl, setServerUrlState] = useState<string>('');

  useEffect(() => {
    async function initializeAuth() {
      try {
        const storedUrl = await ApiService.getServerUrl();
        setServerUrlState(storedUrl);

        const token = await ApiService.getToken();
        if (token) {
          setIsAuthenticated(true);
        }
      } catch (err) {
        console.error('Failed to initialize authentication state', err);
      } finally {
        setIsLoading(false);
      }
    }
    initializeAuth();
  }, []);

  const login = async (password: string, url: string, username: string = 'admin'): Promise<boolean> => {
    setIsLoading(true);
    try {
      await ApiService.setServerUrl(url);
      setServerUrlState(url);
      const success = await ApiService.login(password, username);
      if (success) {
        setIsAuthenticated(true);
        return true;
      }
      return false;
    } catch (err) {
      setIsAuthenticated(false);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    setIsLoading(true);
    try {
      await ApiService.clearToken();
      setIsAuthenticated(false);
    } catch (err) {
      console.error('Logout error', err);
    } finally {
      setIsLoading(false);
    }
  };

  const updateServerUrl = async (url: string) => {
    await ApiService.setServerUrl(url);
    setServerUrlState(url);
  };

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        isLoading,
        serverUrl,
        login,
        logout,
        updateServerUrl,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
