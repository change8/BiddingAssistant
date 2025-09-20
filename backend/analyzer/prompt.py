from typing import List, Dict


SYSTEM_PROMPT_ZH = (
    "你是投标文件分析助手。请基于提供的招标文本，"
    "按照检查项类型（核心条款、疑问澄清、不利条款、拦标项、可能控标信号、关键词）"
    "识别证据片段并给出简明建议。回答使用中文，保留原文引用。"
)


def build_semantic_prompt(text: str, hints: List[str], rule: Dict) -> str:
    return f"""
{SYSTEM_PROMPT_ZH}

【当前规则】
- id: {rule.get('id')}
- 类型: {rule.get('category')}
- 描述: {rule.get('description')}
- 匹配线索: {hints}

【任务】
在以下招标文本中，找出与当前规则相关的段落或句子。对每处命中：
- 摘取原文片段（不超过300字）
- 简要说明为何命中（1句）
- 返回该片段在文档中的大致位置（若无法定位可省略）

【招标文本】
{text}

请以 JSON 数组返回，元素包含 fields: evidence, reason。
""".strip()

