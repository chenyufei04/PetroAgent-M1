"""面向实验方案解释的只读 Agent。"""

from __future__ import annotations

from difflib import SequenceMatcher
import json
from typing import Any, Callable

from petro_agent.llm.provider import LlmProvider


SECTION_IDS = {"overview", "metrics", "rules", "graph", "charts", "ranking", "evidence"}
TOPIC_WORDS = (
    "经济", "成本", "价值", "收入", "价格", "盈亏", "利润",
    "压力", "井底", "注入", "设施", "能力", "配聚", "供应", "约束",
    "产油", "增油", "含水", "产水", "采收", "效果",
    "排名", "最优", "推荐", "方案", "指标", "规则", "图谱", "证据", "曲线", "对比",
)


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
    def _fallback_answer(context: dict[str, Any]) -> str:
        """仅供 Mock 或模型故障降级使用，不再作为真实模型的参考答案。"""
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

    @staticmethod
    def _focused_facts(question: str, context: dict[str, Any]) -> tuple[list[dict], list[dict]]:
        """根据问题选择相关事实，避免每轮都把同一整包上下文交给模型。"""
        text = question.lower()
        groups = [
            (("经济", "成本", "价值", "收入", "价格", "盈亏", "利润"),
             ("cost", "value", "revenue", "price", "economic"), ("ECO", "RANK")),
            (("压力", "井底", "注入", "设施", "能力", "配聚", "供应", "约束"),
             ("pressure", "bhp", "rate", "mass", "injection", "facility"), ("OPS", "DESIGN")),
            (("产油", "增油", "含水", "产水", "采收", "效果"),
             ("oil", "water", "cut", "recovery", "performance"), ("PERF",)),
            (("排名", "最优", "推荐", "方案"), ("rank", "value", "oil"), ("RANK", "ECO")),
        ]
        metric_tokens: set[str] = set()
        rule_tokens: set[str] = set()
        for words, metric_fields, rule_prefixes in groups:
            if any(word in text for word in words):
                metric_tokens.update(metric_fields)
                rule_tokens.update(rule_prefixes)

        observations = [*(context.get("parameters") or []), *(context.get("metrics") or [])]
        # 复制规则并显式标记缺失单位，避免旧解释链被模型当成可自由补全的数据。
        rules = [
            {**item, "unit": item.get("unit") or "未记录（禁止猜测）"}
            for item in (context.get("rules") or [])
        ]
        if metric_tokens:
            focused_observations = [
                item for item in observations
                if any(token in f"{item.get('concept_id', '')} {item.get('source_field', '')}".lower() for token in metric_tokens)
            ]
        else:
            focused_observations = observations
        if rule_tokens:
            focused_rules = [
                item for item in rules
                if any(token in str(item.get("rule_id", "")).upper() for token in rule_tokens)
            ]
        else:
            focused_rules = rules
        return focused_observations or observations, focused_rules or rules

    @staticmethod
    def _similar(left: str, right: str) -> bool:
        """识别几乎重复的长回答，短状态词不参与重复判断。"""
        if min(len(left.strip()), len(right.strip())) < 35:
            return False
        return SequenceMatcher(None, left.strip(), right.strip()).ratio() >= 0.86

    @staticmethod
    def _needs_evidence_rewrite(answer: str, compact: dict[str, Any]) -> bool:
        """识别缺少数值证据或把演示规则夸大为工程结论的回答。"""
        overclaimed = compact.get("assumption_status") == "illustrative_unvalidated" and any(
            phrase in answer for phrase in ("安全", "现场可行", "技术上可行", "工程验证")
        )
        has_numeric_fact = any(
            isinstance(item.get("actual", item.get("value")), (int, float))
            for item in [*compact.get("relevant_observations", []), *compact.get("relevant_rules", [])]
        )
        cites_number = any(character.isdigit() for character in answer)
        return overclaimed or (has_numeric_fact and not cites_number)

    @staticmethod
    def _limit_claims(answer: str, assumption_status: str | None) -> str:
        """即使模型重写失败，也不允许演示性约束被表述成现场安全结论。"""
        if assumption_status != "illustrative_unvalidated":
            return answer
        for phrase in ("技术上可行", "现场可行", "处于安全范围内", "符合安全要求"):
            answer = answer.replace(phrase, "通过当前演示性配置规则")
        return answer

    @staticmethod
    def _evidence_fallback(compact: dict[str, Any]) -> str:
        """模型连续不合格时，用相关规则生成最小但可核验的工程回答。"""
        question = str(compact.get("question", ""))
        rules = compact.get("relevant_rules", [])
        # 优先选择消息文本与当前问题直接相交的规则，例如“压力”只取压力约束。
        selected = next(
            (
                item for item in rules
                if any(word in str(item.get("message", "")) for word in TOPIC_WORDS if word in question)
            ),
            next((item for item in rules if not item.get("passed", True)), rules[0] if rules else None),
        )
        if selected:
            actual = selected.get("actual")
            expected = selected.get("expected")
            unit = selected.get("unit")
            unit_text = "" if not unit or str(unit).startswith("未记录") else f" {unit}"
            status = "通过" if selected.get("passed") else "未通过"
            qualifier = (
                "当前演示性配置规则"
                if compact.get("assumption_status") == "illustrative_unvalidated"
                else "当前配置规则"
            )
            return (
                f"{selected.get('message', '该项约束')}：实际值为 {actual}{unit_text}，"
                f"阈值为 {expected}{unit_text}，因此{status}{qualifier}。"
            )
        return "当前结构化证据不足，无法可靠回答这一问题。"

    def chat(
        self,
        experiment_id: str,
        case_id: str,
        question: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        context = self.context_loader(experiment_id, case_id)
        history = (history or [])[-10:]
        recent_user = " ".join(item["content"] for item in history[-4:] if item.get("role") == "user")
        # 明确提出新主题时只检索新主题；“再详细一点”等省略追问才继承上一轮主题。
        has_explicit_topic = any(word in question for word in TOPIC_WORDS)
        retrieval_query = question if has_explicit_topic else f"{recent_user} {question}".strip()
        suggested_sections = self._sections(retrieval_query)
        observations, rules = self._focused_facts(retrieval_query, context)
        compact = {
            "question": question,
            "selected_case_id": case_id,
            "suggested_sections": suggested_sections,
            "scenario": context.get("scenario", {}),
            "relevant_observations": observations,
            "relevant_rules": rules,
            "recommendation": context.get("recommendation", {}),
            "evidence": context.get("evidence", {}),
            "assumption_status": (context.get("evidence") or {}).get("assumption_status")
            or (context.get("recommendation") or {}).get("assumption_status"),
        }
        system = (
            "你是 PetroAgent 的石油工程分析助手。回答当前问题，不要机械复述完整方案摘要。"
            "优先给出直接结论，再引用最相关的实际值、阈值和规则解释原因；只讨论与问题相关的事实。"
            "要承接最近对话，用户说‘再详细一点’或‘那压力呢’时必须理解上一轮主题。"
            "不要重复上一轮已经说过的整段内容；如需引用，只简短承接并补充新信息。"
            "只能使用最后一条用户消息中提供的结构化工程事实，不得重算模拟值、虚构因果、"
            "修改规则或替代工程师审批。事实不足时明确说明缺少什么；事实未提供单位时禁止猜测单位。"
            "当 assumption_status 为 illustrative_unvalidated 时，只能说‘通过当前演示性配置规则’，"
            "不得表述为安全、现场可行或已经工程验证。"
            "返回 JSON 对象，字段为 answer、sections、selected_case_id；answer 使用自然、专业、简洁的中文。"
            f"sections 只能取 {sorted(SECTION_IDS)}。"
        )
        if self.provider.name == "mock":
            compact["draft_answer"] = self._fallback_answer(context)
        # 当前问题已经明确切换主题时，不把旧助手答案继续喂给模型，避免它先复述旧结论。
        model_history = history if not has_explicit_topic else []
        messages = [{"role": "system", "content": system}, *model_history]
        messages.append({"role": "user", "content": json.dumps(compact, ensure_ascii=False)})
        generated = self.provider.generate_json(messages)
        answer = str(generated.get("answer") or self._fallback_answer(context))

        previous_answer = next(
            (item["content"] for item in reversed(history) if item.get("role") == "assistant"), ""
        )
        if self.provider.name != "mock" and previous_answer and self._similar(answer, previous_answer):
            retry = {
                **compact,
                "previous_answer": previous_answer,
                "rewrite_instruction": "上一版与前文重复。只回答本轮新增问题，引用不同的相关事实，避免重复开场和总结。",
            }
            generated = self.provider.generate_json([
                {"role": "system", "content": system},
                *model_history,
                {"role": "user", "content": json.dumps(retry, ensure_ascii=False)},
            ])
            answer = str(generated.get("answer") or answer)
        if self.provider.name != "mock" and self._needs_evidence_rewrite(answer, compact):
            generated = self.provider.generate_json([
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps({
                    **compact,
                    "rewrite_instruction": (
                        "重写回答：必须引用至少一个相关实际值、阈值和已有单位；"
                        "这些约束未经现场验证，只能称为通过当前演示性配置规则。"
                    ),
                }, ensure_ascii=False)},
            ])
            answer = str(generated.get("answer") or answer)
        answer = self._limit_claims(answer, compact.get("assumption_status"))
        if self.provider.name != "mock" and self._needs_evidence_rewrite(answer, compact):
            answer = self._evidence_fallback(compact)
        return {
            "answer": answer,
            # 页面展示由确定性意图规则决定，模型不能注入未知区域或切换到其他方案。
            "display": {"sections": suggested_sections, "selected_case_id": case_id},
            "sources": [
                {"type": "scenario_context", "id": case_id},
                {"type": "evidence", "id": context.get("evidence", {}).get("source_id")},
            ],
            "model": {"provider": self.provider.name},
            "guardrails": {"read_only": True, "deterministic_values_preserved": True},
        }
