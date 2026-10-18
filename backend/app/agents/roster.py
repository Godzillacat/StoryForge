"""默认智能体阵容（上位文档 §5.2 与附录 A）。

P1a 只预置跑得通故事内核的两个；其余任务类型先登记常量，
P1b/P1c 落地时往 DEFAULT_ROSTER 里追加即可，不改任何运行时代码。
"""

from __future__ import annotations

from app.world_types import CHARACTER_FIELDS, ENTRY_TYPES, HARDNESS_LEVELS

TASK_TYPES = [
    "idea_parse",
    "architecture",
    "worldbuilding",
    "chapter_plan",
    "scene_plan",
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
        "genre": {"type": "string", "title": "题材"},
        "sub_genre": {"type": "string", "title": "子类型"},
        "premise": {"type": "string", "title": "一句话前提"},
        "protagonist_desire": {"type": "string", "title": "主角欲望"},
        "conflict_source": {"type": "string", "title": "核心冲突源"},
        "emotional_core": {"type": "string", "title": "情感内核"},
        "tone": {"type": "string", "title": "调性"},
        "length_expectation": {"type": "string", "title": "篇幅预期"},
        "comparable_works": {"type": "array", "items": {"type": "string"}, "title": "可能参考坐标"},
        "open_questions": {"type": "array", "items": {"type": "string"}, "title": "它没把握的问题"},
    },
}

ARCHITECTURE_SCHEMA = {
    "type": "object",
    "required": ["options"],
    "properties": {
        "options": {
            "type": "array",
            "minItems": 2,
            "title": "候选方案",
            "items": {
                "type": "object",
                "required": ["tool", "reason", "fit_score", "risks"],
                "properties": {
                    "tool": {"type": "string", "title": "结构名"},
                    "reason": {"type": "string", "title": "适配理由"},
                    "fit_score": {"type": "number", "title": "适配度"},
                    "risks": {"type": "array", "items": {"type": "string"}, "title": "风险"},
                    "length_plan": {"type": "string", "title": "篇幅分配"},
                    "rhythm_shape": {"type": "string", "title": "节奏形态"},
                },
            },
        },
        "story_bible_v0": {
            "type": "object",
            "title": "故事圣经 v0",
            "properties": {
                "logline": {"type": "string", "title": "一句话故事"},
                "theme": {"type": "string", "title": "主题句"},
                "premise": {"type": "string", "title": "前提"},
                "acts": {
                    "type": "array",
                    "title": "幕骨架",
                    "items": {
                        "type": "object",
                        "required": ["name"],
                        "properties": {
                            "name": {"type": "string", "title": "幕名"},
                            "purpose": {"type": "string", "title": "这一幕要做什么"},
                            "target_word_ratio": {"type": "number", "title": "篇幅占比"},
                        },
                    },
                },
                "main_characters": {
                    "type": "array",
                    "title": "主要人物",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "title": "人物名"},
                            "role": {"type": "string", "title": "定位"},
                            "desire": {"type": "string", "title": "他/她想要什么"},
                        },
                    },
                },
                "ending_direction": {"type": "string", "title": "结局方向"},
            },
        },
    },
}

_TYPE_TITLE = "、".join(ENTRY_TYPES.values())
_HARDNESS_TITLE = "、".join(HARDNESS_LEVELS.values())

WORLDBUILDER_SCHEMA = {
    "type": "object",
    "required": ["entries"],
    "properties": {
        "entries": {
            "type": "array",
            "minItems": 3,
            "title": "设定候选",
            "items": {
                "type": "object",
                "required": ["type", "name", "summary"],
                "properties": {
                    # 刻意不用 enum：契约说明块不渲染 enum 值的中文名，
                    # 而提示词里又不许写英文键（有护栏拦），模型将无从知道
                    # 哪个键对应哪一类。改由服务层归一化两种写法（见 world_types.py）。
                    "type": {
                        "type": "string",
                        "title": f"类型（只能是：{_TYPE_TITLE}）",
                    },
                    "name": {"type": "string", "title": "标准写法"},
                    "aliases": {
                        "type": "array",
                        "items": {"type": "string"},
                        "title": "别名与称呼",
                    },
                    "summary": {"type": "string", "title": "一句话概述"},
                    "description": {"type": "string", "title": "详细说明"},
                    "hardness": {
                        "type": "string",
                        "title": f"规则硬度（只有规则体系才填，可为：{_HARDNESS_TITLE}）",
                    },
                    # 人物八项**从 world_types 的唯一真相生成**，不手抄 ——
                    # 中文标签也只写在那里。可选项：非人物候选不填。
                    **{
                        key: {"type": "string", "title": f"{label}（只有人物才填）"}
                        for key, (label, _multiline) in CHARACTER_FIELDS.items()
                    },
                },
            },
        },
        "open_questions": {
            "type": "array",
            "items": {"type": "string"},
            "title": "你拿不准、需要作者确认的问题",
        },
    },
}

WORLDBUILDER_PROMPT = """你是长篇小说世界观构建师，服务对象是作者。你的产出是待作者审阅的设定候选，不是既定事实。

【灵感解析卡】
{{ parsed_idea }}

【故事圣经】
{{ story_bible }}

【项目信息】
{{ project_core }}

要求：
1. 提出 3 到 8 条这个故事的设定候选，覆盖故事真正需要的类别：__TYPE_LIST__；
2. 每条候选的概述要说明它**为什么是这个故事需要的** —— 引用解析卡或故事圣经里的具体要素，不许泛泛而谈「丰富世界观」；
3. 规则体系类的候选必须标注硬度：硬规则是体系根基、不可违反，软规则需大体一致，氛围只为质感。其余类别的硬度留空；
4. 别名与称呼把所有叫法都列上（简称、旧称、别称、敌对方的贬称），后面查一致性靠它；
5. 你没把握的一律写进「你拿不准、需要作者确认的问题」，**不许编造设定填空**；
6. 不要替作者决定故事的走向，也不要在候选里写正文；
7. 只有当材料支持时才给人物候选，不要为了凑数编造人；给了人物，就要把__CHARACTER_FIELD_LIST__里适用于这个人物的项写满——不适用的可以省；人物的全部称呼方式写进别名那一项。"""

# 类型清单与人物字段清单都由词表派生，不在提示词里手抄第二份 —— 手抄的那份
# 会在改词表时静默过期，而护栏只查英文键、查不出中文值的漂移。
# 用 replace 而不是 f-string：提示词里有 {{ parsed_idea }} 这类模板变量，
# f-string 会把双花括号吃掉。
WORLDBUILDER_PROMPT = WORLDBUILDER_PROMPT.replace("__TYPE_LIST__", _TYPE_TITLE)
WORLDBUILDER_PROMPT = WORLDBUILDER_PROMPT.replace(
    "__CHARACTER_FIELD_LIST__",
    "、".join(label for label, _multiline in CHARACTER_FIELDS.values()),
)

IDEA_PARSER_PROMPT = """你是长篇小说灵感解析师，服务对象是作者。你的产出是结构化的解析卡，不是改写。

【作者原话】
{{ raw_idea }}

要求：
1. 逐项填写解析卡，字段的键名与含义见下方【输出契约】；
2. 主角欲望要写成「他/她想要什么」，不是「他/她是什么人」；
3. 核心冲突源要指出对撞的两股力量，而不是罗列敌人；
4. 可能参考坐标只写气质相近的作品，不写抄袭对象；
5. 你没把握的地方一律写进「它没把握的问题」这一项，向作者提问，不许编造设定填空；
6. 不要改写作者的原话，也不要在返回里复述它。"""

ARCHITECT_PROMPT = """你是长篇小说结构顾问，服务对象是作者。你的产出是候选方案加理由，不是最终决定。

【灵感解析卡】
{{ parsed_idea }}

【项目信息】
{{ project_core }}

【可用结构工具】
{{ tool_library }}

要求：
1. 给出 2–3 套适配结构，每套的适配理由必须引用解析卡中的具体要素，不许泛泛而谈「符合三幕剧」；
2. 每套写明适配度（0–1 的小数，不是百分数）、风险、篇幅分配与节奏形态；
3. 每套的适配理由末尾要写明这套结构的不适用情形；
4. 允许并鼓励杂交方案（如三幕骨架、第二幕内部走七点结构），杂交时在适配理由里说清是哪两层杂交；
5. 结局方向只作建议，不替作者决定；
6. 同时给出故事圣经 v0；
7. 信息不足时在适配理由里说明缺什么，不要编造设定。"""

CHAPTER_PLANNER_SCHEMA = {
    "type": "object",
    "required": ["volumes", "open_questions"],
    "properties": {
        "volumes": {
            "type": "array",
            "minItems": 1,
            "title": "卷",
            "items": {
                "type": "object",
                "required": ["name", "chapters"],
                "properties": {
                    "name": {"type": "string", "title": "卷名"},
                    "purpose": {"type": "string", "title": "本卷要做什么"},
                    "act_seq": {"type": "integer", "title": "对应第几幕（没有就省略）"},
                    "target_words": {"type": "integer", "title": "本卷目标字数"},
                    "summary": {"type": "string", "title": "本卷摘要"},
                    "chapters": {
                        "type": "array",
                        "minItems": 1,
                        "title": "章",
                        "items": {
                            "type": "object",
                            "required": ["title"],
                            "properties": {
                                "title": {"type": "string", "title": "章标题"},
                                "pov": {"type": "string", "title": "视角"},
                                "target_words": {"type": "integer", "title": "目标字数"},
                                "emotional_tone": {"type": "string", "title": "情绪基调"},
                                "lines": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "title": "推进的线",
                                },
                                "hook": {"type": "string", "title": "章末钩子"},
                                "summary": {"type": "string", "title": "本章摘要"},
                                "conflict_level": {"type": "integer", "title": "冲突强度（1–5）"},
                                "dialogue_ratio": {"type": "number", "title": "对话占比（0–1）"},
                                "hook_strength": {"type": "integer", "title": "钩子强度（1–5）"},
                            },
                        },
                    },
                },
            },
        },
        "open_questions": {
            "type": "array",
            "items": {"type": "string"},
            "title": "没把握的问题",
        },
    },
}

SCENE_PLANNER_SCHEMA = {
    "type": "object",
    "required": ["scenes", "open_questions"],
    "properties": {
        "scenes": {
            "type": "array",
            "minItems": 1,
            "title": "场景",
            "items": {
                "type": "object",
                "required": ["goal", "conflict", "turn"],
                "properties": {
                    "goal": {"type": "string", "title": "场景目标"},
                    "conflict": {"type": "string", "title": "冲突"},
                    "turn": {"type": "string", "title": "转折"},
                    "characters": {
                        "type": "array",
                        "items": {"type": "string"},
                        "title": "出场人物（用标准名）",
                    },
                    "location": {"type": "string", "title": "地点（用标准名）"},
                    "story_time": {"type": "string", "title": "故事内时间"},
                    "pov": {"type": "string", "title": "视角"},
                    "target_words_min": {"type": "integer", "title": "目标字数下限"},
                    "target_words_max": {"type": "integer", "title": "目标字数上限"},
                    "foreshadow_plants": {
                        "type": "array",
                        "items": {"type": "string"},
                        "title": "埋设的伏笔名",
                    },
                    "foreshadow_pays": {
                        "type": "array",
                        "items": {"type": "string"},
                        "title": "回收的伏笔名",
                    },
                },
            },
        },
        "open_questions": {
            "type": "array",
            "items": {"type": "string"},
            "title": "没把握的问题",
        },
    },
}

CHAPTER_PLANNER_PROMPT = """你是长篇小说章纲策划，服务对象是作者。你的产出是卷章纲候选，不是正文。

【项目核心】
{{ project_core }}

【故事圣经】
{{ story_bible }}

【幕骨架】
{{ architecture }}

【灵感解析卡】
{{ parsed_idea }}

【世界观】
{{ world_context }}

【可用结构工具】
{{ tool_library }}

要求：
1. 按幕骨架排卷；每卷要有本卷目标与卷末高潮，卷首承接上一卷；
2. 每卷排章；每章写视角、目标字数、情绪基调、推进的线、章末钩子、摘要，并估计冲突强度、对话占比、钩子强度；
3. 只用【世界观】里已有的人物、势力、地点、规则，不编造；没有合适素材时写进待确认问题；
4. 章数与字数符合项目目标；卷和章的目标字数要与项目目标量级一致；
5. 卷的幕序号只在能明确对应时填，不确定就省略并写进待确认问题；
6. 不写正文；没把握的写进待确认问题；返回符合输出契约的结构化结果。"""

SCENE_PLANNER_PROMPT = """你是长篇小说场景策划，服务对象是作者。你的产出是本章的场景卡候选，不是正文。

【项目核心】
{{ project_core }}

【故事圣经】
{{ story_bible }}

【幕骨架】
{{ architecture }}

【世界观】
{{ world_context }}

【故事内时间线】
{{ timeline }}

【本卷纲要】
{{ volume_outline }}

【本章章纲】
{{ chapter_outline }}

【可用结构工具】
{{ tool_library }}

要求：
1. 把本章拆成 3–6 个场景；每场有具体目标、冲突与转折；转折要让处境更糟或更难；
2. 只用【世界观】里已有的人物与地点名称，不编造；人物只用人物条目，地点可用任意条目；没有合适地点就省略并写进待确认问题；
3. 每场写故事内时间、视角、目标字数区间；沿用本章视角，除非有明确理由；
4. 埋设与回收的伏笔用名称；回收的伏笔必须是前文已埋设或本章埋设的；不确定的写进待确认问题；
5. 不写正文；返回符合输出契约的结构化结果。"""

WRITER_PROMPT = """你是长篇小说执笔，服务对象是作者。你的任务是把当前场景卡写成可以直接进入小说正文的段落。

【项目信息】
{{ project_core }}

【故事圣经】
{{ story_bible }}

【世界观】
{{ world_context }}

【本卷纲要】
{{ volume_outline }}

【本章章纲】
{{ chapter_outline }}

【故事内时间线】
{{ timeline }}

【当前场景卡】
{{ scene_card }}

【出场人物】
{{ scene_characters }}

【相关设定】
{{ related_settings }}

【前情正文】
{{ recent_text }}

要求：
1. 只写这一场，不写章节标题、不写第几章、不写任何解释、提纲或创作说明；
2. 严格按场景卡的目标、冲突、转折、视角与目标字数写，写到转折落地就停；
3. 人物、地点与专有名词一律使用材料里的标准名或已有称呼，不新造名词；
4. 保持章纲与项目的调性，对白与叙述自然，不总结剧情、不评论人物；
5. 输出纯文本段落，段落之间空一行；不要用代码块包裹整篇正文；
6. 材料不足时按已有信息写，不要停下来提问；不确定的地方写得保守些。"""

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
    {
        "key": "worldbuilder",
        "name": "世界观构建师",
        "role_label": "设定",
        "color": "#14b8a6",
        "task_type": "worldbuilding",
        "system_prompt": WORLDBUILDER_PROMPT,
        "context_slots": ["parsed_idea", "story_bible", "project_core"],
        "output_schema": WORLDBUILDER_SCHEMA,
        "param_profile": "balanced",
        "trigger_mode": "assist",
        "note": "提设定候选，标注规则硬度，没把握就问，不编。",
    },
    {
        "key": "chapter_planner",
        "name": "章纲策划",
        "role_label": "章节",
        "color": "#8b5cf6",
        "task_type": "chapter_plan",
        "system_prompt": CHAPTER_PLANNER_PROMPT,
        "context_slots": [
            "project_core",
            "story_bible",
            "architecture",
            "parsed_idea",
            "world_context",
            "tool_library",
        ],
        "output_schema": CHAPTER_PLANNER_SCHEMA,
        "param_profile": "strict",
        "note": "排卷章纲、标节奏，没把握就问，不编。",
    },
    {
        "key": "scene_planner",
        "name": "场景策划",
        "role_label": "场景",
        "color": "#f59e0b",
        "task_type": "scene_plan",
        "system_prompt": SCENE_PLANNER_PROMPT,
        "context_slots": [
            "project_core",
            "story_bible",
            "architecture",
            "world_context",
            "timeline",
            "volume_outline",
            "chapter_outline",
            "tool_library",
        ],
        "output_schema": SCENE_PLANNER_SCHEMA,
        "param_profile": "balanced",
        "note": "把一章拆成场景卡，只用世界观里已有的人物与地点。",
    },
    {
        "key": "writer",
        "name": "执笔",
        "role_label": "正文",
        "color": "#ec4899",
        "task_type": "write",
        "system_prompt": WRITER_PROMPT,
        "context_slots": [
            "project_core",
            "story_bible",
            "world_context",
            "volume_outline",
            "chapter_outline",
            "timeline",
            "scene_card",
            "scene_characters",
            "related_settings",
            "recent_text",
        ],
        "output_schema": None,
        "param_profile": "balanced",
        "trigger_mode": "manual",
        "note": "按场景卡写正文；只出草稿，采纳才入稿。",
    },
]
