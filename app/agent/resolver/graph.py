"""매칭 해결 서브그래프: LLM 노드 ↔ 도구 노드 루프. 품목 하나마다 실행한다."""
import operator
from typing import Annotated, Optional, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

from app.agent.prompts import load_prompt
from app.agent.resolver.tools import Resolution, build_tools
from app.config import settings
from app.llm import estimate_cost, get_chat_model, model_name

MAX_TOOL_CALLS = 5


class ResolverState(TypedDict, total=False):
    customer_id: Optional[int]
    messages: Annotated[list[AnyMessage], operator.add]
    tool_calls: int
    resolution: Optional[Resolution]
    evidence: Annotated[list[dict], operator.add]   # 호출한 도구와 인자 (trace용)
    usage: Annotated[list[dict], operator.add]


def _usage(msg: AIMessage) -> dict:
    u = msg.usage_metadata or {}
    i, o = u.get("input_tokens", 0), u.get("output_tokens", 0)
    return {"node": "resolve_matches", "model": f"{settings.llm_provider}:{model_name()}",
            "input_tokens": i, "output_tokens": o, "cost_usd": estimate_cost("default", i, o)}


def agent(state: ResolverState) -> dict:
    tools = build_tools(state["customer_id"])
    # 도구 호출 한도에 도달하면 결론 제출만 허용한다
    must_submit = state.get("tool_calls", 0) >= MAX_TOOL_CALLS
    llm = get_chat_model().bind_tools(
        tools,
        tool_choice="submit_resolution" if must_submit else "required",
        parallel_tool_calls=False,
    )
    msg = llm.invoke(state["messages"])
    return {"messages": [msg], "usage": [_usage(msg)]}


def run_tools(state: ResolverState) -> dict:
    tools = {t.name: t for t in build_tools(state["customer_id"])}
    messages, evidence, resolution = [], [], None
    for call in state["messages"][-1].tool_calls:
        if call["name"] == "submit_resolution":
            resolution = Resolution(**call["args"])
            messages.append(ToolMessage("submitted", tool_call_id=call["id"]))
            continue
        result = tools[call["name"]].invoke(call["args"])
        messages.append(ToolMessage(result, tool_call_id=call["id"]))
        evidence.append({"tool": call["name"], "args": call["args"]})
    return {"messages": messages, "evidence": evidence, "resolution": resolution,
            "tool_calls": state.get("tool_calls", 0) + len(evidence)}


def route_after_agent(state: ResolverState):
    return "run_tools" if state["messages"][-1].tool_calls else END


def route_after_tools(state: ResolverState):
    return END if state.get("resolution") else "agent"


def build_resolver():
    builder = StateGraph(ResolverState)
    builder.add_node("agent", agent)
    builder.add_node("run_tools", run_tools)
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", route_after_agent, ["run_tools", END])
    builder.add_conditional_edges("run_tools", route_after_tools, ["agent", END])
    return builder.compile()


def initial_messages(raw_text: str, product_name: str, quantity, unit, customer_name: Optional[str],
                     candidates: list[dict]) -> list[AnyMessage]:
    lines = "\n".join(f"- {c['sku']} {c['name']} (유사도 {c['score']})" for c in candidates) or "(없음)"
    return [
        SystemMessage(load_prompt("resolve")),
        HumanMessage(
            f"거래처: {customer_name or '알 수 없음'}\n"
            f"<item>\n원문: {raw_text}\n품목명: {product_name}\n수량: {quantity}\n단위: {unit}\n</item>\n\n"
            f"초기 검색 후보:\n{lines}"
        ),
    ]
