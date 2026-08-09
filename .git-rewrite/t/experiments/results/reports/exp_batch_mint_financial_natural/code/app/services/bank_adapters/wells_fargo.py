from datetime import date, datetime, timedelta
from decimal import Decimal
import json
import random

from app.services.bank_adapters.base import BaseBankAdapter, BankTransaction, BankAccountInfo


class WellsFargoAdapter(BaseBankAdapter):
    INSTITUTION_ID = "wells_fargo"

    async def fetch_transactions(self, start_date: date, end_date: date) -> list[BankTransaction]:
        transactions = []
        current = start_date
        merchants = ["Apple", "Best Buy", "Chipotle", "Delta", "Exxon", "Airbnb"]

        while current <= end_date:
            for _ in range(random.randint(0, 3)):
                amount = Decimal(str(round(random.uniform(-300, 800), 2)))
                transactions.append(BankTransaction(
                    external_id=f"wf_{current.isoformat()}_{random.randint(1000, 9999)}",
                    amount=amount,
                    description=f"WF {random.choice(merchants)} Transaction",
                    transaction_date=current,
                    merchant=random.choice(merchants),
                    post_date=current + timedelta(days=1),
                    is_pending=random.random() < 0.05,
                    raw_data=json.dumps({"source": "wf_api"}),
                ))
            current += timedelta(days=1)
        return transactions

    async def fetch_account_info(self) -> BankAccountInfo:
        return BankAccountInfo(
            current_balance=Decimal(str(round(random.uniform(200, 30000), 2))),
            available_balance=Decimal(str(round(random.uniform(200, 30000), 2))),
        )

    async def validate_connection(self) -> bool:
        return True
