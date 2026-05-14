'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Sparkles, Plus, MessageSquare, Shield, TrendingUp, Cpu, Scale, Loader2, Settings, ChevronRight, RotateCcw } from 'lucide-react';

interface Message {
  id: string;
  role: 'agent_a' | 'agent_b' | 'moderator' | 'user';
  name: string;
  content: string;
  isStreaming?: boolean;
}

const AVAILABLE_MODELS = [
  { id: 'llama3.2:3b', name: 'Llama 3.2 (3B)', provider: 'Ollama' },
  { id: 'llama3.1:8b', name: 'Llama 3.1 (8B)', provider: 'Ollama' },
  { id: 'gemma2:latest', name: 'Gemma 2 (Latest)', provider: 'Ollama' },
  { id: 'gemini-2.0-flash', name: 'Gemini 2.0 Flash', provider: 'Google' },
];

export default function AICouncilApp() {
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStarted, setIsStarted] = useState(false);
  
  const [businessModel, setBusinessModel] = useState('llama3.1:8b');
  const [techModel, setTechModel] = useState('llama3.1:8b');
  const [businessName, setBusinessName] = useState('Agent A');
  const [businessInstruction, setBusinessInstruction] = useState('당신은 수익성과 시장성을 분석하는 제안자입니다.');
  const [techName, setTechName] = useState('Agent B');
  const [techInstruction, setTechInstruction] = useState('당신은 기술적 실현 가능성을 분석하는 비판자입니다.');
  
  const [status, setStatus] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, status]);

  const handleDebate = async () => {
    if (!input.trim() || isLoading) return;
    
    const topic = input;
    setInput('');
    setIsLoading(true);
    setIsStarted(true);
    setMessages([]);
    setStatus('토론 준비 중...');

    try {
      const response = await fetch('http://localhost:8000/api/v1/debate/run/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          topic,
          business_model: businessModel,
          tech_model: techModel,
          business_name: businessName,
          business_instruction: businessInstruction,
          tech_name: techName,
          tech_instruction: techInstruction
        }),
      });

      if (!response.ok) throw new Error('서버 연결 실패');
      
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');
          
          for (const line of lines) {
            if (!line.trim()) continue;
            try {
              const data = JSON.parse(line);
              
              if (data.type === 'status') {
                setStatus(data.content);
              } else if (data.type === 'chunk') {
                setMessages(prev => {
                  const lastMsg = prev[prev.length - 1];
                  if (lastMsg && lastMsg.role === data.node && lastMsg.isStreaming) {
                    return [
                      ...prev.slice(0, -1),
                      { ...lastMsg, content: lastMsg.content + data.content }
                    ];
                  } else {
                    return [
                      ...prev,
                      { 
                        id: Math.random().toString(), 
                        role: data.node, 
                        name: data.node === 'summarize' ? '의장(최종 결론)' : (data.node === 'agent_a' ? businessName : techName), 
                        content: data.content,
                        isStreaming: true 
                      }
                    ];
                  }
                });
              } else if (data.type === 'node_done') {
                setMessages(prev => {
                  const lastMsg = prev[prev.length - 1];
                  if (lastMsg && lastMsg.role === data.node) {
                    return [
                      ...prev.slice(0, -1),
                      { ...lastMsg, content: data.content, isStreaming: false }
                    ];
                  } else {
                    // 이전에 chunk가 없었을 경우 새로 추가
                    return [
                      ...prev,
                      { 
                        id: Math.random().toString(), 
                        role: data.node as any, 
                        name: data.node === 'summarize' ? '의장(최종 결론)' : (data.node === 'agent_a' ? businessName : techName), 
                        content: data.content,
                        isStreaming: false 
                      }
                    ];
                  }
                });
              }
            } catch (e) {
              // Partial JSON handling
            }
          }
        }
      }
    } catch (error) {
      alert('오류 발생: ' + error);
    } finally {
      setIsLoading(false);
      setStatus('토론 종료');
    }
  };

  return (
    <main className="flex h-screen bg-[#0f172a] text-white font-sans overflow-hidden">
      {/* Sidebar */}
      <aside className="w-80 bg-[#1e293b]/50 backdrop-blur-xl border-r border-white/10 flex flex-col p-6 overflow-y-auto">
        <div className="flex items-center gap-3 mb-10">
          <Sparkles className="text-violet-500" size={28} />
          <h2 className="text-2xl font-black tracking-tighter">AI Council V2</h2>
        </div>
        
        <div className="space-y-6">
          <div className="p-4 bg-white/5 rounded-2xl border border-white/10">
            <h3 className="text-sm font-bold text-white/40 mb-4 flex items-center gap-2">
              <Settings size={14} /> Agent A (Proposer)
            </h3>
            <div className="space-y-4">
              <div>
                <label className="text-[10px] uppercase font-bold text-white/40 mb-1 block">Model</label>
                <select 
                  className="w-full bg-[#0f172a] border border-white/10 rounded-lg p-2 text-sm outline-none"
                  value={businessModel}
                  onChange={(e) => setBusinessModel(e.target.value)}
                >
                  {AVAILABLE_MODELS.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[10px] uppercase font-bold text-white/40 mb-1 block">Name</label>
                <input 
                  className="w-full bg-white/5 border border-white/10 rounded-lg p-2 text-sm outline-none"
                  value={businessName}
                  onChange={(e) => setBusinessName(e.target.value)}
                />
              </div>
              <div>
                <label className="text-[10px] uppercase font-bold text-white/40 mb-1 block">Instruction</label>
                <textarea 
                  className="w-full bg-white/5 border border-white/10 rounded-lg p-2 text-xs outline-none min-h-[60px]"
                  value={businessInstruction}
                  onChange={(e) => setBusinessInstruction(e.target.value)}
                />
              </div>
            </div>
          </div>

          <div className="p-4 bg-white/5 rounded-2xl border border-white/10">
            <h3 className="text-sm font-bold text-white/40 mb-4 flex items-center gap-2">
              <Settings size={14} /> Agent B (Critic)
            </h3>
            <div className="space-y-4">
              <div>
                <label className="text-[10px] uppercase font-bold text-white/40 mb-1 block">Model</label>
                <select 
                  className="w-full bg-[#0f172a] border border-white/10 rounded-lg p-2 text-sm outline-none"
                  value={techModel}
                  onChange={(e) => setTechModel(e.target.value)}
                >
                  {AVAILABLE_MODELS.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[10px] uppercase font-bold text-white/40 mb-1 block">Name</label>
                <input 
                  className="w-full bg-white/5 border border-white/10 rounded-lg p-2 text-sm outline-none"
                  value={techName}
                  onChange={(e) => setTechName(e.target.value)}
                />
              </div>
              <div>
                <label className="text-[10px] uppercase font-bold text-white/40 mb-1 block">Instruction</label>
                <textarea 
                  className="w-full bg-white/5 border border-white/10 rounded-lg p-2 text-xs outline-none min-h-[60px]"
                  value={techInstruction}
                  onChange={(e) => setTechInstruction(e.target.value)}
                />
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col relative">
        <header className="px-10 py-6 border-b border-white/10 flex justify-between items-center backdrop-blur-md z-10">
          <div>
            <h1 className="text-xl font-bold">Tiki-Taka Debate Board</h1>
            <p className="text-sm text-white/40">{status || '토론 주제를 입력하여 대화를 시작하세요.'}</p>
          </div>
          <div className="px-3 py-1 bg-violet-600 rounded-full text-[10px] font-black uppercase tracking-widest">
            React 19 + Streaming
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-10 space-y-8 scroll-smooth">
          {!isStarted && (
            <div className="h-full flex flex-col items-center justify-center opacity-20">
              <MessageSquare size={80} className="mb-4" />
              <h2 className="text-2xl font-bold">대기 중...</h2>
            </div>
          )}

          {messages.filter(msg => msg.content && msg.content.trim() !== '').map((msg) => (
            <div 
              key={msg.id} 
              className={`flex flex-col ${
                msg.role === 'summarize' 
                  ? 'items-center' 
                  : (msg.role === 'agent_a' ? 'items-start' : 'items-end')
              } animate-fade-in`}
            >
              <div className="flex items-center gap-2 mb-2 px-1">
                <span className={`text-[11px] font-black uppercase tracking-wider ${
                  msg.role === 'summarize' ? 'text-amber-400' : 'text-white/40'
                }`}>
                  {msg.name}
                </span>
                {msg.isStreaming && <Loader2 size={10} className="animate-spin text-violet-500" />}
              </div>
              <div 
                className={`max-w-[80%] p-6 rounded-2xl leading-relaxed text-sm shadow-2xl transition-all ${
                  msg.role === 'summarize'
                    ? 'bg-gradient-to-br from-amber-900/40 to-yellow-900/40 border-2 border-amber-500/50 text-amber-50'
                    : (msg.role === 'agent_a' 
                        ? 'bg-slate-800 border border-white/10 rounded-bl-none' 
                        : 'bg-violet-600 border border-violet-400/30 rounded-br-none')
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-10 pt-0">
          <div className="max-w-4xl mx-auto relative group">
            <input 
              className="w-full bg-[#1e293b]/80 backdrop-blur-2xl border border-white/10 rounded-3xl py-5 px-8 pr-20 outline-none focus:border-violet-500/50 transition-all shadow-2xl"
              placeholder="토론할 주제를 입력하세요..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleDebate()}
              disabled={isLoading}
            />
            <button 
              className="absolute right-3 top-1/2 -translate-y-1/2 w-12 h-12 bg-violet-500 rounded-2xl flex items-center justify-center hover:bg-violet-400 transition-colors disabled:opacity-50"
              onClick={handleDebate}
              disabled={isLoading || !input.trim()}
            >
              {isLoading ? <Loader2 className="animate-spin" /> : <Send size={20} />}
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
