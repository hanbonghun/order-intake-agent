from langgraph.graph import END, START, StateGraph

from app.agent.nodes.classify import classify
from app.agent.nodes.customer import identify_customer
from app.agent.nodes.extract import extract
from app.agent.nodes.inquiry import await_reply, draft_inquiry, merge_reply
from app.agent.nodes.match import match_products
from app.agent.nodes.order import create_order, draft_confirmation
from app.agent.nodes.parse import parse_document
from app.agent.nodes.resolve import resolve_matches
from app.agent.nodes.validate import validate
from app.agent.state import OrderState


def route_after_classify(state: OrderState):
    return "extract" if state["is_order"] else END


def route_after_match(state: OrderState):
    unresolved = any(m.status in ("ambiguous", "not_found") for m in state.get("matched_items", []))
    return "resolve_matches" if unresolved else "validate"


def route_after_validate(state: OrderState):
    return {
        "create": "create_order",
        "inquire": "draft_inquiry",
        "review": END,    # TODO: human_review (interrupt)
    }[state["decision"]]


def build_graph(checkpointer=None):
    builder = StateGraph(OrderState)
    builder.add_node("parse_document", parse_document)
    builder.add_node("classify", classify)
    builder.add_node("extract", extract)
    builder.add_node("identify_customer", identify_customer)
    builder.add_node("match_products", match_products)
    builder.add_node("resolve_matches", resolve_matches)
    builder.add_node("validate", validate)
    builder.add_node("create_order", create_order)
    builder.add_node("draft_confirmation", draft_confirmation)
    builder.add_node("draft_inquiry", draft_inquiry)
    builder.add_node("await_reply", await_reply)
    builder.add_node("merge_reply", merge_reply)

    builder.add_edge(START, "parse_document")
    builder.add_edge("parse_document", "classify")
    builder.add_conditional_edges("classify", route_after_classify, ["extract", END])
    builder.add_edge("extract", "identify_customer")
    builder.add_edge("identify_customer", "match_products")
    builder.add_conditional_edges("match_products", route_after_match, ["resolve_matches", "validate"])
    builder.add_edge("resolve_matches", "validate")
    builder.add_conditional_edges("validate", route_after_validate, ["create_order", "draft_inquiry", END])
    # 재질의 루프: 회신을 반영해 매칭부터 다시
    builder.add_edge("draft_inquiry", "await_reply")
    builder.add_edge("await_reply", "merge_reply")
    builder.add_edge("merge_reply", "match_products")
    builder.add_edge("create_order", "draft_confirmation")
    builder.add_edge("draft_confirmation", END)

    return builder.compile(checkpointer=checkpointer)
