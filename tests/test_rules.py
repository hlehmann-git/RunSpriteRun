from src.core.rules import default_label, valid_group_name, valid_label, valid_project_name


def test_names():
    assert valid_project_name("Demo_Hero-1")
    assert not valid_project_name("Demo Hero") and not valid_project_name("") and not valid_project_name("a" * 41)
    assert valid_group_name("a" * 20) and not valid_group_name("a" * 21)
    assert valid_label("walk_1") and not valid_label("walk 1")


def test_default_label():
    assert default_label("walk 1 (copy)", set()) == "walk_1__copy_"
    assert default_label("run", {"run"}) == "run001"
    assert default_label("run", {"run", "run001"}) == "run002"
    assert len(default_label("x" * 60, {"x" * 40})) == 40
