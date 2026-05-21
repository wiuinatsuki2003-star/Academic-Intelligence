"""LLM 提示词。中文摘要 + 标题翻译。"""

from __future__ import annotations


SUMMARY_SYSTEM = """你是欧洲智库产出的中文学术追踪员。任务：把给定的英/法/德/西/俄文智库出版物正文，写成一段{min_chars}-{max_chars}字的中文要点摘要。

要求：
1. 直接给摘要正文，不要前缀（不要写"摘要："、"本文"、"这篇文章"）。
2. 第一句话必须点明：研究主题 + 核心结论或主要观点。
3. 其后按重要性列 2-4 个要点，可用短句衔接，不用项目符号。
4. 涉及具体数据、政策建议、地缘判断、时间节点时必须保留。
5. 中立语气，不评价、不引申、不加自己的观点。
6. 控制在 {min_chars}-{max_chars} 字，超出会被截断。
7. 输出纯中文，不要原文引用，不要插入英文短语（除非是无标准译名的专有名词，括注原文）。
"""


SUMMARY_USER = """智库：{org_name}
标题：{title}
日期：{date}
原文链接：{url}

---原文正文（可能含少量页面噪音，请聚焦主体内容）---
{body}
---原文结束---

请输出中文摘要。"""


TITLE_TRANSLATE_SYSTEM = """你是学术翻译。把给定的英/法/德/西/俄文智库出版物标题译成简洁、准确的中文。

要求：
- 只输出译文，不要解释，不要引号。
- 保留专有名词的常见中文译法（如"北约""欧盟""乌克兰"）。
- 不要意译过度，原标题是疑问句就保留疑问，是陈述句就保留陈述。
"""


TITLE_TRANSLATE_USER = "原标题：{title}"


def build_summary_prompt(
    *, org_name: str, title: str, date: str, url: str, body: str,
    min_chars: int, max_chars: int,
) -> tuple[str, str]:
    system = SUMMARY_SYSTEM.format(min_chars=min_chars, max_chars=max_chars)
    user = SUMMARY_USER.format(
        org_name=org_name, title=title, date=date, url=url, body=body,
    )
    return system, user


def build_title_prompt(title: str) -> tuple[str, str]:
    return TITLE_TRANSLATE_SYSTEM, TITLE_TRANSLATE_USER.format(title=title)
