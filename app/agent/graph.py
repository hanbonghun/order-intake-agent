from langgraph.graph import END, START, StateGraph

from app.agent.nodes.classify import classify
from app.agent.nodes.customer import identify_customer
from app.agent.nodes.extract import extract
from app.agent.nodes.parse import parse_document
from app.agent.nodes.stubs import create_order, draft_confirmation, match_products, validate
from app.agent.state import OrderState


def route_after_classify(state: OrderState):
    return "extract" if state["is_order"] else END


def route_after_validate(state: OrderState):
    return {
        "create": "create_order",
        "inquire": END,   # 2단계: draft_inquiry
        "review": END,    # 2단계: human_review
    }[state["decision"]]


def build_graph(checkpointer=None):
    builder = StateGraph(OrderState)
    builder.add_node("parse_document", parse_document)
    builder.add_node("classify", classify)
    builder.add_node("extract", extract)
    builder.add_node("identify_customer", identify_customer)
    builder.add_node("match_products", match_products)
    builder.add_node("validate", validate)
    builder.add_node("create_order", create_order)
    builder.add_node("draft_confirmation", draft_confirmation)

    builder.add_edge(START, "parse_document")
    builder.add_edge("parse_document", "classify")
    builder.add_conditional_edges("classify", route_after_classify, ["extract", END])
    builder.add_edge("extract", "identify_customer")
    builder.add_edge("identify_customer", "match_products")
    builder.add_edge("match_products", "validate")
    builder.add_conditional_edges("validate", route_after_validate, ["create_order", END])
    builder.add_edge("create_order", "draft_confirmation")
    builder.add_edge("draft_confirmation", END)

    return builder.compile(checkpointer=checkpointer)
