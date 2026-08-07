"""验证大模型只读编排不会篡改确定性工程事实。"""

from petro_agent.agents import AnalysisAssistant
from petro_agent.llm.provider import MockProvider


def _context(_experiment_id: str, case_id: str) -> dict:
    return {
        "case_id": case_id,
        "scenario": {"scenario_rank": 1, "net_incremental_value": -100.0, "currency": "USD"},
        "parameters": [],
        "metrics": [],
        "rules": [{"rule_id": "ECO-1", "passed": False, "message": "净值必须为正"}],
        "recommendation": {"decision": "经济未通过"},
        "evidence": {"source_id": "model-v1"},
    }


def test_mock_assistant_returns_grounded_answer_and_display_directive() -> None:
    assistant = AnalysisAssistant(MockProvider(), _context)

    payload = assistant.chat("experiment-1", "case-1", "为什么未通过？展示规则和证据")

    assert "-100.00 USD" in payload["answer"]
    assert "ECO-1" in payload["answer"]
    assert {"rules", "evidence"}.issubset(payload["display"]["sections"])
    assert payload["display"]["selected_case_id"] == "case-1"
    assert payload["guardrails"]["read_only"] is True


def test_assistant_rejects_unknown_model_sections() -> None:
    class UnsafeProvider:
        name = "test"

        def generate_json(self, _messages):
            return {"answer": "ok", "sections": ["rules", "arbitrary_html", "run_flow"]}

    payload = AnalysisAssistant(UnsafeProvider(), _context).chat("experiment-1", "case-1", "规则")

    assert payload["display"]["sections"] == ["rules"]
