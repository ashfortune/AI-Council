from typing import Annotated, List, TypedDict, AsyncGenerator, Union
import operator
import os
import json
import asyncio
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from loguru import logger
from app.core.config import settings
from app.services.vector_service import vector_service
import json
import asyncio

# 토론 상태 정의
class DebateState(TypedDict):
    topic: str
    messages: Annotated[List[BaseMessage], operator.add]
    next_speaker: str
    turn_count: int
    is_consented: bool
    models: dict
    personas: dict

class DebateService:
    def _get_llm(self, model_name: str, temperature: float = 0.5):
        # 2026년 환경 표준 모델 우선순위
        model_candidates = ["gemini-2.5-flash", "gemini-flash-latest", "gemma-4-31b-it"]
        
        if not model_name or "gemini" in model_name.lower() or "gemma" in model_name.lower():
            # Google Provider (Gemini & Gemma 4)
            target_model = model_name if model_name else model_candidates[0]
            api_key = os.getenv("GOOGLE_API_KEY") or settings.GOOGLE_API_KEY
            
            return ChatGoogleGenerativeAI(
                model=target_model, 
                google_api_key=api_key,
                temperature=temperature,
                streaming=True
            )
        elif ":" in model_name or "gemma" in model_name.lower():
            # Ollama
            return ChatOllama(
                model=model_name, 
                base_url=settings.OLLAMA_BASE_URL,
                temperature=temperature,
                streaming=True
            )
        else:
            # Groq
            return ChatGroq(
                model=model_name, 
                groq_api_key=settings.GROQ_API_KEY,
                temperature=temperature,
                streaming=True
            )

    def _extract_text(self, content: Union[str, List]) -> str:
        """콘텐츠가 리스트(thinking 블록 포함)인 경우 텍스트만 추출"""
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, str):
                    text_parts.append(part)
                elif isinstance(part, dict) and "text" in part:
                    text_parts.append(part["text"])
            return "".join(text_parts).strip()
        return ""

    def _prepare_messages(self, system_prompt: str, state_messages: List[BaseMessage]) -> List[BaseMessage]:
        """Gemini API의 User-AI 교차 규칙을 준수하도록 메시지 목록을 가공"""
        # 1. 시스템 프롬프트 설정
        final_messages = [SystemMessage(content=system_prompt)]
        
        if not state_messages:
            return final_messages

        # 2. 역할 정규화 및 연속된 역할 통합
        normalized = []
        for m in state_messages:
            # 역할 판별 (Human/System은 user로, 나머지는 assistant로 일단 분류)
            role = "user" if isinstance(m, (HumanMessage, SystemMessage)) else "assistant"
            content = self._extract_text(m.content)
            
            if not content: continue # 빈 메시지 스킵
            
            if normalized and normalized[-1]["role"] == role:
                # 같은 역할이 연속되면 내용 통합
                normalized[-1]["content"] += f"\n\n{content}"
            else:
                normalized.append({"role": role, "content": content})

        # 3. 제미나이 규칙 적용: 무조건 user로 시작, user로 끝남, 중간은 user-assistant 교차
        # 첫 번째가 assistant라면 user로 강제 변경
        if normalized and normalized[0]["role"] == "assistant":
            normalized[0]["role"] = "user"

        # 4. 최종 메시지 리스트 생성
        for i, entry in enumerate(normalized):
            # 마지막 메시지는 무조건 user여야 함
            if i == len(normalized) - 1:
                final_messages.append(HumanMessage(content=entry["content"]))
            elif entry["role"] == "user":
                final_messages.append(HumanMessage(content=entry["content"]))
            else:
                final_messages.append(AIMessage(content=entry["content"]))
                
        return final_messages

    async def agent_a_node(self, state: DebateState):
        persona = state['personas'].get('business', {})
        name = persona.get('name', '재복')
        instruction = persona.get('instruction', '당신은 비즈니스 분석가입니다.')
        
        model = state['models'].get('business', 'gemini-2.0-flash') 
        llm = self._get_llm(model)
        
        logger.info(f"--- [Agent A: {name}] node start ---")
        
        system_prompt = f"""You are {name}. {instruction}
Your role: 'Proposer' (Business Strategy).

STRICT RULES:
1. Speak ONLY in Korean. NO ENGLISH.
2. Be concise: 2-3 sentences.
3. Defend your position logically and professionally."""
        
        messages = [SystemMessage(content=system_prompt)] + state['messages']
        if not state['messages']:
            messages.append(HumanMessage(content=f"토론 주제: {state['topic']}"))
            
        # RPM 제한(15회) 준수: API 호출 전 4초 대기
        await asyncio.sleep(4)
        logger.debug(f"Agent A invoking LLM with {len(messages)} messages")
        response = await llm.ainvoke(messages)
        response.name = "agent_a"
        
        logger.info(f"Agent A response generated: {response.content[:50]}...")
        logger.info(f"Agent A state transition: next_speaker=agent_b")
        
        return {
            "messages": [response],
            "next_speaker": "agent_b",
            "turn_count": state['turn_count'] + 1
        }

    async def agent_b_node(self, state: DebateState):
        persona = state['personas'].get('tech', {})
        name = persona.get('name', '지영')
        instruction = persona.get('instruction', '당신은 기술 전문가입니다.')
        
        model = state['models'].get('tech', 'gemini-2.0-flash')
        llm = self._get_llm(model)
        
        logger.info(f"--- [Agent B: {name}] node start ---")
        
        system_prompt = f"""You are {name}. {instruction}
Your role: 'Critic' (Technical/Operational flaws).

STRICT RULES:
1. Speak ONLY in Korean. NO ENGLISH.
2. Be concise: 2-3 sentences.
3. Attack specific flaws: Cost, Security, or Scalability."""
        
        messages = self._prepare_messages(system_prompt, state['messages'])
        
        # RPM 제한(15회) 준수: API 호출 전 4초 대기
        await asyncio.sleep(4)
        logger.debug(f"Agent B invoking LLM with {len(messages)} messages")
        response = await llm.ainvoke(messages)
        response.name = "agent_b"
        
        logger.info(f"Agent B response generated: {response.content[:50]}...")
        logger.info(f"Agent B state transition: next_speaker=moderator")
        
        return {
            "messages": [response],
            "next_speaker": "moderator"
        }

    async def moderator_node(self, state: DebateState):
        """합의 여부 판단 (최소 4턴 보장)"""
        if state['turn_count'] < 4:
            logger.info(f"Moderator: Turn count {state['turn_count']} < 4, continuing.")
            return {"is_consented": False, "next_speaker": "agent_a"}

        # 비즈니스 에이전트가 사용하는 모델을 중재자용으로도 사용 (하드코딩 제거)
        model = state['models'].get('business', 'llama-3.1-70b-versatile')
        llm = self._get_llm(model, temperature=0.1)
        
        chat_history = "\n".join([f"{m.name}: {m.content}" for m in state['messages'][-4:]])
        
        prompt = f"""당신은 공정한 중재자입니다. 아래 두 사람의 대화를 보고 결론이 났는지 판단하세요.

대화 내용:
{chat_history}

판단 기준:
1. 두 사람이 서로의 의견에 동의했는가?
2. 구체적인 실행 방안이 도출되었는가?
3. 충분한 의견 교환이 이루어졌는가?

아직 토론이 더 필요하다고 판단되면 반드시 'NO'라고 답하세요.
완벽히 합의된 경우에만 'YES'라고만 답하세요."""
        
        # RPM 제한(15회) 준수: API 호출 전 4초 대기
        await asyncio.sleep(4)
        response = await llm.ainvoke(prompt)
        content = self._extract_text(response.content)
        is_consented = "YES" in content.upper()
        
        logger.info(f"Moderator decision: {'Consented' if is_consented else 'Not consented'}")
        
        return {
            "is_consented": is_consented,
            "next_speaker": "agent_a" if not is_consented else "summarize"
        }

    async def summarizer_node(self, state: DebateState):
        """토론 내용을 요약하고 최종 결론을 도출하여 DB에 저장"""
        model = state['models'].get('business', 'llama-3.1-70b-versatile')
        llm = self._get_llm(model, temperature=0.3)
        
        chat_history = "\n".join([f"{m.name}: {m.content}" for m in state['messages'] if m.name])
        
        prompt = f"""당신은 토론의 최종 의장입니다. 아래 진행된 전문가들의 토론 내용을 바탕으로 
최종 의사결정 결과 보고서를 작성하세요.

토론 주제: {state['topic']}
토론 내용:
{chat_history}

요구사항:
1. 결정된 사항이나 합의점을 명확히 기술할 것.
2. 향후 실행 계획을 1~2문장으로 포함할 것.
3. 한국어로 정중하게 작성할 것."""
        
        # RPM 제한(15회) 준수: API 호출 전 4초 대기
        await asyncio.sleep(4)
        response = await llm.ainvoke(prompt)
        
        # 벡터 DB에 저장
        try:
            await vector_service.save_decision(
                topic=state['topic'],
                content=response.content,
                metadata={"turn_count": state['turn_count']}
            )
        except Exception as e:
            print(f"Failed to save to vector DB: {e}")
            
        return {
            "messages": [AIMessage(content=response.content, name="moderator")],
            "next_speaker": "end"
        }

    def should_continue(self, state: DebateState):
        if state['is_consented'] or state['turn_count'] >= 10:
            return "summarize"
        return "agent_a"

    def create_debate_graph(self):
        workflow = StateGraph(DebateState)
        workflow.add_node("agent_a", self.agent_a_node)
        workflow.add_node("agent_b", self.agent_b_node)
        workflow.add_node("moderator", self.moderator_node)
        workflow.add_node("summarize", self.summarizer_node)
        
        workflow.set_entry_point("agent_a")
        workflow.add_edge("agent_a", "agent_b")
        workflow.add_edge("agent_b", "moderator")
        
        workflow.add_conditional_edges(
            "moderator", 
            self.should_continue, 
            {
                "agent_a": "agent_a", 
                "summarize": "summarize"
            }
        )
        workflow.add_edge("summarize", END)
        
        return workflow.compile()

    async def run_debate_stream(self, topic: str, models: dict = None, personas: dict = None) -> AsyncGenerator[str, None]:
        graph = self.create_debate_graph()
        state = {
            "topic": topic, "messages": [], "next_speaker": "agent_a", "turn_count": 0,
            "is_consented": False, "models": models or {}, "personas": personas or {}
        }
        
        finished_nodes = set()
        async for event in graph.astream_events(state, version="v2", config={"recursion_limit": 50}):
            kind = event["event"]
            if kind == "on_chain_start" and event["name"] in ["agent_a", "agent_b", "summarize"]:
                speaker_node = event["name"]
                if speaker_node in finished_nodes:
                    finished_nodes.remove(speaker_node)
                
                status_msg = "의장이 최종 결론을 작성 중..." if speaker_node == "summarize" else f"{speaker_node}가 생각 중..."
                yield json.dumps({
                    "type": "status", 
                    "content": status_msg, 
                    "node": speaker_node,
                    "turn": state.get('turn_count', 0)
                }) + "\n"
            
            elif kind == "on_chat_model_stream":
                tags = event.get("tags", [])
                if "langgraph_node:moderator" in tags:
                    continue
                    
                chunk = event["data"]["chunk"]
                if hasattr(chunk, "content"):
                    content = chunk.content
                    if content:
                        node = "unknown"
                        for tag in tags:
                            if tag.startswith("langgraph_node:"):
                                node = tag.split(":")[-1]
                                break
                        
                        if node in ["agent_a", "agent_b", "summarize"]:
                            yield json.dumps({
                                "type": "chunk", 
                                "node": node, 
                                "content": content,
                                "turn": state.get('turn_count', 0)
                            }) + "\n"

            elif kind == "on_chain_end" and event["name"] in ["agent_a", "agent_b", "summarize"]:
                output = event["data"]["output"]
                if "messages" in output:
                    last_msg = output["messages"][-1]
                    display_content = self._extract_text(last_msg.content)
                    
                    if display_content and len(display_content.strip()) > 0:
                        yield json.dumps({
                            "type": "node_done", 
                            "node": event["name"], 
                            "content": display_content,
                            "turn": state.get('turn_count', 0)
                        }) + "\n"
            
            elif kind == "on_chain_end" and event["name"] == "moderator":
                output = event["data"]["output"]
                if output.get("is_consented"):
                    yield json.dumps({"type": "status", "content": "합의 도달. 토론을 마칩니다.", "node": "moderator"}) + "\n"

    async def run_debate(self, topic: str, models: dict = None, personas: dict = None):
        graph = self.create_debate_graph()
        initial_state = {
            "topic": topic, "messages": [], "next_speaker": "agent_a", "turn_count": 0,
            "is_consented": False, "models": models or {}, "personas": personas or {}
        }
        return await graph.ainvoke(initial_state, config={"recursion_limit": 50})

debate_service = DebateService()
