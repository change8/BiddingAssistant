from __future__ import annotations

from typing import Any, Dict, List

MAX_CHARS_PER_CHUNK = 6000

DOCUMENT_KEYWORDS = {
    "IT系统": ["软件", "系统", "开发", "运维", "信息化", "数据库", "平台", "接口"],
    "工程建设": ["施工", "建设", "工程", "土建", "装修", "改造", "安装", "土石方"],
    "服务采购": ["服务", "运营", "咨询", "物业", "保洁", "保安", "外包"],
}


def detect_document_type(text: str) -> str:
    lowered = text.lower()
    for doc_type, keywords in DOCUMENT_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in lowered:
                return doc_type
    return "通用"


def generate_dynamic_examples(text: str) -> str:
    doc_type = detect_document_type(text)
    examples_map = {
        "IT系统": """
### 示例：IT系统招标常见的隐性要求
- 看似简单的"7×24小时服务"可能意味着需要建立完整的运维团队
- "与现有系统无缝对接"可能隐含大量的接口开发工作
- "数据迁移"看似一句话，但可能涉及海量数据清洗
- 特别注意信创要求、等保要求等合规性要求
""",
        "工程建设": """
### 示例：工程类招标的特殊关注点
- 施工资质的细分等级
- 安全生产许可证的有效性
- 项目经理的在建工程限制
- 材料品牌的指定可能存在垄断
""",
        "服务采购": """
### 示例：服务类采购的易忽视点
- 服务人员的社保要求
- 服务场地的提供方
- 知识产权归属
- 服务成果的验收标准
""",
    }
    return examples_map.get(doc_type, "")


def _chunk_text(text: str, max_chars: int = MAX_CHARS_PER_CHUNK) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    total = len(text)
    cursor = 0
    index = 1
    while cursor < total:
        end = min(total, cursor + max_chars)
        if end < total:
            # try to break on newline to keep语义完整
            newline = text.rfind("\n", cursor, end)
            if newline > cursor + max_chars // 2:
                end = newline
        segment = text[cursor:end]
        chunks.append({"index": index, "start": cursor, "end": end, "content": segment})
        cursor = end
        index += 1
    return chunks


def build_adaptive_prompt(text: str, max_chars: int = MAX_CHARS_PER_CHUNK) -> Dict[str, Any]:
    system_prompt = (
        "你是一位经验丰富的招标文件分析专家。\n"
        "你的任务是全面识别招标文件中所有可能影响投标成功的关键信息。\n"
        "请保持开放和批判性思维，不要被任何预设框架限制，重要的是发现文件中的所有关键点。"
    )

    open_analysis_instruction = """
## 核心任务
请全面分析这份招标文件，识别所有可能影响投标的重要信息。

## 分析原则
1. **全面性优先**：宁可多发现，不可遗漏
2. **原文依据**：每个发现必须有原文支撑
3. **实用导向**：关注对投标实际操作的影响

## 分析方法

### 第一步：自由探索
先通读全文，不受任何框架限制，标记出所有你认为重要的内容，包括但不限于：
- 任何强制性要求（"必须"、"应当"、"不得"等）
- 任何可能导致失败的条件
- 任何涉及成本的内容
- 任何时间限制
- 任何特殊或异常的要求
- 任何含糊不清需要澄清的地方
- 任何可能的陷阱或风险

### 第二步：分类整理
将发现的内容按照其性质和影响自然分组，可能的分类方向包括（但不限于）：

#### 资格与合规类
- 硬性资质要求（会导致废标的）
- 软性资质要求（影响评分的）
- 人员要求
- 业绩要求
- 财务要求
- 其他你发现的资格要求...

#### 技术与方案类
- 技术指标要求
- 方案完整性要求
- 实施方法要求
- 其他技术相关要求...

#### 商务与成本类
- 报价要求
- 付款条件
- 成本相关的技术要求
- 隐性成本（如驻场、差旅等）
- 其他影响成本的因素...

#### 时间与流程类
- 投标流程时间点
- 项目实施时间要求
- 维保服务期限
- 其他时间约束...

#### 风险与注意事项
- 合同条款风险
- 技术实施风险
- 商务风险
- 法律合规风险
- **以及任何你识别到的其他风险类型**

### 第三步：补充发现
完成基础分析后，请特别思考：
1. 有没有任何异常或不寻常的要求？
2. 有没有相互矛盾的条款？
3. 有没有表述模糊可能有歧义的地方？
4. 有没有看似简单但实际很难满足的要求？
5. 从竞争角度，哪些要求可能是为特定供应商定制的？
"""

    two_stage_prompt = """
## 分析策略

### 第一遍：发散性扫描
像一个经验丰富的投标经理初次阅读标书一样，标记所有引起你注意的内容。
不要担心分类，只要觉得重要就记录下来。

### 第二遍：系统性整理
将第一遍发现的内容进行整理归类，但记住：
- 如果某些内容不适合现有分类，创建新分类
- 如果某些内容跨越多个分类，在多处提及
- 如果不确定如何分类，放在 "unusual_findings" 中

这样可以确保不会因为框架限制而遗漏重要信息。
"""

    dynamic_examples = generate_dynamic_examples(text)

    chunk_messages: List[Dict[str, str]] = []
    for chunk in _chunk_text(text, max_chars=max_chars):
        content = (
            f"### 文档片段 {chunk['index']}（字符 {chunk['start']} - {chunk['end']}）\n"
            f"请阅读并记住该片段内容，后续回答需要引用对应的字符位置。\n"
            f"{chunk['content']}"
        )
        chunk_messages.append({"role": "user", "content": content})

    schema_instruction = """
## 输出结构要求
请输出能被严格解析的 JSON（不得包含注释、Markdown、额外说明），结构如下：
{
  "summary": "面向投标团队的总览提醒（不超过180字）",
  "tabs": [
    {
      "id": "hard_requirements",
      "title": "废标项/硬性要求",
      "items": [
        {
          "title": "要点标题",
          "why_important": "重点提示，帮助读者理解这条为何关键（不超过120字）",
          "guidance": "建议采取的行动或思考方向（不超过100字）",
          "priority": "critical|high|medium|low",
          "source_excerpt": "原文摘录（<=200字，保持原语序）",
          "source_start": 整数（对应原文字符起始位置）
          "source_end": 整数（对应原文字符结束位置，开区间）
        }
      ]
    },
    {
      "id": "scoring_items",
      "title": "评分项",
      "items": [ { 同上字段要求 } ]
    },
    {
      "id": "submission_format",
      "title": "投标形式",
      "items": [ { 同上字段要求，可聚焦报名、递交方式、份数、盖章等 } ]
    },
    {
      "id": "technical_requirements",
      "title": "技术要求",
      "items": [ { 同上字段要求 } ]
    },
    {
      "id": "cost_items",
      "title": "成本项",
      "items": [ { 同上字段要求，可突出付款条件、押金、质保、隐性成本 } ]
    },
    {
      "id": "bid_timeline",
      "title": "投标日历",
      "items": [
        {
          "title": "关键节点",
          "milestone": "事件描述",
          "date": "日期或截止时间",
          "guidance": "提醒或行动建议",
          "source_excerpt": "原文摘录（<=200字）",
          "source_start": 整数,
          "source_end": 整数
        }
      ]
    }
  ]
}

补充要求：
- 六个 tab 必须全部输出，若无相关内容，items 为 []。
- 每个 tab 建议筛选 3-6 条高价值要点（投标日历可多于 6 条）。
- "source_start" 与 "source_end" 必须依据上方片段提供的字符索引，确保可定位原文。
- "source_excerpt" 需与对应区段一致，以便核对。
- 若原文存在时间或数字，保留原格式；不要臆造信息。
- 输出仅包含 JSON 字面量，不得加入 Markdown、注释或额外文字。
"""

    final_instruction = """
基于全部片段，完成结构化输出，特别注意显性废标项、硬性要求以及影响评标和交付的关键信息。若发现相互矛盾、待澄清、潜在风险的条款，请在相应 tab 的 items 中给出明确提示并提供行动建议。
"""

    prelude_message = {
        "role": "user",
        "content": f"""
{open_analysis_instruction}

{two_stage_prompt}

{dynamic_examples}

请通读全部片段，严格按照下述 JSON 结构返回结果。不要提前输出。\n\n{schema_instruction}
""".strip(),
    }

    analysis_request = {"role": "user", "content": final_instruction.strip()}

    messages = [prelude_message]
    messages.extend(chunk_messages)
    messages.append(analysis_request)

    return {"system": system_prompt, "messages": messages, "raw_text": text}
