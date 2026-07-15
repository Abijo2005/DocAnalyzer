import React, { useEffect, useState, useRef } from "react"
import { useAuth } from "../context/AuthContext"
import { useTheme } from "../context/ThemeContext"
import api from "../services/api"
import {
  MessageSquare,
  FolderOpen,
  UploadCloud,
  LogOut,
  Sun,
  Moon,
  Plus,
  Trash2,
  Send,
  FileText,
  Search,
  User,
  BookOpen,
  Layers,
  Settings,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  ChevronRight,
  Info,
  X,
} from "lucide-react"

// Types matching backend schemas
interface DocumentItem {
  id: number
  filename: string
  file_size: number
  status: string
  page_count: number
  chunk_count: number
  uploaded_at: string
  error_message: string | null
}

interface Citation {
  document_name: string
  page: number | null
  chunk_id: number | null
  similarity_score: number | null
  text: string | null
}

interface Message {
  id: number
  role: string
  content: string
  sources: Citation[] | null
  timestamp: string
}

interface ChatSession {
  id: number
  title: string
  created_at: string
}

export const Dashboard: React.FC = () => {
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()

  // Navigation state
  const [activeTab, setActiveTab] = useState<"chat" | "documents">("chat")

  // Sidebar Chat Sessions state
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null)
  const [sessionMessages, setSessionMessages] = useState<Message[]>([])
  const [newSessionTitle, setNewSessionTitle] = useState("")

  // RAG Input parameters state
  const [question, setQuestion] = useState("")
  const [searchType, setSearchType] = useState<"similarity" | "mmr">("similarity")
  const [topK, setTopK] = useState(5)
  const [scoreThreshold, setScoreThreshold] = useState(0.2)
  const [showRAGSettings, setShowRAGSettings] = useState(false)
  const [queryLoading, setQueryLoading] = useState(false)

  // Documents state
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [uploadError, setUploadError] = useState("")
  const [uploadProgress, setUploadProgress] = useState<number | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  // Citation Detail Modal state
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null)

  // Custom states for UI enhancements
  const [deleteDocId, setDeleteDocId] = useState<number | null>(null)
  const [copiedBlockIdx, setCopiedBlockIdx] = useState<number | null>(null)

  const chatEndRef = useRef<HTMLDivElement>(null)

  // 1. Fetch data on mount
  useEffect(() => {
    fetchSessions()
    fetchDocuments()
  }, [])

  // Auto-scroll to bottom of chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [sessionMessages, queryLoading])

  // Polling for processing documents (runs every 3 seconds if there are active processing files)
  useEffect(() => {
    const hasProcessing = documents.some(
      (doc) => doc.status === "UPLOADED" || doc.status === "PROCESSING"
    )
    if (!hasProcessing) return

    const interval = setInterval(() => {
      fetchDocuments()
    }, 3000)

    return () => clearInterval(interval)
  }, [documents])

  // Fetch session messages when active session changes
  useEffect(() => {
    if (activeSessionId) {
      fetchSessionDetails(activeSessionId)
    } else {
      setSessionMessages([])
    }
  }, [activeSessionId])

  // --- API Functions ---

  const fetchSessions = async () => {
    try {
      const response = await api.get<ChatSession[]>("/chat/sessions")
      setSessions(response.data)
      // Auto-select first session if exists and none is selected
      if (response.data.length > 0 && activeSessionId === null) {
        setActiveSessionId(response.data[0].id)
      }
    } catch (error) {
      console.error("Failed to load chat sessions", error)
    }
  }

  const fetchDocuments = async () => {
    try {
      const response = await api.get<DocumentItem[]>("/documents/")
      setDocuments(response.data)
    } catch (error) {
      console.error("Failed to load documents", error)
    }
  }

  const fetchSessionDetails = async (sessionId: number) => {
    try {
      const response = await api.get<{ messages: Message[] }>(
        `/chat/sessions/${sessionId}`
      )
      setSessionMessages(response.data.messages)
    } catch (error) {
      console.error("Failed to load session details", error)
    }
  }

  const handleCreateSession = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    const title = newSessionTitle.trim() || `Chat Session #${sessions.length + 1}`
    try {
      const response = await api.post<ChatSession>("/chat/sessions", { title })
      setSessions((prev) => [response.data, ...prev])
      setActiveSessionId(response.data.id)
      setNewSessionTitle("")
      setActiveTab("chat")
    } catch (error) {
      console.error("Failed to create session", error)
    }
  }

  const handleDeleteSession = async (sessionId: number, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await api.delete(`/chat/sessions/${sessionId}`)
      setSessions((prev) => prev.filter((s) => s.id !== sessionId))
      if (activeSessionId === sessionId) {
        setActiveSessionId(null)
      }
    } catch (error) {
      console.error("Failed to delete session", error)
    }
  }

  const handleAskQuestion = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim() || !activeSessionId || queryLoading) return

    const userPrompt = question.trim()
    setQuestion("")
    setQueryLoading(true)

    // Pre-inject optimistic user message
    const tempUserMsg: Message = {
      id: Date.now(),
      role: "user",
      content: userPrompt,
      sources: null,
      timestamp: new Date().toISOString(),
    }
    setSessionMessages((prev) => [...prev, tempUserMsg])

    try {
      const response = await api.post<{ answer: string; sources: Citation[] }>(
        `/chat/sessions/${activeSessionId}/ask`,
        {
          question: userPrompt,
          search_type: searchType,
          top_k: topK,
          score_threshold: scoreThreshold,
        }
      )

      // Add assistant response to messages
      const tempAssistantMsg: Message = {
        id: Date.now() + 1,
        role: "assistant",
        content: response.data.answer,
        sources: response.data.sources,
        timestamp: new Date().toISOString(),
      }
      setSessionMessages((prev) => [...prev, tempAssistantMsg])
    } catch (error: any) {
      console.error("Failed to ask question", error)
      const tempErrorMsg: Message = {
        id: Date.now() + 1,
        role: "assistant",
        content: `Error: ${
          error.response?.data?.detail || "RAG pipeline failed to respond."
        }`,
        sources: null,
        timestamp: new Date().toISOString(),
      }
      setSessionMessages((prev) => [...prev, tempErrorMsg])
    } finally {
      setQueryLoading(false)
    }
  }

  // File Upload Handlers
  const handleFileUpload = async (files: FileList) => {
    setUploadError("")
    if (files.length === 0) return

    // Single upload loop or parallel
    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      const formData = new FormData()
      formData.append("file", file)

      setUploadProgress(10)
      try {
        await api.post("/documents/upload", formData, {
          headers: {
            "Content-Type": "multipart/form-data",
          },
          onUploadProgress: (progressEvent) => {
            const percentCompleted = Math.round(
              (progressEvent.loaded * 100) / (progressEvent.total || 1)
            )
            setUploadProgress(percentCompleted)
          },
        })
        fetchDocuments()
      } catch (error: any) {
        console.error("Upload failed", error)
        setUploadError(
          error.response?.data?.detail || `Failed to upload file ${file.name}.`
        )
      } finally {
        setUploadProgress(null)
      }
    }
  }

  const handleDeleteDocument = async (docId: number) => {
    try {
      await api.delete(`/documents/${docId}`)
      setDocuments((prev) => prev.filter((d) => d.id !== docId))
      setDeleteDocId(null)
    } catch (error) {
      console.error("Failed to delete document", error)
    }
  }

  // Helper file size formatter
  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes"
    const k = 1024
    const sizes = ["Bytes", "KB", "MB"]
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i]
  }

  // Render message content with markdown (bold, lists) and copyable code blocks
  const renderMessageContent = (content: string) => {
    // Split content by code blocks: ```lang\ncode\n```
    const parts = content.split(/(```[\s\S]*?```)/g)
    
    return parts.map((part, idx) => {
      if (part.startsWith("```") && part.endsWith("```")) {
        // Extract language and code content
        const lines = part.slice(3, -3).trim().split("\n")
        let language = ""
        let codeContent = part.slice(3, -3).trim()
        
        if (lines.length > 0 && /^[a-zA-Z0-9_-]+$/.test(lines[0])) {
          language = lines[0]
          codeContent = lines.slice(1).join("\n")
        }
        
        return (
          <div key={idx} className="my-3 overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-950 text-slate-100 font-mono text-[11px] shadow-sm max-w-full">
            <div className="flex items-center justify-between px-4 py-1.5 bg-slate-900 border-b border-slate-800 text-[10px] uppercase font-bold text-slate-400 select-none">
              <span>{language || "code"}</span>
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(codeContent)
                  setCopiedBlockIdx(idx)
                  setTimeout(() => setCopiedBlockIdx(null), 2000)
                }}
                className="hover:text-white transition-colors cursor-pointer flex items-center gap-1"
              >
                {copiedBlockIdx === idx ? "Copied!" : "Copy Code"}
              </button>
            </div>
            <pre className="p-4 overflow-x-auto leading-relaxed whitespace-pre font-mono">
              <code>{codeContent}</code>
            </pre>
          </div>
        )
      } else {
        // Handle bold (**text**) and inline code (`code`) and lists
        const escapeHtml = (unsafe: string) => {
          return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;")
        }
        
        let html = escapeHtml(part)
        
        // Match **bold**
        html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        
        // Match `inline code`
        html = html.replace(
          /`(.*?)`/g,
          '<code class="bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded text-[11px] font-mono border border-slate-200/50 dark:border-slate-700/50 text-pink-600 dark:text-pink-400 font-semibold">$1</code>'
        )
        
        // Match bullet lists
        const lines = html.split("\n")
        const parsedLines = lines.map((line) => {
          const cleanLine = line.trim()
          if (cleanLine.startsWith("- ") || cleanLine.startsWith("* ")) {
            return `<li class="ml-4 list-disc my-1 text-slate-700 dark:text-slate-300">${cleanLine.substring(2)}</li>`
          }
          if (/^\d+\.\s/.test(cleanLine)) {
            const match = cleanLine.match(/^(\d+)\.\s(.*)/)
            if (match) {
              return `<li class="ml-4 list-decimal my-1 text-slate-700 dark:text-slate-300">${match[2]}</li>`
            }
          }
          return line
        })
        
        const finalHtml = parsedLines.join("<br />")
        
        return (
          <span 
            key={idx} 
            dangerouslySetInnerHTML={{ __html: finalHtml }}
          />
        )
      }
    })
  }

  return (
    <div className="flex h-screen bg-slate-100 dark:bg-slate-950 text-slate-800 dark:text-slate-100 transition-colors duration-200 overflow-hidden">
      
      {/* 1. LEFT SIDEBAR: Dialogue History */}
      <aside className="w-80 border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex flex-col shrink-0">
        {/* Workspace Brand Title */}
        <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-brand-500 flex items-center justify-center text-white font-bold shadow-md shadow-brand-500/20">
            DA
          </div>
          <div>
            <h1 className="font-bold text-lg leading-tight">DocAnalyzer</h1>
            <span className="text-xs text-slate-400 font-medium">Document Intelligence</span>
          </div>
        </div>

        {/* Create new Chat Session */}
        <div className="p-4 border-b border-slate-200 dark:border-slate-800">
          <form onSubmit={handleCreateSession} className="flex gap-2">
            <input
              type="text"
              placeholder="New session title..."
              value={newSessionTitle}
              onChange={(e) => setNewSessionTitle(e.target.value)}
              className="flex-1 px-3 py-1.5 rounded-lg text-sm border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent dark:text-white"
            />
            <button
              type="submit"
              className="p-2 rounded-lg bg-brand-500 hover:bg-brand-600 text-white shadow-sm flex items-center justify-center shrink-0 cursor-pointer active:scale-95 transition-all"
              title="Create Session"
            >
              <Plus size={18} />
            </button>
          </form>
        </div>

        {/* Chat History List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-1">
          {sessions.length === 0 ? (
            <div className="text-center py-8 text-sm text-slate-400">
              No chat sessions yet. Create one above!
            </div>
          ) : (
            sessions.map((s) => (
              <div
                key={s.id}
                onClick={() => {
                  setActiveSessionId(s.id)
                  setActiveTab("chat")
                }}
                className={`group flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-all cursor-pointer ${
                  activeSessionId === s.id
                    ? "bg-brand-500/10 text-brand-500 border-l-4 border-brand-500 pl-2"
                    : "hover:bg-slate-50 dark:hover:bg-slate-800/50 text-slate-600 dark:text-slate-400"
                }`}
              >
                <div className="flex items-center gap-3 overflow-hidden">
                  <MessageSquare size={16} className="shrink-0" />
                  <span className="truncate pr-1">{s.title}</span>
                </div>
                <button
                  onClick={(e) => handleDeleteSession(s.id, e)}
                  className="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-400 hover:text-red-500 transition-all"
                  title="Delete Session"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))
          )}
        </div>

        {/* User Profile / Logout Footer */}
        <div className="p-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-between">
          <div className="flex items-center gap-3 overflow-hidden">
            <div className="h-9 w-9 rounded-full bg-slate-200 dark:bg-slate-800 flex items-center justify-center text-slate-500 dark:text-slate-400 shrink-0">
              <User size={18} />
            </div>
            <div className="overflow-hidden">
              <p className="text-xs text-slate-400 font-medium">Logged in as</p>
              <p className="text-sm font-semibold truncate dark:text-white" title={user?.email}>
                {user?.email}
              </p>
            </div>
          </div>
          <button
            onClick={logout}
            className="p-2 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-500 hover:text-red-500 transition-colors cursor-pointer"
            title="Log Out"
          >
            <LogOut size={18} />
          </button>
        </div>
      </aside>

      {/* 2. MAIN SECTION */}
      <main className="flex-1 flex flex-col overflow-hidden bg-slate-50 dark:bg-slate-950">
        
        {/* HEADER: Tabs navigation & Actions */}
        <header className="h-16 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-6 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-950 p-1 rounded-xl">
            <button
              onClick={() => setActiveTab("chat")}
              className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-semibold transition-all cursor-pointer ${
                activeTab === "chat"
                  ? "bg-white dark:bg-slate-800 shadow-sm text-brand-500"
                  : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
              }`}
            >
              <MessageSquare size={16} />
              <span>Workspace Chat</span>
            </button>
            <button
              onClick={() => setActiveTab("documents")}
              className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-semibold transition-all cursor-pointer ${
                activeTab === "documents"
                  ? "bg-white dark:bg-slate-800 shadow-sm text-brand-500"
                  : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
              }`}
            >
              <FolderOpen size={16} />
              <span>Documents Hub</span>
            </button>
          </div>

          <div className="flex items-center gap-3">
            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              className="p-2 rounded-xl bg-slate-100 dark:bg-slate-950 text-slate-600 dark:text-slate-400 hover:scale-105 transition-all cursor-pointer"
            >
              {theme === "dark" ? <Sun size={18} className="text-yellow-500" /> : <Moon size={18} />}
            </button>
          </div>
        </header>

        {/* CONTENT AREA: Dynamic tabs load */}
        <div className="flex-1 overflow-hidden relative flex flex-col">
          
          {/* TAB 1: WORKSPACE CHAT PANEL */}
          {activeTab === "chat" && (
            <div className="flex-1 flex flex-col h-full overflow-hidden">
              {/* Message History View */}
              <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
                {activeSessionId === null ? (
                  <div className="h-full flex flex-col items-center justify-center text-center p-8 max-w-md mx-auto">
                    <MessageSquare size={48} className="text-slate-300 mb-4" />
                    <h3 className="font-bold text-lg mb-2">No Active Session</h3>
                    <p className="text-sm text-slate-500">
                      Select an existing chat thread from the left menu or create a new session to begin asking questions.
                    </p>
                  </div>
                ) : sessionMessages.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-center p-8 max-w-md mx-auto">
                    <BookOpen size={48} className="text-brand-500/20 mb-4" />
                    <h3 className="font-bold text-lg mb-2">Secure RAG Portal Active</h3>
                    <p className="text-sm text-slate-500">
                      Make sure you have uploaded source documents in the <strong>Documents Hub</strong> tab, then write a query below. The system will answer utilizing your private indexed context.
                    </p>
                  </div>
                ) : (
                  sessionMessages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`flex gap-4 max-w-3xl ${
                        msg.role === "user" ? "ml-auto flex-row-reverse" : "mr-auto"
                      }`}
                    >
                      {/* Avatar */}
                      <div
                        className={`h-8 w-8 rounded-lg flex items-center justify-center text-xs font-bold shrink-0 ${
                          msg.role === "user"
                            ? "bg-brand-500 text-white"
                            : "bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-300"
                        }`}
                      >
                        {msg.role === "user" ? "U" : <Layers size={14} />}
                      </div>

                      {/* Bubble */}
                      <div className="space-y-2">
                        <div
                          className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed border ${
                            msg.role === "user"
                              ? "bg-brand-500 border-brand-600 text-white rounded-tr-none shadow-sm"
                              : "bg-white dark:bg-slate-900 border-slate-200/50 dark:border-slate-800/50 rounded-tl-none dark:text-slate-100 shadow-sm"
                          }`}
                        >
                          {renderMessageContent(msg.content)}
                        </div>

                        {/* Citations / Sources */}
                        {msg.role === "assistant" && msg.sources && msg.sources.length > 0 && (
                          <div className="flex flex-wrap gap-2 pt-1 pl-1">
                            {msg.sources.map((source, sIdx) => (
                              <button
                                key={sIdx}
                                onClick={() => setSelectedCitation(source)}
                                className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 hover:bg-slate-200 dark:bg-slate-900 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 hover:scale-105 active:scale-95 transition-all cursor-pointer"
                                title={`Click to view chunk preview. Score: ${source.similarity_score}`}
                              >
                                <FileText size={12} className="text-brand-500" />
                                <span className="max-w-[120px] truncate">
                                  {source.document_name}
                                </span>
                                {source.page && (
                                  <span className="text-[10px] bg-slate-200 dark:bg-slate-800 px-1 py-0.5 rounded text-slate-600 dark:text-slate-300">
                                    P. {source.page}
                                  </span>
                                )}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                )}

                {/* Bouncing three-dot typing loader */}
                {queryLoading && (
                  <div className="flex gap-4 max-w-3xl mr-auto animate-pulse">
                    <div className="h-8 w-8 rounded-lg bg-slate-200 dark:bg-slate-800 flex items-center justify-center shrink-0 text-slate-600 dark:text-slate-300">
                      <Layers size={14} />
                    </div>
                    <div className="bg-white dark:bg-slate-900 border border-slate-200/50 dark:border-slate-800/50 px-5 py-3.5 rounded-2xl rounded-tl-none shadow-sm flex items-center gap-1.5">
                      <div className="w-2.5 h-2.5 bg-brand-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }}></div>
                      <div className="w-2.5 h-2.5 bg-brand-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }}></div>
                      <div className="w-2.5 h-2.5 bg-brand-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }}></div>
                    </div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              {/* RAG Settings Panel Drawer (Collapsible) */}
              {showRAGSettings && (
                <div className="mx-6 p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-lg space-y-4 animate-in slide-in-from-bottom duration-200 shrink-0">
                  <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-2">
                    <div className="flex items-center gap-2 font-bold text-sm">
                      <Settings size={16} className="text-brand-500" />
                      <span>RAG Engine Search Parameters</span>
                    </div>
                    <button
                      onClick={() => setShowRAGSettings(false)}
                      className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 cursor-pointer"
                    >
                      <X size={16} />
                    </button>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-semibold">
                    {/* Search Type */}
                    <div className="space-y-2">
                      <label className="text-slate-500 uppercase tracking-wider block">
                        Retrieval Strategy
                      </label>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => setSearchType("similarity")}
                          className={`flex-1 py-1.5 rounded-lg border text-center font-bold cursor-pointer transition-all ${
                            searchType === "similarity"
                              ? "bg-brand-500/10 border-brand-500 text-brand-500"
                              : "border-slate-200 dark:border-slate-800 text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                          }`}
                        >
                          Cosine Similarity
                        </button>
                        <button
                          type="button"
                          onClick={() => setSearchType("mmr")}
                          className={`flex-1 py-1.5 rounded-lg border text-center font-bold cursor-pointer transition-all ${
                            searchType === "mmr"
                              ? "bg-brand-500/10 border-brand-500 text-brand-500"
                              : "border-slate-200 dark:border-slate-800 text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                          }`}
                          title="Maximum Marginal Relevance (Diversifies retrieved contexts)"
                        >
                          MMR Diversity
                        </button>
                      </div>
                    </div>

                    {/* Top K */}
                    <div className="space-y-2">
                      <label className="text-slate-500 uppercase tracking-wider flex justify-between">
                        <span>Retrieve Top-K Chunks</span>
                        <span className="text-brand-500 font-bold">{topK} chunks</span>
                      </label>
                      <input
                        type="range"
                        min="1"
                        max="15"
                        value={topK}
                        onChange={(e) => setTopK(parseInt(e.target.value))}
                        className="w-full h-1.5 bg-slate-200 dark:bg-slate-800 rounded-lg appearance-none cursor-pointer accent-brand-500"
                      />
                    </div>

                    {/* Score Threshold */}
                    <div className="space-y-2">
                      <label className="text-slate-500 uppercase tracking-wider flex justify-between">
                        <span>Cosine Threshold</span>
                        <span className="text-brand-500 font-bold">{scoreThreshold}</span>
                      </label>
                      <input
                        type="range"
                        min="0.1"
                        max="0.9"
                        step="0.05"
                        value={scoreThreshold}
                        onChange={(e) => setScoreThreshold(parseFloat(e.target.value))}
                        className="w-full h-1.5 bg-slate-200 dark:bg-slate-800 rounded-lg appearance-none cursor-pointer accent-brand-500"
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Chat Input Box */}
              <div className="p-6 bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 shrink-0">
                <form onSubmit={handleAskQuestion} className="max-w-3xl mx-auto flex items-center gap-3">
                  {/* Settings Toggle button */}
                  <button
                    type="button"
                    onClick={() => setShowRAGSettings((prev) => !prev)}
                    className={`p-3 rounded-xl border transition-all cursor-pointer shrink-0 ${
                      showRAGSettings
                        ? "bg-brand-500/10 border-brand-500 text-brand-500"
                        : "border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500"
                    }`}
                    title="RAG Search Configuration"
                  >
                    <Settings size={20} />
                  </button>

                  <input
                    type="text"
                    disabled={!activeSessionId || queryLoading}
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    placeholder={
                      !activeSessionId
                        ? "Please select a chat session first..."
                        : "Ask a question about your uploaded documents..."
                    }
                    className="flex-1 px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all dark:text-white disabled:opacity-50"
                  />

                  <button
                    type="submit"
                    disabled={!question.trim() || !activeSessionId || queryLoading}
                    className="p-3 rounded-xl bg-brand-500 hover:bg-brand-600 text-white font-semibold shadow-md shadow-brand-500/15 cursor-pointer disabled:opacity-40 disabled:pointer-events-none transition-all shrink-0 active:scale-95"
                  >
                    <Send size={20} />
                  </button>
                </form>
              </div>
            </div>
          )}

          {/* TAB 2: DOCUMENT MANAGER HUB */}
          {activeTab === "documents" && (
            <div className="flex-1 overflow-y-auto p-8 space-y-8">
              
              {/* Top description grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                
                {/* Drag-and-drop Upload Zone */}
                <div className="md:col-span-2">
                  <div
                    onDragOver={(e) => {
                      e.preventDefault()
                      setIsDragging(true)
                    }}
                    onDragLeave={() => setIsDragging(false)}
                    onDrop={(e) => {
                      e.preventDefault()
                      setIsDragging(false)
                      if (e.dataTransfer.files) {
                        handleFileUpload(e.dataTransfer.files)
                      }
                    }}
                    className={`h-64 border-2 border-dashed rounded-2xl flex flex-col items-center justify-center p-6 text-center transition-all ${
                      isDragging
                        ? "border-brand-500 bg-brand-500/5"
                        : "border-slate-300 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-brand-500 dark:hover:border-brand-500"
                    }`}
                  >
                    {uploadProgress !== null ? (
                      <div className="space-y-4 w-full max-w-xs mx-auto">
                        <Loader2 size={36} className="animate-spin text-brand-500 mx-auto" />
                        <h4 className="font-semibold text-sm">Uploading and Storing File...</h4>
                        <div className="w-full bg-slate-200 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                          <div
                            className="bg-brand-500 h-full transition-all duration-300 rounded-full pulse-progress"
                            style={{ width: `${uploadProgress}%` }}
                          ></div>
                        </div>
                        <span className="text-xs text-slate-400 font-bold">{uploadProgress}% complete</span>
                      </div>
                    ) : (
                      <>
                        <div className="h-12 w-12 rounded-xl bg-slate-100 dark:bg-slate-950 flex items-center justify-center text-slate-500 dark:text-slate-400 mb-4 shadow-sm">
                          <UploadCloud size={24} />
                        </div>
                        <h3 className="font-bold text-base mb-1 dark:text-white">Upload New Files</h3>
                        <p className="text-sm text-slate-400 mb-4 max-w-xs">
                          Drag and drop your PDF, DOCX, Markdown, or TXT documents here, or click to browse.
                        </p>
                        <input
                          type="file"
                          multiple
                          accept=".pdf,.txt,.docx,.md"
                          onChange={(e) => {
                            if (e.target.files) handleFileUpload(e.target.files)
                          }}
                          className="hidden"
                          id="file-selector-input"
                        />
                        <label
                          htmlFor="file-selector-input"
                          className="px-4 py-2 text-xs font-semibold rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 transition-colors shadow-sm cursor-pointer border border-slate-200/50 dark:border-slate-700"
                        >
                          Select Files
                        </label>
                      </>
                    )}
                  </div>
                  {uploadError && (
                    <div className="mt-3 flex items-start gap-2.5 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-xs font-semibold animate-pulse">
                      <AlertTriangle size={16} className="shrink-0 mt-0.5" />
                      <span>{uploadError}</span>
                    </div>
                  )}
                </div>

                {/* Upload Guard Metadata Card */}
                <div className="glass-panel p-6 rounded-2xl flex flex-col justify-between">
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 font-bold text-sm border-b border-slate-200 dark:border-slate-800 pb-2">
                      <Info size={16} className="text-brand-500" />
                      <span>Upload Safety Guard</span>
                    </div>
                    <ul className="space-y-2 text-xs font-medium text-slate-500 dark:text-slate-400">
                      <li className="flex items-center gap-2">
                        <CheckCircle2 size={12} className="text-green-500" />
                        <span>Max upload size: 25MB per file</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <CheckCircle2 size={12} className="text-green-500" />
                        <span>Supported formats: PDF, DOCX, TXT, MD</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <CheckCircle2 size={12} className="text-green-500" />
                        <span>Local embedding model: all-MiniLM-L6-v2</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <CheckCircle2 size={12} className="text-green-500" />
                        <span>SHA-256 caching: skipped processing on duplicates</span>
                      </li>
                    </ul>
                  </div>
                  <div className="p-3 bg-brand-500/5 rounded-xl border border-brand-500/10 text-xs font-medium text-slate-500 leading-relaxed mt-4">
                    Files are parsed page-by-page. For multi-page PDFs, chunks remain bound to exact page coordinates for clean citations.
                  </div>
                </div>
              </div>

              {/* Documents Status List */}
              <div className="glass-panel rounded-2xl overflow-hidden shadow-sm">
                <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
                  <h3 className="font-bold text-base dark:text-white">Indexed Documents Workspace</h3>
                  <span className="text-xs font-bold bg-slate-100 dark:bg-slate-800 px-2.5 py-1 rounded-full text-slate-500">
                    {documents.length} items total
                  </span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm border-collapse">
                    <thead>
                      <tr className="bg-slate-50 dark:bg-slate-900/50 text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-200 dark:border-slate-800">
                        <th className="px-6 py-3">Document Name</th>
                        <th className="px-6 py-3">File Size</th>
                        <th className="px-6 py-3">Pages / Chunks</th>
                        <th className="px-6 py-3">Processing Status</th>
                        <th className="px-6 py-3 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200/50 dark:divide-slate-800/50 font-medium">
                      {documents.length === 0 ? (
                        <tr>
                          <td colSpan={5} className="px-6 py-12 text-center text-slate-400 text-sm">
                            No documents uploaded yet. Add some files to activate the RAG search.
                          </td>
                        </tr>
                      ) : (
                        documents.map((doc) => (
                          <tr key={doc.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/20">
                            <td className="px-6 py-4 flex items-center gap-3 overflow-hidden max-w-xs">
                              <FileText size={18} className="text-brand-500 shrink-0" />
                              <span className="truncate dark:text-white" title={doc.filename}>
                                {doc.filename}
                              </span>
                            </td>
                            <td className="px-6 py-4 text-slate-400">
                              {formatBytes(doc.file_size)}
                            </td>
                            <td className="px-6 py-4 text-slate-500">
                              {doc.status === "COMPLETED" ? (
                                <span className="flex items-center gap-1.5">
                                  <span>{doc.page_count} pages</span>
                                  <ChevronRight size={10} className="text-slate-300" />
                                  <span>{doc.chunk_count} chunks</span>
                                </span>
                              ) : (
                                <span className="text-slate-300">N/A</span>
                              )}
                            </td>
                            <td className="px-6 py-4">
                              {doc.status === "COMPLETED" && (
                                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-green-500/10 text-green-600 dark:text-green-400">
                                  <CheckCircle2 size={12} />
                                  <span>Completed</span>
                                </span>
                              )}
                              {doc.status === "UPLOADED" && (
                                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-600 dark:text-blue-400 animate-pulse">
                                  <Loader2 size={12} className="animate-spin" />
                                  <span>Uploaded</span>
                                </span>
                              )}
                              {doc.status === "PROCESSING" && (
                                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 animate-pulse">
                                  <Loader2 size={12} className="animate-spin" />
                                  <span>Chunking/Embedding</span>
                                </span>
                              )}
                              {doc.status === "FAILED" && (
                                <span
                                  className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-500/10 text-red-600 dark:text-red-400 cursor-pointer"
                                  title={doc.error_message || "Ingestion error"}
                                >
                                  <AlertTriangle size={12} />
                                  <span>Failed</span>
                                </span>
                              )}
                            </td>
                            <td className="px-6 py-4 text-right">
                              <button
                                onClick={() => setDeleteDocId(doc.id)}
                                className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-red-500 transition-all cursor-pointer"
                                title="Delete Document"
                              >
                                <Trash2 size={16} />
                              </button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* 3. CITATION PREVIEW DRAWER (SLIDES IN FROM RIGHT) */}
      <div 
        className={`fixed inset-y-0 right-0 z-50 w-full max-w-md bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-800 shadow-2xl flex flex-col transition-transform duration-300 ease-in-out transform ${
          selectedCitation ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Drawer Header */}
        <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2 font-bold text-base dark:text-white">
            <FileText size={20} className="text-brand-500" />
            <span>Citation Details</span>
          </div>
          <button
            onClick={() => setSelectedCitation(null)}
            className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-600 cursor-pointer transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Drawer Scrollable Content */}
        {selectedCitation && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            <div className="grid grid-cols-2 gap-4 text-xs font-semibold">
              <div className="p-3 bg-slate-50 dark:bg-slate-950 rounded-xl border border-slate-200/50 dark:border-slate-800/50">
                <p className="text-slate-400 uppercase tracking-wider mb-0.5 text-[9px]">Document</p>
                <p className="truncate dark:text-white" title={selectedCitation.document_name}>
                  {selectedCitation.document_name}
                </p>
              </div>
              <div className="p-3 bg-slate-50 dark:bg-slate-950 rounded-xl border border-slate-200/50 dark:border-slate-800/50">
                <p className="text-slate-400 uppercase tracking-wider mb-0.5 text-[9px]">Coordinate</p>
                <p className="dark:text-white">
                  {selectedCitation.page ? `Page ${selectedCitation.page}` : "N/A"}
                </p>
              </div>
              <div className="p-3 bg-slate-50 dark:bg-slate-950 rounded-xl border border-slate-200/50 dark:border-slate-800/50">
                <p className="text-slate-400 uppercase tracking-wider mb-0.5 text-[9px]">Relevance Score</p>
                <p className="text-brand-500 font-bold">
                  {selectedCitation.similarity_score !== null
                    ? `${(selectedCitation.similarity_score * 100).toFixed(1)}% match`
                    : "N/A"}
                </p>
              </div>
              <div className="p-3 bg-slate-50 dark:bg-slate-950 rounded-xl border border-slate-200/50 dark:border-slate-800/50">
                <p className="text-slate-400 uppercase tracking-wider mb-0.5 text-[9px]">Chunk Index</p>
                <p className="dark:text-white">#{selectedCitation.chunk_id}</p>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Retrieved Context Snippet
              </label>
              <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-xs leading-relaxed max-h-96 overflow-y-auto whitespace-pre-wrap dark:text-slate-200 font-mono shadow-inner select-text">
                {selectedCitation.text}
              </div>
            </div>
          </div>
        )}

        {/* Drawer Footer */}
        <div className="p-6 border-t border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex justify-end shrink-0">
          <button
            onClick={() => setSelectedCitation(null)}
            className="px-4 py-2 text-xs font-bold rounded-lg bg-brand-500 hover:bg-brand-600 text-white cursor-pointer active:scale-95 transition-all shadow-md shadow-brand-500/10"
          >
            Close Drawer
          </button>
        </div>
      </div>

      {/* Drawer Backdrop overlay */}
      {selectedCitation && (
        <div 
          onClick={() => setSelectedCitation(null)}
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm transition-opacity duration-300"
        />
      )}

      {/* 4. CONFIRMATION MODAL: DELETE DOCUMENT */}
      {deleteDocId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="w-full max-w-sm bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 rounded-2xl shadow-2xl space-y-4 animate-in zoom-in-95 duration-200 relative text-center">
            <div className="mx-auto h-12 w-12 rounded-full bg-red-500/10 flex items-center justify-center text-red-500 mb-2">
              <AlertTriangle size={24} />
            </div>
            
            <div className="space-y-1">
              <h3 className="font-bold text-base dark:text-white">Delete Document?</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Are you sure you want to delete this document? This will remove the file from local storage and delete its vector indexes permanently.
              </p>
            </div>
            
            <div className="flex gap-3 justify-center pt-2">
              <button
                onClick={() => setDeleteDocId(null)}
                className="px-4 py-2 text-xs font-semibold rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-850 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDeleteDocument(deleteDocId)}
                className="px-4 py-2 text-xs font-bold rounded-lg bg-red-500 hover:bg-red-600 text-white cursor-pointer active:scale-95 transition-all shadow-md shadow-brand-500/10"
              >
                Confirm Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
