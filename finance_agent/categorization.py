import json

from .categories import CATEGORY_DESCRIPTIONS, normalize_category
from .descriptions import clean_description
from .models import Transaction


def build_categorization_prompt(transactions: list[Transaction]) -> str:
    examples = {}
    for source in ("expenses.csv", "transactions_uncategorized.csv"):
        for tx in transactions:
            if tx.source_file != source:
                continue
            category = normalize_category(tx.raw.get("Category"))
            if category and category not in examples:
                examples[category] = clean_description(tx.description)

    definitions = "\n".join(
        f"- {category}: {description}"
        for category, description in CATEGORY_DESCRIPTIONS.items()
    )
    missing = [tx for tx in transactions if not tx.category]
    lines = "\n".join(
        f"[{index}] {clean_description(tx.description)} | amount={tx.amount}"
        for index, tx in enumerate(missing)
    )
    return (
        "CATEGORIZE_TRANSACTIONS\n"
        f"Valid categories and definitions:\n{definitions}\n"
        "Existing CSV-labeled examples (category to description):\n"
        f"{json.dumps(examples)}\n"
        "Use the definitions and examples to infer each transaction's purpose. "
        "Examples illustrate categories; they are not an exhaustive merchant list. "
        "Use Other when the description gives insufficient context.\n"
        f"Transactions to categorize:\n{lines}\n"
        'Return ONLY a JSON object mapping the numeric ids to category strings, '
        'for example: {"0": "Food", "1": "Housing"}. '
        "Do not include markdown, explanations, or a list of objects."
    )
