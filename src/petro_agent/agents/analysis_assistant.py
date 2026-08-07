"""面向实验方案解释的只读 Agent。"""

from __future__ import annotations

from typing import Any, Callable

from petro_agent.llm.provider import LlmProvider


SECTION_IDS = {"overview", "metrics", "rules", "graph", "charts", "ranking", "evidence"}


class AnalysisAssistant:
    """把用户问题转换为受控页面指令，并让模型仅基于检索事实组织答案。"""

    def __init__(self, provider: LlmProvider, context_loader: Callable[[str, str], dict[str, Any]]):
        self.provider = provider
        self.context_loader = context_loader

    @staticmethod
    def _sections(question: str) -> list[str]:
        text = question.lower()
        sections = ["overview"]
        mapping = {
            "metrics": ("指标", "产油", "含水", "压力", "成本", "价值", "参数"),
            "rules": ("规则", "约束", "通过", "失败", "为什么", "原因"),
            "graph": ("图谱", "关系", "解释链", "知识"),
            "charts": ("图", "曲线", "趋势", "敏感性", "对比"),
            "ranking": ("排名", "最优", "方案", "推荐"),
            "evidence": ("证据", "来源", "依据", "可信"),
        }
        for section, keywords in mapping.items():
            if any(keyword in text for keyword in keywords):
                sections.append(section)
        return list(dict.fromkeys(sections if len(sections) > 1 else ["overview", "metrics", "rules", "graph"]))

    @staticmethod
    def _draft(context: dict[str, Any]) -> str:
        recommendation = context.get("recommendation", {})
        scenario = context.get("scenario", {})
        failed = [item for item in context.get("rules", []) if not item.get("passed")]
        answer = [f"当前方案结论：{recommendation.get('decision') or scenario.get('recommendation') or '暂无结论'}。"]
        if scenario.get("scenario_rank") is not None:
            answer.append(f"方案排名为第 {scenario['scenario_rank']}。")
        if scenario.get("net_incremental_value") is not None:
            answer.append(f"净增量价值为 {scenario['net_incremental_value']:,.2f} {scenario.get('currency', '')}。")
        if failed:
            answer.append("未通过规则：" + "；".join(f"{item.get('rule_id')}（{item.get('message')}）" for item in failed) + "。")
        else:
            answer.append("当前检索到的规则均已通过。")
        return "".join(answer)

    def chat(self, experiment_id: str, case_id: str, question: str) -> dict[str, Any]:
        context = self.context_loader(experiment_id, case_id)
        suggested_sections = self._sections(question)
        compact = {
            "question": question,
            "selected_case_id": case_id,
            "suggested_sections": suggested_sections,
            "draft_answer": self._draft(context),
            "scenario": context.get("scenario", {}),
            "parameters": context.get("parameters", []),
            "metrics": context.get("metrics", []),
            "rules": context.get("rules", []),
            "recommendation": context.get("recommendation", {}),
            "evidence": context.get("evidence", {}),
        }
        system = (
            "你是 PetroAgent 石油工程分析助手。只能使用用户消息中的检索事实回答；"
            "不得重算模拟值、虚构规则或替代工程师审批。返回 JSON，字段为 answer、sections、selected_case_id。"
            f"sections 只能取 {sorted(SECTION_IDS)}。"
        )
        generated = self.provider.generate_json([
            {"role": "system", "content": system},
            {"role": "user", "content": __import__("json").dumps(compact, ensure_ascii=False)},
        ])
        sections = [item for item in generated.get("sections", []) if item in SECTION_IDS]
        return {
            "answer": str(generated.get("answer") or compact["draft_answer"]),
            "display": {"sections": sections or suggested_sections, "selected_case_id": case_id},
            "sources": [
                {"type": "scenario_context", "id": case_id},
                {"type": "evidence", "id": context.get("evidence", {}).get("source_id")},
            ],
            "model": {"provider": self.provider.name},
            "guardrails": {"read_only": True, "deterministic_values_preserved": True},
        }
