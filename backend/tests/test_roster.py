from app.agents.roster import DEFAULT_ROSTER, TASK_TYPES


def test_task_types_cover_documented_roster():
    for task in (
        "idea_parse",
        "architecture",
        "worldbuilding",
        "chapter_plan",
        "write",
        "polish",
        "continuity",
        "logic_check",
        "reader",
        "assistant",
    ):
        assert task in TASK_TYPES


def test_roster_defines_the_two_p1a_agents():
    keys = {entry["key"] for entry in DEFAULT_ROSTER}
    assert {"idea_parser", "architect"} <= keys


def test_every_roster_entry_has_required_fields():
    for entry in DEFAULT_ROSTER:
        assert entry["key"] and entry["name"] and entry["task_type"]
        assert entry["system_prompt"].strip()
        assert isinstance(entry["context_slots"], list) and entry["context_slots"]
        assert entry["param_profile"] in {"strict", "balanced", "creative"}


def test_architect_prompt_forbids_deciding_for_the_author():
    architect = next(e for e in DEFAULT_ROSTER if e["key"] == "architect")
    prompt = architect["system_prompt"]
    assert "不替作者决定" in prompt or "只作建议" in prompt


def test_parser_prompt_requires_asking_instead_of_inventing():
    parser = next(e for e in DEFAULT_ROSTER if e["key"] == "idea_parser")
    assert "不许编" in parser["system_prompt"] or "编造" in parser["system_prompt"]


def test_parser_output_schema_lists_documented_fields():
    parser = next(e for e in DEFAULT_ROSTER if e["key"] == "idea_parser")
    props = parser["output_schema"]["properties"]
    for field in (
        "genre",
        "sub_genre",
        "premise",
        "protagonist_desire",
        "conflict_source",
        "emotional_core",
        "tone",
        "length_expectation",
        "comparable_works",
        "open_questions",
    ):
        assert field in props


def test_architect_output_schema_has_options_and_bible():
    architect = next(e for e in DEFAULT_ROSTER if e["key"] == "architect")
    props = architect["output_schema"]["properties"]
    assert "options" in props and "story_bible_v0" in props
