"""
图像生成图（v4.0 完整版）
build_med_prompt → safety_check → generate_images → postprocess → save_images → END
"""
from langgraph.graph import StateGraph, END

from app.workflow.states import ImageGenState
from app.workflow.nodes.image_nodes import (
    build_med_prompt_node,
    safety_check_node,
    generate_images_node,
    postprocess_node,
    save_images_node,
)


def _route_after_safety(s: ImageGenState) -> str:
    return "generate_images" if not s.get("error") else "save_images"  # error 时跳过生成，直接到 save（空）


def build_image_gen_graph():
    """构建图像生成图"""
    graph = StateGraph(ImageGenState)
    graph.add_node("build_med_prompt", build_med_prompt_node)
    graph.add_node("safety_check", safety_check_node)
    graph.add_node("generate_images", generate_images_node)
    graph.add_node("postprocess", postprocess_node)
    graph.add_node("save_images", save_images_node)
    graph.set_entry_point("build_med_prompt")
    graph.add_edge("build_med_prompt", "safety_check")
    graph.add_conditional_edges("safety_check", _route_after_safety, {
        "generate_images": "generate_images",
        "save_images": "save_images",
    })
    graph.add_edge("generate_images", "postprocess")
    graph.add_edge("postprocess", "save_images")
    graph.add_edge("save_images", END)
    return graph.compile()


async def run_image_gen_graph(state: ImageGenState) -> ImageGenState:
    """执行图像生成图"""
    g = build_image_gen_graph()
    final = None
    async for s in g.astream(state):
        final = list(s.values())[0] if s else final
    return final or state
