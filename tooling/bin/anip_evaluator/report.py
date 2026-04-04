from __future__ import annotations


def to_markdown(evaluation_doc: dict[str, object]) -> str:
    ev = evaluation_doc["evaluation"]

    def bullets(items: list[str]) -> str:
        if not items:
            return "- none"
        return "\n".join(f"- {item}" for item in items)

    return f"""# Evaluation: {ev['scenario_name']}

Result: {ev['result']}

Handled by ANIP:
{bullets(ev['handled_by_anip'])}

Glue you will still write:
{bullets(ev['glue_you_will_still_write'])}

Glue category:
{bullets(ev['glue_category'])}

Why:
{bullets(ev['why'])}

What would improve the result:
{bullets(ev['what_would_improve'])}
"""
