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
    "排名", "最优", "推荐", "方案", "第一名", "第二名", "优于",
    "指标", "规则", "图谱", "证据", "曲线", "对比",
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
            "ranking": ("排名", "最优", "方案", "推荐", "第一名", "第二名", "优于"),
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

    @staticmethod
    def _ranking_display_answer(context: dict[str, Any], case_id: str) -> str:
        """对纯排名展示指令返回与页面同源的摘要，不让模型误答成单方案解释。"""
        rankings = sorted(
            context.get("rankings") or [],
            key=lambda item: item.get("scenario_rank") if item.get("scenario_rank") is not None else float("inf"),
        )
        if not rankings:
            return "当前实验尚未生成方案排名，无法展示全部方案。"

        def row_case_id(row: dict[str, Any]) -> str:
            # 优先使用通用 case_id；兼容当前聚合物分析产物中的 polymer_case_id。
            return str(row.get("case_id") or row.get("polymer_case_id") or "未知方案")

        current = next((row for row in rankings if row_case_id(row) == case_id), None)
        current_text = (
            f"当前选中方案排名第 {current.get('scenario_rank')}。" if current else "当前方案不在排名表中。"
        )
        top_items = []
        for row in rankings[:3]:
            details = []
            if row.get("net_incremental_value") is not None:
                details.append(f"净增量价值 {row['net_incremental_value']:,.2f} {row.get('currency') or ''}".strip())
            if row.get("incremental_oil_m3") is not None:
                details.append(f"增量油 {row['incremental_oil_m3']:,.2f} m3")
            suffix = f"（{'，'.join(details)}）" if details else ""
            top_items.append(f"#{row.get('scenario_rank')} {row_case_id(row)}{suffix}")
        return (
            f"已展示当前实验的全部 {len(rankings)} 个方案排名。{current_text}"
            f"前三名为：{'；'.join(top_items)}。排名表中的数值来自确定性技术经济分析。"
        )

    @staticmethod
    def _ranking_comparison_answer(context: dict[str, Any]) -> str:
        """用同一排名表直接比较前两名，避免模型遗漏被比较方案或混淆排序目标。"""
        rankings = sorted(
            context.get("rankings") or [],
            key=lambda item: item.get("scenario_rank") if item.get("scenario_rank") is not None else float("inf"),
        )
        if len(rankings) < 2:
            return "当前排名表不足两个方案，无法进行第一名与第二名比较。"
        first, second = rankings[:2]

        def case_id(row: dict[str, Any]) -> str:
            return str(row.get("case_id") or row.get("polymer_case_id") or "未知方案")

        currency = first.get("currency") or second.get("currency") or ""
        first_net = first.get("net_incremental_value")
        second_net = second.get("net_incremental_value")
        parts = [f"第 1 名 {case_id(first)} 与第 2 名 {case_id(second)} 的排序依据如下。"]
        if isinstance(first_net, (int, float)) and isinstance(second_net, (int, float)):
            difference = first_net - second_net
            parts.append(
                f"第一名净增量价值为 {first_net:,.2f} {currency}，第二名为 {second_net:,.2f} {currency}；"
                f"第一名高出 {difference:,.2f} {currency}。"
            )
        first_oil, second_oil = first.get("incremental_oil_m3"), second.get("incremental_oil_m3")
        first_cost, second_cost = first.get("polymer_cost"), second.get("polymer_cost")
        if all(isinstance(value, (int, float)) for value in (first_oil, second_oil, first_cost, second_cost)):
            parts.append(
                f"第二名增量油更高（{second_oil:,.2f} 对 {first_oil:,.2f} m3），但聚合物成本也更高"
                f"（{second_cost:,.2f} 对 {first_cost:,.2f} {currency}），新增产量未抵消新增成本。"
            )
        if first.get("technically_feasible") == second.get("technically_feasible"):
            status = "均通过" if first.get("technically_feasible") else "均未通过"
            parts.append(f"两者技术可行性状态相同（{status}当前配置约束），因此这一项没有拉开排序。")
        policy = (context.get("ranking_metadata") or {}).get("ranking_policy")
        if policy:
            parts.append(f"当前排序政策是“{policy}”，所以第一名是在当前评价口径下经济损失较小，并非所有指标都更高。")
        else:
            parts.append("因此第一名是在当前排名口径下经济表现更好，并非所有工程指标都优于第二名。")
        return "".join(parts)

    @staticmethod
    def _row_case_id(row: dict[str, Any]) -> str:
        """从不同领域的排名行中读取稳定方案标识。"""
        return str(row.get("case_id") or row.get("polymer_case_id") or row.get("scenario_id") or "未知方案")

    @classmethod
    def _scenario_choices(cls, context: dict[str, Any]) -> list[dict[str, str]]:
        """把当前实验全部排名行转换成聊天区可点击的安全选项。"""
        rankings = sorted(
            context.get("rankings") or [],
            key=lambda item: item.get("scenario_rank") if item.get("scenario_rank") is not None else float("inf"),
        )
        choices = []
        for row in rankings:
            case_id = cls._row_case_id(row)
            label = f"#{row.get('scenario_rank')} · {case_id}"
            # 当前领域存在参数字段时补充人类可读摘要；新领域缺少这些字段时仍可使用通用方案 ID。
            if row.get("polymer_concentration_kg_m3") is not None and row.get("injection_rate_m3_day") is not None:
                label = (
                    f"#{row.get('scenario_rank')} · 浓度 {row['polymer_concentration_kg_m3']:g} kg/m3"
                    f" · 注入 {row['injection_rate_m3_day']:g} m3/day"
                )
            choices.append({
                "id": case_id,
                "label": label,
                "question": f"解释候选方案 {case_id} 的推荐原因",
            })
        return choices

    @classmethod
    def _scenario_reason_answer(cls, context: dict[str, Any], target_case_id: str) -> str:
        """依据排名宽表解释任意候选方案，不把“排序候选”误写成“已批准推荐”。"""
        row = next(
            (item for item in context.get("rankings") or [] if cls._row_case_id(item) == target_case_id),
            None,
        )
        if row is None:
            return f"当前实验排名表中不存在方案 {target_case_id}。"
        rank = row.get("scenario_rank")
        decision = row.get("recommendation") or "暂无推荐结论"
        technical = "通过当前配置约束" if row.get("technically_feasible") else "未通过当前配置约束"
        economic = "经济为正" if row.get("economically_positive") else "经济未通过"
        currency = row.get("currency") or ""
        parts = [f"方案 {target_case_id} 排名第 {rank}，结论为“{decision}”：{technical}，{economic}。"]
        if row.get("net_incremental_value") is not None:
            parts.append(f"净增量价值为 {row['net_incremental_value']:,.2f} {currency}。")
        if row.get("incremental_oil_m3") is not None:
            parts.append(f"相对水驱增量油为 {row['incremental_oil_m3']:,.2f} m3。")
        if row.get("polymer_cost") is not None:
            parts.append(f"聚合物成本为 {row['polymer_cost']:,.2f} {currency}。")
        if row.get("polymer_concentration_kg_m3") is not None and row.get("injection_rate_m3_day") is not None:
            parts.append(
                f"对应参数为聚合物浓度 {row['polymer_concentration_kg_m3']:g} kg/m3、"
                f"注入速率 {row['injection_rate_m3_day']:g} m3/day。"
            )
        if not row.get("economically_positive"):
            parts.append("因此它只是当前排序政策下的相对候选，不代表已经通过经济评价或现场审批。")
        return "".join(parts)

    @staticmethod
    def _failed_rules_answer(context: dict[str, Any]) -> str:
        """直接汇总当前方案失败规则及证据值。"""
        failed = [item for item in context.get("rules") or [] if not item.get("passed")]
        if not failed:
            return "当前方案没有未通过规则；页面已切换到规则与证据区域，可检查全部通过项及来源。"
        details = []
        for item in failed:
            unit = item.get("unit") or ""
            details.append(
                f"{item.get('rule_id')}：{item.get('message')}，实际值 {item.get('actual')} {unit}，"
                f"阈值 {item.get('expected')} {unit}"
            )
        return f"当前方案共有 {len(failed)} 条未通过规则：" + "；".join(details) + "。页面已聚焦规则和证据链。"

    @staticmethod
    def _key_metrics_answer(context: dict[str, Any]) -> str:
        """列出当前方案最关键的可审计指标，并提示图谱已同步展示。"""
        scenario = context.get("scenario") or {}
        fields = (
            ("scenario_rank", "方案排名", ""),
            ("incremental_oil_m3", "增量油", "m3"),
            ("net_incremental_value", "净增量价值", scenario.get("currency") or ""),
            ("polymer_cost", "聚合物成本", scenario.get("currency") or ""),
            ("polymer_concentration_kg_m3", "聚合物浓度", "kg/m3"),
            ("injection_rate_m3_day", "注入速率", "m3/day"),
        )
        values = [
            f"{label} {scenario[key]:,.2f} {unit}".strip()
            for key, label, unit in fields if isinstance(scenario.get(key), (int, float))
        ]
        return "当前方案关键指标为：" + "；".join(values) + "。页面已同步展示指标卡、相关规则和方案解释图谱。"

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
        requested_case_id = next(
            (self._row_case_id(row) for row in context.get("rankings") or [] if self._row_case_id(row) in question),
            None,
        )
        if requested_case_id and any(word in question for word in ("解释", "原因", "推荐")):
            return {
                "answer": self._scenario_reason_answer(context, requested_case_id),
                "display": {"sections": ["overview", "metrics", "rules", "ranking"], "selected_case_id": case_id},
                "sources": [{"type": "experiment_rankings", "id": experiment_id}],
                "model": {"provider": self.provider.name, "bypassed": True},
                "guardrails": {"read_only": True, "deterministic_values_preserved": True},
            }
        if "为什么推荐当前方案" in question:
            choices = self._scenario_choices(context)
            return {
                "answer": (
                    f"当前实验共有 {len(choices)} 个可选方案。请选择下面任意方案，我会说明它的排名、"
                    "技术与经济状态以及推荐或不推荐原因。这里的“推荐”表示相对排序候选，不等同于现场批准。"
                ),
                "choices": choices,
                "display": {"sections": ["overview", "ranking"], "selected_case_id": case_id},
                "sources": [{"type": "experiment_rankings", "id": experiment_id}],
                "model": {"provider": self.provider.name, "bypassed": True},
                "guardrails": {"read_only": True, "deterministic_values_preserved": True},
            }
        if "只看未通过规则和证据" in question:
            return {
                "answer": self._failed_rules_answer(context),
                "display": {"sections": ["overview", "rules", "evidence", "graph"], "selected_case_id": case_id},
                "sources": [{"type": "scenario_context", "id": case_id}],
                "model": {"provider": self.provider.name, "bypassed": True},
                "guardrails": {"read_only": True, "deterministic_values_preserved": True},
            }
        if "展示关键指标和图谱" in question:
            return {
                "answer": self._key_metrics_answer(context),
                "display": {"sections": ["overview", "metrics", "rules", "graph"], "selected_case_id": case_id},
                "sources": [{"type": "scenario_context", "id": case_id}],
                "model": {"provider": self.provider.name, "bypassed": True},
                "guardrails": {"read_only": True, "deterministic_values_preserved": True},
            }
        ranking_intent = any(
            word in retrieval_query
            for word in ("排名", "最优", "全部方案", "方案对比", "第一名", "第二名", "优于")
        )
        if ranking_intent:
            # 只有排名问题才附带全实验排名，避免普通单方案问答上下文膨胀。
            compact["experiment_rankings"] = context.get("rankings") or []
        ranking_display = ranking_intent and any(
            word in question for word in ("查看", "展示", "打开", "列出", "全部")
        )
        ranking_comparison = ranking_intent and any(
            word in question for word in ("优于", "第一名", "第二名", "前两名", "差异")
        )
        if ranking_display or ranking_comparison:
            return {
                "answer": (
                    self._ranking_comparison_answer(context)
                    if ranking_comparison
                    else self._ranking_display_answer(context, case_id)
                ),
                "display": {"sections": suggested_sections, "selected_case_id": case_id},
                "sources": [
                    {"type": "experiment_rankings", "id": experiment_id},
                    {"type": "scenario_context", "id": case_id},
                ],
                "model": {"provider": self.provider.name, "bypassed": True},
                "guardrails": {"read_only": True, "deterministic_values_preserved": True},
            }
        system = (
            "你是 PetroAgent 的石油工程分析助手。回答当前问题，不要机械复述完整方案摘要。"
            "优先给出直接结论，再引用最相关的实际值、阈值和规则解释原因；只讨论与问题相关的事实。"
            "回答排名原因时必须比较 experiment_rankings 中至少两个方案，不得只复述当前方案结论。"
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
