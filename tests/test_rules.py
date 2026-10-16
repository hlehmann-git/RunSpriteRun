from src.core.rules import default_label, valid_group_name, valid_label, valid_project_name


def test_names():
    assert valid_project_name("Demo_Hero-1")
    assert not valid_project_name("Demo Hero") and not valid_project_name("") and not valid_project_name("a" * 41)
    assert valid_group_name("a" * 20) and not valid_group_name("a" * 21)
    assert valid_label("walk_1") and not valid_label("walk 1")


def test_default_label():
    assert default_label("walk 1 (copy)") == "walk_1__copy_"
    assert default_label("run") == "run" and default_label("") == "Frame"
    assert len(default_label("x" * 100)) == 60


def test_label_parts():
    from src.core.rules import make_label, name_of, old_label_name
    assert make_label("Idle", 4) == "Idle_004" and make_label("Idle_4", 5) == "Idle_4_005"
    assert name_of("Idle_4_005") == "Idle_4" and name_of("Idle_004") == "Idle" and name_of("Idle") == "Idle"
    assert old_label_name("Idle_4") == "Idle" and old_label_name("_3") == "Frame" and old_label_name("Run") == "Run"
    assert valid_label("a" * 64) and not valid_label("a" * 65)
