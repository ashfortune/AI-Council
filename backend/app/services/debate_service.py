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
        model_candidates = ["gemini-3.1-flash-lite", "gemini-2.5-flash", "gemini-flash-latest", "gemma-4-31b-it"]
        
        if not model_name or "gemini" in model_name.lower() or "gemma" in model_name.lower():
            # Google Provider (Gemini & Gemma 4)
            target_model = model_name if model_name else model_candidates[0]
            api_key = os.getenv("GOOGLE_API_KEY") or settings.GOOGLE_API_KEY
            
            return ChatGoogleGenerativeAI(
                model=target_model, 
                google_api_key=api_key,
                temperature=temperature,
                max_retries=2,
                timeout=30,
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
                elif isinstance(part, dict):
                    if "text" in part and part["text"]:
                        text_parts.append(part["text"])
                    elif "thinking" in part and part["thinking"]:
                        text_parts.append(part["thinking"])
            res = "\n\n".join(text_parts).strip()
            return res if res else str(content).strip()
        return str(content).strip()

    def _format_debate_prompt(self, system_prompt: str, state_messages: List[BaseMessage], current_node: str) -> List[BaseMessage]:
        """발화자 식별 기반 역할 분리 및 Gemini User-AI 교차 규칙 정규화"""
        final_messages = [SystemMessage(content=system_prompt)]
        
        if not state_messages:
            return final_messages

        # 슬라이딩 윈도우: 최근 6개의 턴만 유지 (에코 루프 방지 및 Rate Limit 경감)
        recent_messages = state_messages[-6:]
        
        normalized = []
        for m in recent_messages:
            content = self._extract_text(m.content)
            if not content: continue
            
            speaker_node = getattr(m, 'name', None) or "unknown"
            # 현재 노드와 메시지 작성자가 같으면 본인의 과거 발화(assistant), 다르면 상대방의 의견(user)
            role = "assistant" if speaker_node == current_node else "user"
            
            # 발화자 명시 포맷팅으로 컨텍스트 혼동 차단
            display_name = "사업총괄 CBO" if speaker_node == "agent_a" else ("기술총괄 CTO" if speaker_node == "agent_b" else "참여자")
            formatted_content = f"[{display_name}의 의견]:\n{content}" if role == "user" else content
            
            if normalized and normalized[-1]["role"] == role:
                normalized[-1]["content"] += f"\n\n{formatted_content}"
            else:
                normalized.append({"role": role, "content": formatted_content})

        # Gemini API 규칙 보장: 첫 번째 메시지는 user로 시작
        if normalized and normalized[0]["role"] == "assistant":
            normalized[0]["role"] = "user"

        # 마지막 메시지는 무조건 user로 끝나야 함 (상대방의 최근 의견에 대한 반박 구조)
        if normalized and normalized[-1]["role"] == "assistant":
            normalized[-1]["role"] = "user"

        for entry in normalized:
            if entry["role"] == "user":
                final_messages.append(HumanMessage(content=entry["content"]))
            else:
                final_messages.append(AIMessage(content=entry["content"]))
                
        return final_messages

    async def agent_a_node(self, state: DebateState):
        persona = state['personas'].get('business', {})
        name = persona.get('name') or '사업총괄 CBO'
        instruction = persona.get('instruction') or '당신은 기업의 비즈니스 전략 및 수익성을 총괄하는 최고비즈니스책임자입니다.'
        
        model = state['models'].get('business', 'gemini-2.0-flash') 
        llm = self._get_llm(model)
        
        logger.info(f"--- [Agent A: {name}] node start ---")
        
        # RAG 검색: 과거 유사 판단 이력 조회
        rag_docs = await vector_service.search_similar_decisions(state['topic'], k=2)
        rag_context = ""
        if rag_docs:
            rag_text = "\n\n".join([f"사례 {i+1}:\n{doc.page_content}" for i, doc in enumerate(rag_docs)])
            rag_context = f"\n\n[과거 유사 의사결정 참고자료 (RAG Reference)]:\n{rag_text}"
        
        system_prompt = f"""당신의 이름(역할)은 {name}입니다.
다음 지침에 따라 안건에 대해 발언하세요:
{instruction}

핵심 토론 안건 (CORE DEBATE TOPIC - 절대 안건에서 이탈하지 마세요): {state['topic']}
{rag_context}

STRICT RULES:
1. 답변은 반드시 한국어로만 작성하세요 (NO ENGLISH).
2. 분량은 2~3문장으로 핵심만 간결하게 전달하세요.
3. 주어진 안건({state['topic']}) 및 자신의 역할({name})에 완벽히 몰입하여 상대방의 의견에 논리적으로 대응하세요.
4. 절대 이전 주장을 그대로 앵무새처럼 반복하지 말고, 상대방의 직전 발언을 직접 언급하며 새로운 논거나 절충안을 제시하세요."""
        
        if not state['messages']:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"오늘의 토론 안건: {state['topic']}\n이에 대한 제안과 의견을 말씀해주세요.")
            ]
        else:
            messages = self._format_debate_prompt(system_prompt, state['messages'], current_node="agent_a")
            
        await asyncio.sleep(4)
        logger.debug(f"Agent A invoking LLM with {len(messages)} messages")
        response = await llm.ainvoke(messages)
        
        clean_content = self._extract_text(response.content)
        final_msg = AIMessage(content=clean_content, name="agent_a")
        
        logger.info(f"Agent A response generated: {clean_content[:50]}...")
        logger.info(f"Agent A state transition: next_speaker=agent_b")
        
        return {
            "messages": [final_msg],
            "next_speaker": "agent_b",
            "turn_count": state['turn_count'] + 1
        }

    async def agent_b_node(self, state: DebateState):
        persona = state['personas'].get('tech', {})
        name = persona.get('name') or '기술총괄 CTO'
        instruction = persona.get('instruction') or '당신은 기업의 아키텍처, 시스템 안정성 및 기술적 타당성을 총괄하는 최고기술책임자입니다.'
        
        model = state['models'].get('tech', 'gemini-2.0-flash')
        llm = self._get_llm(model)
        
        logger.info(f"--- [Agent B: {name}] node start ---")
        
        # RAG 검색: 과거 유사 판단 이력 조회
        rag_docs = await vector_service.search_similar_decisions(state['topic'], k=2)
        rag_context = ""
        if rag_docs:
            rag_text = "\n\n".join([f"사례 {i+1}:\n{doc.page_content}" for i, doc in enumerate(rag_docs)])
            rag_context = f"\n\n[과거 유사 의사결정 참고자료 (RAG Reference)]:\n{rag_text}"
        
        system_prompt = f"""당신의 이름(역할)은 {name}입니다.
다음 지침에 따라 안건에 대해 발언하세요:
{instruction}

핵심 토론 안건 (CORE DEBATE TOPIC - 절대 안건에서 이탈하지 마세요): {state['topic']}
{rag_context}

STRICT RULES:
1. 답변은 반드시 한국어로만 작성하세요 (NO ENGLISH).
2. 분량은 2~3문장으로 핵심만 간결하게 전달하세요.
3. 주어진 안건({state['topic']}) 및 자신의 역할({name})에 완벽히 몰입하여 상대방의 의견에 논리적으로 대응하세요.
4. 절대 이전 주장을 그대로 앵무새처럼 반복하지 말고, 상대방의 직전 발언을 직접 언급하며 새로운 논거나 절충안을 제시하세요."""
        
        messages = self._format_debate_prompt(system_prompt, state['messages'], current_node="agent_b")
        
        await asyncio.sleep(4)
        logger.debug(f"Agent B invoking LLM with {len(messages)} messages")
        response = await llm.ainvoke(messages)
        
        clean_content = self._extract_text(response.content)
        final_msg = AIMessage(content=clean_content, name="agent_b")
        
        logger.info(f"Agent B response generated: {clean_content[:50]}...")
        logger.info(f"Agent B state transition: next_speaker=moderator")
        
        return {
            "messages": [final_msg],
            "next_speaker": "moderator"
        }

    async def moderator_node(self, state: DebateState):
        """합의 여부 판단 (2턴부터 즉시 판별)"""
        if state['turn_count'] < 2:
            logger.info(f"Moderator: Turn count {state['turn_count']} < 2, continuing.")
            return {"is_consented": False, "next_speaker": "agent_a"}

        # 의장(중재자) 모델 고정
        model = "gemini-3.1-flash-lite"
        llm = self._get_llm(model, temperature=0.1)
        
        chat_history = "\n".join([f"{m.name}: {m.content}" for m in state['messages'][-4:]])
        
        prompt = f"""당신은 토론의 공정한 중재자(의장)입니다. 아래 대화를 분석하여 두 발언자가 최종 합의에 도달했는지 판단하세요.

[대화 내용]:
{chat_history}

[합의 도달 판별 기준 - CRITICAL]:
1. 한쪽이 제안한 안건(메뉴, 전략, 절충안 등)에 대해 상대방이 명확히 수락하고 동의를 표명했는가?
2. 상호 간에 더 이상의 반박, 이견, 혹은 추가 요구사항 없이 긍정적으로 마무리가 되고 있는가? ("결정해요", "좋아요", "그렇게 진행합시다" 등)
3. 이미 합의가 끝나서 서로 인사말("얼른 가자", "오늘 하루도 수고하셨습니다")이나 칭찬을 반복하고 있는 상태라면 반드시 합의 도달로 판정해야 합니다.

[출력 형식]:
합의에 도달했다고 판단되면 반드시 오직 [CONSENT_REACHED: YES] 라고만 출력하세요.
아직 이견이 남아있어 토론이 더 필요하다면 오직 [CONSENT_REACHED: NO] 라고만 출력하세요."""
        
        # RPM 제한(15회) 준수: API 호출 전 4초 대기
        await asyncio.sleep(4)
        response = await llm.ainvoke(prompt)
        content = self._extract_text(response.content)
        is_consented = "[CONSENT_REACHED: YES]" in content.upper() or "CONSENT_REACHED: YES" in content.upper()
        
        logger.info(f"Moderator decision: {'Consented' if is_consented else 'Not consented'} (raw content: {content.strip()})")
        
        return {
            "is_consented": is_consented,
            "next_speaker": "agent_a" if not is_consented else "summarize"
        }

    async def summarizer_node(self, state: DebateState):
        """토론 내용을 요약하고 최종 결론을 도출하여 DB에 저장"""
        # 의장(최종 결론) 모델 고정
        model = "gemini-3.1-flash-lite"
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
        
        current_turn = 1
        agent_a_started_count = 0
        finished_nodes = set()
        
        async for event in graph.astream_events(state, version="v2", config={"recursion_limit": 50}):
            kind = event["event"]
            if kind == "on_chain_start" and event["name"] in ["agent_a", "agent_b", "summarize"]:
                speaker_node = event["name"]
                if speaker_node == "agent_a":
                    agent_a_started_count += 1
                    if agent_a_started_count > 1:
                        current_turn += 1

                if speaker_node in finished_nodes:
                    finished_nodes.remove(speaker_node)
                
                status_msg = "의장이 최종 결론을 작성 중..." if speaker_node == "summarize" else f"{speaker_node}가 생각 중..."
                yield json.dumps({
                    "type": "status", 
                    "content": status_msg, 
                    "node": speaker_node,
                    "turn": current_turn
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
                                "turn": current_turn
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
                            "turn": current_turn
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
