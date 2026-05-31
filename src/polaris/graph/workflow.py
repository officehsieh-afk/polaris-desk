"""LangGraph 5 節點 Workflow 骨架（@R2）。

流水線：Planner → Retriever → Calculator → Writer → Compliance
W1 目標：5 節點串成一條，每節點先回假資料，能端到端跑一次（v0）。
langgraph 採延遲 import，未安裝時 `import polaris` 仍正常。
"""
from __future__ import annotations

from typing import Any, TypedDict


class PolarisState(TypedDict, total=False):
    """流程在各節點間傳遞的狀態（共用記憶）。"""
    query: str
    plan: list[str]
    contexts: list[dict[str, Any]]
    calculations: dict[str, Any]
    draft: str
    answer: str
    compliance_ok: bool


# --- 各節點（v0 先回假資料，之後接真實實作）---
def planner(state: PolarisState) -> PolarisState:
    # TODO(@R2/@R3)：把 query 拆成步驟
    return {"plan": ["（v0 假步驟）擷取相關段落", "計算指標", "撰寫並標引用"]}


def retriever(state: PolarisState) -> PolarisState:
    # TODO(@R3)：呼叫 HybridRetriever
    return {"contexts": []}


def calculator(state: PolarisState) -> PolarisState:
    # TODO(@R3)：財務指標計算，數字要 grounding 到來源
    return {"calculations": {}}


def writer(state: PolarisState) -> PolarisState:
    # TODO(@R3)：逐句標引用地寫成答案
    return {"draft": "（v0 假答案）", "answer": "（v0 假答案）"}


def compliance(state: PolarisState) -> PolarisState:
    # TODO(@R6/@R3)：NFR-031 檢查 —— 不得出現買賣建議
    return {"compliance_ok": True}


def build_workflow():
    """組裝 LangGraph。回傳 compiled graph。"""
    from langgraph.graph import END, StateGraph  # 延遲 import

    g = StateGraph(PolarisState)
    g.add_node("planner", planner)
    g.add_node("retriever", retriever)
    g.add_node("calculator", calculator)
    g.add_node("writer", writer)
    g.add_node("compliance", compliance)

    g.set_entry_point("planner")
    g.add_edge("planner", "retriever")
    g.add_edge("retriever", "calculator")
    g.add_edge("calculator", "writer")
    g.add_edge("writer", "compliance")
    g.add_edge("compliance", END)
    return g.compile()


if __name__ == "__main__":
    app = build_workflow()
    print(app.invoke({"query": "台積電最近兩季毛利率趨勢？"}))
