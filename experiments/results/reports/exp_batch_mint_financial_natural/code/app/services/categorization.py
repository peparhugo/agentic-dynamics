import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category


DEFAULT_CATEGORIES = [
    ("Income", None, "💰", "#4CAF50"),
    ("Salary", "Income", "💼", "#66BB6A"),
    ("Freelance", "Income", "💻", "#81C784"),
    ("Investments", "Income", "📈", "#A5D6A7"),
    ("Housing", None, "🏠", "#FF9800"),
    ("Rent", "Housing", "🏢", "#FFA726"),
    ("Mortgage", "Housing", "🔑", "#FFB74D"),
    ("Utilities", "Housing", "💡", "#FFCC80"),
    ("Transportation", None, "🚗", "#2196F3"),
    ("Gas", "Transportation", "⛽", "#42A5F5"),
    ("Public Transit", "Transportation", "🚌", "#64B5F6"),
    ("Ride Share", "Transportation", "🚕", "#90CAF9"),
    ("Food & Dining", None, "🍔", "#E91E63"),
    ("Groceries", "Food & Dining", "🛒", "#EC407A"),
    ("Restaurants", "Food & Dining", "🍽️", "#F06292"),
    ("Coffee Shops", "Food & Dining", "☕", "#F48FB1"),
    ("Shopping", None, "🛍️", "#9C27B0"),
    ("Clothing", "Shopping", "👕", "#AB47BC"),
    ("Electronics", "Shopping", "📱", "#BA68C8"),
    ("Entertainment", None, "🎬", "#00BCD4"),
    ("Streaming", "Entertainment", "📺", "#26C6DA"),
    ("Movies", "Entertainment", "🎥", "#4DD0E1"),
    ("Health", None, "🏥", "#8BC34A"),
    ("Pharmacy", "Health", "💊", "#9CCC65"),
    ("Insurance", "Health", "🛡️", "#AED581"),
    ("Transfers", None, "🔄", "#607D8B"),
    ("Credit Card Payment", "Transfers", "💳", "#78909C"),
    ("Uncategorized", None, "❓", "#BDBDBD"),
]


RULE_PATTERNS: dict[str, list[re.Pattern]] = {
    "Salary": [re.compile(r"(salary|payroll|direct deposit)", re.I)],
    "Groceries": [re.compile(r"(grocery|supermarket|whole foods|trader joe|kroger|safeway|aldi)", re.I)],
    "Restaurants": [re.compile(r"(restaurant|diner|mcdonald|burger|pizza|sushi|taco)", re.I)],
    "Coffee Shops": [re.compile(r"(starbucks|coffee|cafe|dunkin|peet)", re.I)],
    "Gas": [re.compile(r"(gas|fuel|shell|exxon|chevron|bp|mobil|7-eleven)", re.I)],
    "Ride Share": [re.compile(r"(uber|lyft|ride)", re.I)],
    "Streaming": [re.compile(r"(netflix|spotify|hulu|disney\+|hbo|amazon prime)", re.I)],
    "Pharmacy": [re.compile(r"(pharmacy|cvs|walgreens|rite aid|prescription)", re.I)],
    "Rent": [re.compile(r"(rent|lease|apartment)", re.I)],
    "Utilities": [re.compile(r"(electric|water|gas bill|utility|internet|comcast|verizon)", re.I)],
    "Credit Card Payment": [re.compile(r"(payment.*credit|credit.*payment|card payment)", re.I)],
    "Electronics": [re.compile(r"(apple|best buy|amazon.*electronic|newegg)", re.I)],
    "Clothing": [re.compile(r"(nordstrom|macy|gap|zara|h&m|nike|adidas|clothing)", re.I)],
}


class CategorizationEngine:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _ensure_default_categories(self):
        for name, parent_name, icon, color in DEFAULT_CATEGORIES:
            existing = await self.db.execute(select(Category).where(Category.name == name))
            if existing.scalar_one_or_none() is None:
                cat = Category(name=name, icon=icon, color=color)
                self.db.add(cat)
                await self.db.flush()

        parent_cats_result = await self.db.execute(select(Category))
        all_cats = {c.name: c for c in parent_cats_result.scalars().all()}

        for name, parent_name, icon, color in DEFAULT_CATEGORIES:
            if parent_name and parent_name in all_cats:
                cat = all_cats[name]
                cat.parent_id = all_cats[parent_name].id

        await self.db.commit()

    async def get_all_categories(self) -> list[Category]:
        result = await self.db.execute(select(Category).order_by(Category.name))
        return result.scalars().all()

    async def categorize(self, description: str, merchant: str | None = None) -> list[dict]:
        search_text = f"{description or ''} {merchant or ''}"

        for category_name, patterns in RULE_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(search_text):
                    result = await self.db.execute(
                        select(Category).where(Category.name == category_name)
                    )
                    cat = result.scalar_one_or_none()
                    if cat:
                        return [{"category_id": cat.id, "category_name": cat.name, "confidence": 0.85}]

        result = await self.db.execute(
            select(Category).where(Category.name == "Uncategorized")
        )
        cat = result.scalar_one_or_none()
        if cat:
            return [{"category_id": cat.id, "category_name": cat.name, "confidence": 0.5}]

        return []

    async def assign_category(self, transaction_id: str, category_id: str):
        result = await self.db.execute(
            select(Category).where(Category.id == category_id)
        )
        if result.scalar_one_or_none() is None:
            raise ValueError("Category not found")
        return True
