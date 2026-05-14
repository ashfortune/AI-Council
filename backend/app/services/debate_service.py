from typing import Annotated, List, TypedDict, AsyncGenerator, Union
import operator
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
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
    def get_llm(self, model_name: str, temperature: float = 0.5): # 온도를 낮춤
        if "gemini" in model_name.lower():
            return ChatGoogleGenerativeAI(
                model=model_name,
                temperature=temperature,
                google_api_key=settings.GOOGLE_API_KEY,
                streaming=True
            )
        # Ollama 모델 사용 시 안정성을 위해 num_predict 등 파라미터 추가 고려
        return ChatOllama(
            model=model_name,
            temperature=temperature,
            base_url=settings.OLLAMA_BASE_URL,
            streaming=True,
            num_predict=256 # 응답 길이를 제한하여 반복 발산 방지
        )

    async def agent_a_node(self, state: DebateState):
        persona = state['personas'].get('business', {})
        name = persona.get('name', '재복')
        instruction = persona.get('instruction', '당신은 비즈니스 분석가입니다.')
        
        # 3b 모델보다는 최소 8b 모델 이상 사용 권장
        model = state['models'].get('business', 'llama3.1:8b') 
        llm = self.get_llm(model)
        
        system_prompt = f"""당신은 {name}입니다. {instruction}
제약 사항:
1. 반드시 한국어로만 말하십시오. 외국어 사용 금지.
2. 이전 대화 내용을 확인하고, 상대방의 의견에 대해 짧게 자기 생각을 말하세요.
3. 2~3문장 이내로 핵심만 말하고 질문으로 대화를 이어가세요.
4. 같은 말을 반복하지 마십시오."""
        
        messages = [SystemMessage(content=system_prompt)] + state['messages']
        if not state['messages']:
            messages.append(HumanMessage(content=f"토론 주제: {state['topic']}"))
            
        response = await llm.ainvoke(messages)
        response.name = "agent_a"
        
        return {
            "messages": [response],
            "next_speaker": "agent_b",
            "turn_count": state['turn_count'] + 1
        }

    async def agent_b_node(self, state: DebateState):
        persona = state['personas'].get('tech', {})
        name = persona.get('name', '지영')
        instruction = persona.get('instruction', '당신은 기술 전문가입니다.')
        
        model = state['models'].get('tech', 'llama3.1:8b')
        llm = self.get_llm(model)
        
        system_prompt = f"""당신은 {name}입니다. {instruction}
제약 사항:
1. 반드시 한국어로만 말하십시오. 외국어 사용 금지.
2. 상대방({state['personas'].get('business', {}).get('name', '재복')})의 마지막 제안에 대해 기술적 관점에서 의견을 주십시오.
3. 2~3문장 이내로 짧게 답변하십시오.
4. 같은 문구를 반복해서 출력하지 마십시오."""
        
        messages = [SystemMessage(content=system_prompt)] + state['messages']
        response = await llm.ainvoke(messages)
        response.name = "agent_b"
        
        return {
            "messages": [response],
            "next_speaker": "moderator"
        }

    async def moderator_node(self, state: DebateState):
        """합의 여부 판단 (최소 4턴 보장)"""
        if state['turn_count'] < 4:
            return {"is_consented": False, "next_speaker": "agent_a"}

        llm = self.get_llm("llama3.1:8b", temperature=0.1)
        
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
        
        response = await llm.ainvoke(prompt)
        is_consented = "YES" in response.content.upper()
        
        return {
            "is_consented": is_consented,
            "next_speaker": "agent_a" if not is_consented else "summarize"
        }

    async def summarizer_node(self, state: DebateState):
        """토론 내용을 요약하고 최종 결론을 도출하여 DB에 저장"""
        llm = self.get_llm("llama3.1:8b", temperature=0.3)
        
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
        
        async for event in graph.astream_events(state, version="v2", config={"recursion_limit": 50}):
            kind = event["event"]
            if kind == "on_chain_start" and event["name"] in ["agent_a", "agent_b", "summarize"]:
                speaker_node = event["name"]
                status_msg = "의장이 최종 결론을 작성 중..." if speaker_node == "summarize" else f"{speaker_node}가 생각 중..."
                yield json.dumps({"type": "status", "content": status_msg, "node": speaker_node}) + "\n"
            
            elif kind == "on_chat_model_stream":
                # 중재자(moderator)의 판단 과정은 스트리밍하지 않음
                tags = event.get("tags", [])
                if "langgraph_node:moderator" in tags:
                    continue
                    
                content = event["data"]["chunk"].content
                if content:
                    # tags에서 노드 이름 추출 (예: 'langgraph_node:agent_a')
                    node = "unknown"
                    for tag in tags:
                        if tag.startswith("langgraph_node:"):
                            node = tag.split(":")[-1]
                            break
                    
                    if node in ["agent_a", "agent_b", "summarize"] and content.strip():
                        yield json.dumps({"type": "chunk", "node": node, "content": content}) + "\n"

            elif kind == "on_chain_end" and event["name"] in ["agent_a", "agent_b", "summarize"]:
                output = event["data"]["output"]
                if "messages" in output:
                    last_msg = output["messages"][-1]
                    if last_msg.content.strip():
                        yield json.dumps({"type": "node_done", "node": event["name"], "content": last_msg.content}) + "\n"
            
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
