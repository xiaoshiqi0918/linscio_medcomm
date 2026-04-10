"""
MedComm 通用写作图（v5.0 完整版）
mode_detect → retrieve_context → context_check → retrieve_examples → inject_terms
  → format_route → generate_new|generate_continue → quality_check
  → verify_medical_claims → check_reading_level → suggest_images → normalize_terms → save → END
  → save_partial → END
  → regenerate_* → 回到 generate
"""
from langgraph.graph import StateGraph, END

from app.workflow.states import MedCommSectionState
from app.workflow.nodes.medcomm_nodes import (
    mode_detect_node,
    retrieve_context_node,
    context_check_node,
    retrieve_examples_node,
    inject_terms_node,
    format_route_node,
    generate_new_node,
    generate_continue_node,
    quality_check_node,
    verify_medical_claims_node,
    check_reading_level_node,
    suggest_images_node,
    normalize_terms_node,
    save_node,
    save_partial_node,
)


def _route_after_mode(s: MedCommSectionState) -> str:
    return "retrieve_context"


def _route_after_format(s: MedCommSectionState) -> str:
    return "generate_new" if s.get("generate_mode") == "new" else "generate_continue"


def _route_after_quality_check(s: MedCommSectionState) -> str:
    n = s.get("next", "verify_medical_claims")
    if n == "regenerate":
        return "regenerate_new" if s.get("generate_mode") == "new" else "regenerate_continue"
    return n


def build_medcomm_article_graph():
    """构建 MedComm 写作图"""
    graph = StateGraph(MedCommSectionState)

    # 通用节点
    graph.add_node("mode_detect", mode_detect_node)
    graph.add_node("retrieve_context", retrieve_context_node)
    graph.add_node("context_check", context_check_node)
    graph.add_node("retrieve_examples", retrieve_examples_node)
    graph.add_node("inject_terms", inject_terms_node)
    graph.add_node("format_route", format_route_node)
    graph.add_node("generate_new", generate_new_node)
    graph.add_node("generate_continue", generate_continue_node)
    graph.add_node("quality_check", quality_check_node)
    graph.add_node("verify_medical_claims", verify_medical_claims_node)
    graph.add_node("check_reading_level", check_reading_level_node)
    graph.add_node("suggest_images", suggest_images_node)
    graph.add_node("normalize_terms", normalize_terms_node)
    graph.add_node("save", save_node)
    graph.add_node("save_partial", save_partial_node)
    # error_handler 节点已实现，LangGraph 0.2 无 add_error_handler，异常由调用方 try/except 处理

    # 边
    graph.set_entry_point("mode_detect")
    graph.add_edge("mode_detect", "retrieve_context")
    graph.add_edge("retrieve_context", "context_check")
    graph.add_edge("context_check", "retrieve_examples")
    graph.add_edge("retrieve_examples", "inject_terms")
    graph.add_edge("inject_terms", "format_route")
    graph.add_conditional_edges("format_route", _route_after_format, {
        "generate_new": "generate_new",
        "generate_continue": "generate_continue",
    })
    graph.add_edge("generate_new", "quality_check")
    graph.add_edge("generate_continue", "quality_check")
    graph.add_conditional_edges("quality_check", _route_after_quality_check, {
        "regenerate_new": "generate_new",
        "regenerate_continue": "generate_continue",
        "verify_medical_claims": "verify_medical_claims",
        "save_partial": "save_partial",
    })
    graph.add_edge("verify_medical_claims", "check_reading_level")
    graph.add_edge("check_reading_level", "suggest_images")
    graph.add_edge("suggest_images", "normalize_terms")
    graph.add_edge("normalize_terms", "save")
    graph.add_edge("save", END)
    graph.add_edge("save_partial", END)

    return graph.compile()


async def run_medcomm_graph(state: MedCommSectionState) -> MedCommSectionState:
    """执行 MedComm 写作图"""
    g = build_medcomm_article_graph()
    final = None
    async for s in g.astream(state):
        final = list(s.values())[0] if s else final
    return final or state
