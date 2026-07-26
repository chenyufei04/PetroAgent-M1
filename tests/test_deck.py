from petro_agent.adapters.eclipse_deck import inspect_deck


def test_inspects_include_tree(tmp_path):
    child = tmp_path / "grid.inc"
    child.write_text("PORO\n  0.2 /\n", encoding="utf-8")
    root = tmp_path / "CASE.DATA"
    root.write_text("RUNSPEC\nINCLUDE 'grid.inc'\n/\n", encoding="utf-8")
    result = inspect_deck(root)
    assert not result.missing_includes
    assert "RUNSPEC" in result.keywords
    assert "PORO" in result.keywords
    assert len(result.files) == 2

