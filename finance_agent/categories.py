CATEGORY_DESCRIPTIONS = {
    "Income": "Earnings and interest received; excludes refunds and transfers.",
    "Food": "Groceries, restaurants, coffee, and food delivery.",
    "Transportation": "Fuel, public transit, taxis, and rideshares; excludes insurance.",
    "Shopping": "General retail and online purchases; use a more specific category when clear.",
    "Entertainment": "Streaming, media, games, and leisure subscriptions.",
    "Health": "Medical care, pharmacies, fitness, and gym memberships.",
    "Rent": "Rent payments, including payments to a landlord regardless of payment method.",
    "Housing": "Home repairs, improvements, and home supplies; excludes rent and utilities.",
    "Insurance": "Insurance premiums, including car, health, and home insurance.",
    "Utilities": "Electricity, gas service, water, internet, phone, and cable bills.",
    "Transfers": "Account transfers, cash withdrawals, and person-to-person payments with no stated purchase purpose. Payments to a landlord belong in Rent, even when sent through Zelle or Venmo.",
    "Refunds": "Money returned for a previous purchase; separate from earnings.",
    "Other": "Fees, pending authorizations, and transactions with insufficient context.",
}

VALID_CATEGORIES = set(CATEGORY_DESCRIPTIONS)

# Consolidate old labels while preserving the source label in each raw CSV row.
CATEGORY_ALIASES = {
    "healthcare": "Health",
    "home": "Housing",
    "cash": "Transfers",
    "fees": "Other",
}


def normalize_category(value: str | None) -> str:
    if not value:
        return ""
    cleaned = value.strip()
    if cleaned.lower() in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[cleaned.lower()]
    for category in VALID_CATEGORIES:
        if cleaned.lower() == category.lower():
            return category
    return ""
