"""验证大模型只读编排不会篡改确定性工程事实。"""

from petro_agent.agents import AnalysisAssistant
from petro_agent.llm.provider import MockProvider


def _context(_experiment_id: str, case_id: str) -> dict:
    return {
        "case_id": case_id,
        "scenario": {"scenario_rank": 1, "net_incremental_value": -100.0, "currency": "USD"},
        "parameters": [{"concept_id": "injection_rate", "source_field": "injection_rate", "value": 100}],
        "metrics": [
            {"concept_id": "net_incremental_value", "source_field": "net_incremental_value", "value": -100},
            {"concept_id": "injector_bhp", "source_field": "pressure_bar", "value": 290},
        ],
        "rules": [
            {"rule_id": "PF-ECO-1", "passed": False, "message": "净值必须为正", "actual": -100, "expected": 0, "unit": "USD"},
            {"rule_id": "PF-OPS-1", "passed": True, "message": "压力不超过上限", "actual": 290, "expected": 380, "unit": "bar"},
        ],
        "recommendation": {"decision": "经济未通过"},
        "evidence": {"source_id": "model-v1", "assumption_status": "illustrative_unvalidated"},
    }


def test_mock_assistant_returns_grounded_answer_and_display_directive() -> None:
    assistant = AnalysisAssistant(MockProvider(), _context)

    payload = assistant.chat("experiment-1", "case-1", "为什么未通过？展示规则和证据")

    assert "-100.00 USD" in payload["answer"]
    assert "PF-ECO-1" in payload["answer"]
    assert {"rules", "evidence"}.issubset(payload["display"]["sections"])
    assert payload["display"]["selected_case_id"] == "case-1"
    assert payload["guardrails"]["read_only"] is True


def test_assistant_rejects_unknown_model_sections() -> None:
    class UnsafeProvider:
        name = "test"

        def generate_json(self, _messages):
            return {"answer": "ok", "sections": ["rules", "arbitrary_html", "run_flow"]}

    payload = AnalysisAssistant(UnsafeProvider(), _context).chat("experiment-1", "case-1", "规则")

    assert payload["display"]["sections"] == ["overview", "rules"]


def test_assistant_passes_history_and_focuses_pressure_facts() -> None:
    class RecordingProvider:
        name = "test"

        def __init__(self):
            self.messages = []

        def generate_json(self, messages):
            self.messages = messages
            return {"answer": "注入井压力为 290 bar，当前规则通过。"}

    model = RecordingProvider()
    assistant = AnalysisAssistant(model, _context)
    assistant.chat(
        "experiment-1", "case-1", "那压力呢？",
        history=[{"role": "user", "content": "为什么经济失败？"}, {"role": "assistant", "content": "因为净值为负。"}],
    )

    # 显式切换到压力主题时不再携带上一轮经济消息，避免模型先复述旧答案。
    assert len(model.messages) == 2
    facts = __import__("json").loads(model.messages[1]["content"])
    assert any(item["concept_id"] == "injector_bhp" for item in facts["relevant_observations"])
    assert any(item["rule_id"] == "PF-OPS-1" for item in facts["relevant_rules"])
    assert all("ECO" not in item["rule_id"] for item in facts["relevant_rules"])
    assert "draft_answer" not in facts


def test_assistant_retries_when_answer_repeats_previous_turn() -> None:
    repeated = "当前方案技术可行但经济未通过，因为净增量价值为负，建议继续检查经济参数和成本假设。" * 2

    class RewritingProvider:
        name = "ollama"

        def __init__(self):
            self.calls = 0

        def generate_json(self, _messages):
            self.calls += 1
            return {"answer": repeated if self.calls == 1 else "本轮只补充压力：注入井压力为 290 bar，当前规则通过。"}

    model = RewritingProvider()
    payload = AnalysisAssistant(model, _context).chat(
        "experiment-1", "case-1", "那压力呢？",
        history=[{"role": "assistant", "content": repeated}],
    )

    assert model.calls == 2
    assert payload["answer"].startswith("本轮只补充压力")


def test_assistant_falls_back_to_structured_evidence_after_bad_rewrite() -> None:
    class OverclaimingProvider:
        name = "ollama"

        def generate_json(self, _messages):
            return {"answer": "压力安全，技术上可行，但经济没有通过。"}

    result = AnalysisAssistant(OverclaimingProvider(), _context).chat(
        "experiment-1", "case-1", "压力是否通过？"
    )

    assert result["answer"] == "压力不超过上限：实际值为 290 bar，阈值为 380 bar，因此通过当前演示性配置规则。"
    assert "经济" not in result["answer"]
