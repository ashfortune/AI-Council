'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Sparkles, Plus, MessageSquare, Shield, TrendingUp, Cpu, Scale, Loader2, Settings, ChevronRight, RotateCcw } from 'lucide-react';

interface Message {
  id: string;
  role: 'agent_a' | 'agent_b' | 'moderator' | 'user' | 'summarize';
  name: string;
  content: string;
  isStreaming: boolean;
  isThinking?: boolean;
  turn?: number;
}

const TypingDots = () => (
  <div className="flex space-x-1 items-center h-5">
    <div className="w-1.5 h-1.5 bg-current rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
    <div className="w-1.5 h-1.5 bg-current rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
    <div className="w-1.5 h-1.5 bg-current rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
  </div>
);

const AVAILABLE_MODELS = [
  { id: 'gemini-3.1-flash-lite', name: 'Gemini 3.1 Flash Lite' },
  { id: 'gemma-4-26b-a4b-it', name: 'Gemma 4 26B' },
  { id: 'gemma-4-31b-it', name: 'Gemma 4 31B' },
];

export default function AICouncilApp() {
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStarted, setIsStarted] = useState(false);

  const [businessModel, setBusinessModel] = useState('gemini-3.1-flash-lite');
  const [techModel, setTechModel] = useState('gemini-3.1-flash-lite');
  const [businessName, setBusinessName] = useState('');
  const [businessInstruction, setBusinessInstruction] = useState('');
  const [techName, setTechName] = useState('');
  const [techInstruction, setTechInstruction] = useState('');

  const [status, setStatus] = useState<string | null>(null);
  const [activeNode, setActiveNode] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, status, activeNode]);

  const handleReset = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setInput('');
    setMessages([]);
    setIsStarted(false);
    setIsLoading(false);
    setStatus(null);
    setActiveNode(null);
  };

  const handleResetAgentA = () => {
    setBusinessModel('gemini-3.1-flash-lite');
    setBusinessName('');
    setBusinessInstruction('');
  };

  const handleResetAgentB = () => {
    setTechModel('gemini-3.1-flash-lite');
    setTechName('');
    setTechInstruction('');
  };

  const handleResetAllSettings = () => {
    handleResetAgentA();
    handleResetAgentB();
  };

  const handleDebate = async () => {
    if (isLoading) return;

    if (!businessName.trim()) {
      alert('Agent A의 이름을 입력해주세요.');
      return;
    }
    if (!businessInstruction.trim()) {
      alert('Agent A의 지침(Instruction)을 입력해주세요.');
      return;
    }
    if (!techName.trim()) {
      alert('Agent B의 이름을 입력해주세요.');
      return;
    }
    if (!techInstruction.trim()) {
      alert('Agent B의 지침(Instruction)을 입력해주세요.');
      return;
    }

    if (!input.trim()) {
      alert('토론할 주제를 입력해주세요.');
      return;
    }

    const topic = input;
    setInput('');
    setIsLoading(true);
    setIsStarted(true);
    setMessages([]);
    setStatus('토론 준비 중...');

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch('http://localhost:8000/api/v1/debate/run/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: abortControllerRef.current.signal,
        body: JSON.stringify({
          topic,
          business_model: businessModel,
          tech_model: techModel,
          business_name: businessName.trim(),
          business_instruction: businessInstruction.trim(),
          tech_name: techName.trim(),
          tech_instruction: techInstruction.trim()
        }),
      });

      if (!response.ok) throw new Error('서버 연결 실패');

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunkStr = decoder.decode(value);
          const lines = chunkStr.split('\n');

          for (const line of lines) {
            if (!line.trim()) continue;
            try {
              const data = JSON.parse(line);

              if (data.type === 'status') {
                setStatus(data.content);
                setActiveNode(data.node);
                if (data.node && ['agent_a', 'agent_b', 'summarize'].includes(data.node)) {
                  setMessages(prev => {
                    const targetId = `turn-${data.turn}-${data.node}`;
                    const exists = prev.some(m => m.id === targetId);
                    if (!exists) {
                      return [
                        ...prev,
                        {
                          id: targetId,
                          role: data.node as any,
                          name: data.node === 'summarize' ? '의장(최종 결론)' : (data.node === 'agent_a' ? businessName : techName),
                          content: '',
                          isStreaming: true,
                          isThinking: true,
                          turn: data.turn
                        }
                      ];
                    }
                    return prev;
                  });
                }
              } else if (data.type === 'chunk') {
                setMessages(prev => {
                  const targetId = `turn-${data.turn}-${data.node}`;
                  const targetIdx = prev.findLastIndex(m => m.id === targetId);

                  if (targetIdx === -1) {
                    return [
                      ...prev,
                      {
                        id: targetId,
                        role: data.node,
                        name: data.node === 'summarize' ? '의장(최종 결론)' : (data.node === 'agent_a' ? businessName : techName),
                        content: data.content,
                        isStreaming: true,
                        isThinking: false,
                        turn: data.turn
                      }
                    ];
                  }

                  const newMessages = [...prev];
                  newMessages[targetIdx] = {
                    ...newMessages[targetIdx],
                    content: newMessages[targetIdx].content + data.content,
                    isThinking: false
                  };
                  return newMessages;
                });
              } else if (data.type === 'node_done') {
                setMessages(prev => {
                  const targetId = `turn-${data.turn}-${data.node}`;
                  const targetIdx = prev.findLastIndex(m => m.id === targetId);

                  // 모든 메시지의 스트리밍 상태 종료
                  const baseMessages = prev.map((m: Message) => ({ ...m, isStreaming: false, isThinking: false }));

                  if (targetIdx !== -1) {
                    const newMessages = [...baseMessages];
                    newMessages[targetIdx] = {
                      ...newMessages[targetIdx],
                      content: data.content,
                      isStreaming: false,
                      isThinking: false
                    };
                    return newMessages;
                  } else {
                    // 메시지가 없었다면 새로 생성
                    return [
                      ...baseMessages,
                      {
                        id: targetId,
                        role: data.node as any,
                        name: data.node === 'summarize' ? '의장(최종 결론)' : (data.node === 'agent_a' ? businessName : techName),
                        content: data.content,
                        isStreaming: false,
                        isThinking: false,
                        turn: data.turn
                      }
                    ];
                  }
                });
              }
            } catch (e) {
              console.error("Parse error:", e, line);
            }
          }
        }
      }
    } catch (error: any) {
      if (error.name === 'AbortError') return;
      alert('오류 발생: ' + error);
    } finally {
      setIsLoading(false);
      setStatus(null);
      setActiveNode(null);
    }
  };

  return (
    <main className="flex h-screen bg-[#0f172a] text-white font-sans overflow-hidden">
      <aside className="w-80 bg-[#1e293b]/50 backdrop-blur-xl border-r border-white/10 flex flex-col p-6 overflow-y-auto">
        <div className="flex items-center justify-between mb-10">
          <div className="flex items-center gap-3">
            <Sparkles className="text-violet-500" size={28} />
            <h2 className="text-2xl font-black tracking-tighter">AI Council</h2>
          </div>
          <button
            type="button"
            onClick={handleResetAllSettings}
            title="모든 에이전트 설정 초기화"
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-[11px] text-white/60 hover:text-white transition-all shadow-sm"
          >
            <RotateCcw size={12} />
            <span>설정 리셋</span>
          </button>
        </div>

        <div className="space-y-6">
          <div className="p-4 bg-white/5 rounded-2xl border border-white/10">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-sm font-bold text-white/40 flex items-center gap-2">
                <Settings size={14} /> Agent A
              </h3>
              <button
                type="button"
                onClick={handleResetAgentA}
                title="Agent A 설정 초기화"
                className="text-white/30 hover:text-white transition-colors p-1"
              >
                <RotateCcw size={12} />
              </button>
            </div>
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
                  placeholder="이름을 입력하세요 (예: 사업총괄)"
                  value={businessName}
                  onChange={(e) => setBusinessName(e.target.value)}
                />
              </div>
              <div>
                <label className="text-[10px] uppercase font-bold text-white/40 mb-1 block">Instruction</label>
                <textarea
                  className="w-full bg-white/5 border border-white/10 rounded-lg p-2 text-xs outline-none min-h-[60px]"
                  placeholder="예: 제안된 안건의 수익성과 시장성 관점에서 방어하고 확장 전략을 제시하세요."
                  value={businessInstruction}
                  onChange={(e) => setBusinessInstruction(e.target.value)}
                />
              </div>
            </div>
          </div>

          <div className="p-4 bg-white/5 rounded-2xl border border-white/10">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-sm font-bold text-white/40 flex items-center gap-2">
                <Settings size={14} /> Agent B
              </h3>
              <button
                type="button"
                onClick={handleResetAgentB}
                title="Agent B 설정 초기화"
                className="text-white/30 hover:text-white transition-colors p-1"
              >
                <RotateCcw size={12} />
              </button>
            </div>
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
                  placeholder="이름을 입력하세요 (예: 기술총괄)"
                  value={techName}
                  onChange={(e) => setTechName(e.target.value)}
                />
              </div>
              <div>
                <label className="text-[10px] uppercase font-bold text-white/40 mb-1 block">Instruction</label>
                <textarea
                  className="w-full bg-white/5 border border-white/10 rounded-lg p-2 text-xs outline-none min-h-[60px]"
                  placeholder="예: 기술적 실현 가능성과 시스템 안정성, 리스크를 냉철하게 비판하세요."
                  value={techInstruction}
                  onChange={(e) => setTechInstruction(e.target.value)}
                />
              </div>
            </div>
          </div>
        </div>
      </aside>

      <div className="flex-1 flex flex-col relative">
        <header className="px-10 py-6 border-b border-white/10 flex justify-between items-center backdrop-blur-md z-10">
          <div>
            <h1 className="text-xl font-bold">Debate Board</h1>
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

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col ${msg.role === 'summarize'
                ? 'items-center'
                : (msg.role === 'agent_a' ? 'items-start' : 'items-end')
                } animate-fade-in mb-6`}
            >
              <div className="flex flex-col max-w-[80%]">
                <span className={`text-[11px] font-medium mb-1.5 px-1 opacity-50 ${msg.role === 'agent_b' ? 'text-right' : ''
                  }`}>
                  {msg.name}
                </span>
                <div className={`relative px-4 py-3 rounded-2xl shadow-lg transition-all duration-300 ${msg.role === 'summarize'
                  ? 'bg-gradient-to-br from-amber-400/20 to-orange-500/20 border border-amber-500/30 text-amber-100 text-center backdrop-blur-md'
                  : (msg.role === 'agent_a'
                    ? 'bg-[#1e293b] border border-white/10 text-white rounded-tl-none'
                    : 'bg-indigo-600 text-white rounded-tr-none shadow-indigo-500/20')
                  }`}>
                  {msg.isThinking ? (
                    <div className="flex items-center gap-3">
                      <TypingDots />
                      <span className="text-[11px] opacity-70">생각 중...</span>
                    </div>
                  ) : (
                    <p className="text-[13.5px] leading-relaxed whitespace-pre-wrap">
                      {msg.content}
                    </p>
                  )}
                </div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-10 pt-0">
          <div className="max-w-4xl mx-auto relative group">
            <input
              className="w-full bg-[#1e293b]/80 backdrop-blur-2xl border border-white/10 rounded-3xl py-5 px-8 pr-32 outline-none focus:border-violet-500/50 transition-all shadow-2xl"
              placeholder="토론할 주제를 입력하세요..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleDebate()}
              disabled={isLoading}
            />
            <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-2">
              <button
                type="button"
                title="초기화"
                className="w-12 h-12 bg-white/10 rounded-2xl flex items-center justify-center hover:bg-white/20 transition-colors text-white/70 hover:text-white disabled:opacity-50 shadow-md"
                onClick={handleReset}
                disabled={!input && !isStarted && !isLoading}
              >
                <RotateCcw size={20} className={isLoading ? "animate-spin" : ""} />
              </button>
              <button
                type="button"
                title="전송"
                className="w-12 h-12 bg-violet-500 rounded-2xl flex items-center justify-center hover:bg-violet-400 transition-colors disabled:opacity-50 shadow-md"
                onClick={handleDebate}
                disabled={isLoading}
              >
                {isLoading ? <Loader2 className="animate-spin" /> : <Send size={20} />}
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
