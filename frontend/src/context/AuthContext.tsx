import React, { createContext, useContext, useEffect, useState } from "react"
import api from "../services/api"

interface User {
  id: number
  email: string
}

interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const refreshUser = async () => {
    try {
      const response = await api.get<User>("/auth/me")
      setUser(response.data)
    } catch (error) {
      logout()
    }
  }

  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem("token")
      if (token) {
        try {
          const response = await api.get<User>("/auth/me")
          setUser(response.data)
        } catch (error) {
          localStorage.removeItem("token")
          setUser(null)
        }
      }
      setLoading(false)
    }
    checkAuth()
  }, [])

  const login = async (email: string, password: string) => {
    // FastAPI OAuth2PasswordRequestForm expects URLSearchParams or form data
    const params = new URLSearchParams()
    params.append("username", email)
    params.append("password", password)

    const response = await api.post<{ access_token: string }>("/auth/login", params, {
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
    })

    localStorage.setItem("token", response.data.access_token)
    await refreshUser()
  }

  const register = async (email: string, password: string) => {
    await api.post("/auth/register", { email, password })
  }

  const logout = () => {
    localStorage.removeItem("token")
    setUser(null)
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        loading,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
