from datetime import date, datetime, timedelta
from decimal import Decimal
import json
import random

from app.services.bank_adapters.base import BaseBankAdapter, BankTransaction, BankAccountInfo


class BankOfAmericaAdapter(BaseBankAdapter):
    INSTITUTION_ID = "bank_of_america"

    async def fetch_transactions(self, start_date: date, end_date: date) -> list[BankTransaction]:
        transactions = []
        current = start_date
        merchants = ["Whole Foods", "Home Depot", "McDonald's", "Spotify", "CVS", "Lyft"]

        while current <= end_date:
            for _ in range(random.randint(0, 4)):
                amount = Decimal(str(round(random.uniform(-500, 1000), 2)))
                transactions.append(BankTransaction(
                    external_id=f"boa_{current.isoformat()}_{random.randint(1000, 9999)}",
                    amount=amount,
                    description=f"BOA TXN {random.choice(merchants)}",
                    transaction_date=current,
                    merchant=random.choice(merchants),
                    is_pending=random.random() < 0.15,
                    raw_data=json.dumps({"source": "boa_api_v2"}),
                ))
            current += timedelta(days=1)
        return transactions

    async def fetch_account_info(self) -> BankAccountInfo:
        balance = Decimal(str(round(random.uniform(1000, 100000), 2)))
        return BankAccountInfo(current_balance=balance, available_balance=balance)

    async def validate_connection(self) -> bool:
        return True
