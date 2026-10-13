"""默认智能体阵容（上位文档 §5.2 与附录 A）。

P1a 只预置跑得通故事内核的两个；其余任务类型先登记常量，
P1b/P1c 落地时往 DEFAULT_ROSTER 里追加即可，不改任何运行时代码。
"""

from __future__ import annotations

TASK_TYPES = [
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
]

IDEA_PARSE_SCHEMA = {
    "type": "object",
    "required": ["genre", "premise", "protagonist_desire", "conflict_source", "open_questions"],
    "properties": {
        "genre": {"type": "string"},
        "sub_genre": {"type": "string"},
        "premise": {"type": "string"},
        "protagonist_desire": {"type": "string"},
        "conflict_source": {"type": "string"},
        "emotional_core": {"type": "string"},
        "tone": {"type": "string"},
        "length_expectation": {"type": "string"},
        "comparable_works": {"type": "array", "items": {"type": "string"}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
    },
}

ARCHITECTURE_SCHEMA = {
    "type": "object",
    "required": ["options"],
    "properties": {
        "options": {
            "type": "array",
            "minItems": 2,
            "items": {
                "type": "object",
                "required": ["tool", "reason", "fit_score", "risks"],
                "properties": {
                    "tool": {"type": "string"},
                    "reason": {"type": "string"},
                    "fit_score": {"type": "number"},
                    "risks": {"type": "array", "items": {"type": "string"}},
                    "length_plan": {"type": "string"},
                    "rhythm_shape": {"type": "string"},
                },
            },
        },
        "story_bible_v0": {
            "type": "object",
            "properties": {
                "logline": {"type": "string"},
                "theme": {"type": "string"},
                "premise": {"type": "string"},
                "acts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["name"],
                        "properties": {
                            "name": {"type": "string"},
                            "purpose": {"type": "string"},
                            "target_word_ratio": {"type": "number"},
                        },
                    },
                },
                "main_characters": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "role": {"type": "string"},
                            "desire": {"type": "string"},
                        },
                    },
                },
                "ending_direction": {"type": "string"},
            },
        },
    },
}

IDEA_PARSER_PROMPT = """你是长篇小说灵感解析师，服务对象是作者。你的产出是结构化的解析卡，不是改写。

【作者原话】
{{ raw_idea }}

要求：
1. 逐项填写解析卡：题材、子类型、一句话前提、主角欲望、核心冲突源、情感内核、调性、篇幅预期、可能参考坐标；
2. 主角欲望要写成「他/她想要什么」，不是「他/她是什么人」；
3. 核心冲突源要指出对撞的两股力量，而不是罗列敌人；
4. 可能参考坐标只写气质相近的作品，不写抄袭对象；
5. 你没把握的地方一律写进 open_questions 向作者提问，不许编造设定填空；
6. 不要改写作者的原话，也不要在返回里复述它。

输出：符合解析卡 schema 的 JSON。"""

ARCHITECT_PROMPT = """你是长篇小说结构顾问，服务对象是作者。你的产出是候选方案加理由，不是最终决定。

【灵感解析卡】
{{ parsed_idea }}

【项目信息】
{{ project_core }}

【可用结构工具】
{{ tool_library }}

要求：
1. 给出 2–3 套适配结构，每套必须引用解析卡中的具体要素说明适配理由，不许泛泛而谈「符合三幕剧」；
2. 每套写明适配度（0–1 的小数）、风险、篇幅分配与节奏形态；
3. 明确写出每套结构的不适用情形；
4. 允许并鼓励杂交方案（如三幕骨架、第二幕内部走七点结构），杂交时要说清是哪两层杂交；
5. 结局方向只作建议，不替作者决定；
6. 同时给出故事圣经 v0：logline、主题句、前提、幕骨架、主要人物、结局方向；
7. 信息不足时在 reason 里说明缺什么，不要编造设定。

输出：符合架构推荐 schema 的 JSON。"""

DEFAULT_ROSTER: list[dict] = [
    {
        "key": "idea_parser",
        "name": "灵感解析师",
        "role_label": "解析",
        "color": "#6366f1",
        "task_type": "idea_parse",
        "system_prompt": IDEA_PARSER_PROMPT,
        "context_slots": ["raw_idea"],
        "output_schema": IDEA_PARSE_SCHEMA,
        "param_profile": "strict",
        "note": "灵感变结构化解析卡，没把握就问，不编。",
    },
    {
        "key": "architect",
        "name": "架构师",
        "role_label": "架构",
        "color": "#0ea5e9",
        "task_type": "architecture",
        "system_prompt": ARCHITECT_PROMPT,
        "context_slots": ["parsed_idea", "project_core", "tool_library"],
        "output_schema": ARCHITECTURE_SCHEMA,
        "param_profile": "strict",
        "note": "推荐结构并并排比较，生成故事圣经 v0。",
    },
]
