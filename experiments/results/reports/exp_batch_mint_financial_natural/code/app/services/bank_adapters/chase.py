from datetime import date, datetime, timedelta
from decimal import Decimal
import json
import random

from app.services.bank_adapters.base import BaseBankAdapter, BankTransaction, BankAccountInfo


class ChaseAdapter(BaseBankAdapter):
    INSTITUTION_ID = "chase"

    async def fetch_transactions(self, start_date: date, end_date: date) -> list[BankTransaction]:
        transactions = []
        current = start_date
        merchants = ["Amazon", "Walmart", "Starbucks", "Netflix", "Shell", "Uber", "Target", "Costco"]
        descriptions = ["Purchase", "Payment", "Transfer", "Withdrawal", "Deposit"]

        while current <= end_date:
            for _ in range(random.randint(0, 3)):
                amount = Decimal(str(round(random.uniform(-200, 500), 2)))
                transactions.append(BankTransaction(
                    external_id=f"chase_{current.isoformat()}_{random.randint(1000, 9999)}",
                    amount=amount,
                    description=f"{random.choice(descriptions)} {random.choice(merchants)}",
                    transaction_date=current,
                    merchant=random.choice(merchants),
                    post_date=current + timedelta(days=random.randint(0, 2)),
                    is_pending=random.random() < 0.1,
                    raw_data=json.dumps({"source": "chase_api_v3"}),
                ))
            current += timedelta(days=1)
        return transactions

    async def fetch_account_info(self) -> BankAccountInfo:
        return BankAccountInfo(
            current_balance=Decimal(str(round(random.uniform(500, 50000), 2))),
            available_balance=Decimal(str(round(random.uniform(500, 50000), 2))),
        )

    async def validate_connection(self) -> bool:
        return True
