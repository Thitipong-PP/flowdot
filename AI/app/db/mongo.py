from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings

class MongoDBManager:
    """Centralized MongoDB async connection pool manager."""
    def __init__(self, uri: str = settings.MONGO_URI, db_name: str = settings.MONGO_DB_NAME):
        self.uri = uri
        self.db_name = db_name
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        
        # Collection names
        self.receipts_col_name = "receipts"
        self.statements_col_name = "statements"
        self.loan_products_col_name = "loan_products"
        self.sessions_col_name = "sessions"

    def connect(self) -> AsyncIOMotorDatabase:
        if not self.client:
            self.client = AsyncIOMotorClient(self.uri, serverSelectionTimeoutMS=2000)
            self.db = self.client[self.db_name]
        return self.db

    def close(self):
        if self.client:
            self.client.close()
            self.client = None
            self.db = None

    @property
    def receipts(self):
        return self.connect()[self.receipts_col_name]

    @property
    def statements(self):
        return self.connect()[self.statements_col_name]

    @property
    def loan_products(self):
        return self.connect()[self.loan_products_col_name]

    @property
    def sessions(self):
        return self.connect()[self.sessions_col_name]

    async def init_indexes(self):
        """Initializes 24h TTL index and duplicate detection indexes."""
        if self.db is None:
            self.connect()
        try:
            # 1. 24h TTL Index: automatically purge unconfirmed receipts after 86400s (24h)
            await self.receipts.create_index(
                "created_at",
                expireAfterSeconds=86400,
                partialFilterExpression={"status": "PENDING_CONFIRMATION"}
            )
            # 2. Hard duplicate compound index on invoice (seller_tax_id + document_no)
            await self.receipts.create_index(
                [("seller_tax_id", 1), ("document_no", 1)],
                sparse=True
            )
            # 3. Hard duplicate index on slip reference_no
            await self.receipts.create_index(
                "reference_no",
                sparse=True
            )
            return {"status": "success", "message": "MongoDB indexes verified & created"}
        except Exception as e:
            print(f"Error in create_indexes: {e}")
            return {"status": "warning", "message": f"Index creation deferred: {e}"}

    async def check_health(self) -> Dict[str, Any]:
        """Pings MongoDB to verify connection status."""
        try:
            self.connect()
            await self.client.admin.command('ping')
            return {
                "connected": True,
                "db_name": self.db_name,
                "uri": self.uri,
                "message": "Connected to MongoDB successfully"
            }
        except Exception as e:
            print(f"Error in check_health: {e}")
            return {
                "connected": False,
                "db_name": self.db_name,
                "uri": self.uri,
                "message": f"MongoDB not reachable on localhost:27017: {e}"
            }

    async def seed_initial_data(self) -> Dict[str, Any]:
        """Seeds real sample documents into MongoDB collections so Compass displays them immediately."""
        self.connect()
        now = datetime.now(timezone.utc)

        # 1. Seed Loan Products
        try:
            from app.db.seed_loan_catalog import seed_loan_products
            await seed_loan_products()
        except Exception as e:
            print(f"Loan catalog seed note: {e}")

        # 2. Seed Sample Bank Statements (Somchai Supermart 30 days)
        await self.statements.delete_many({})
        sample_statement = {
            "business_id": "sme_user_001",
            "business_name": "Somchai Supermart Ltd.",
            "period": "2026-09-01 to 2026-09-30",
            "current_cash_reserve": 120000.0,
            "upcoming_debt_service": 70000.0,
            "daily_burn_rate": 3000.0,
            "net_monthly_operating_income": 60000.0,
            "monthly_gross_revenue": 200000.0,
            "transactions_count": 42,
            "updated_at": now
        }
        await self.statements.insert_one(sample_statement)

        # 3. Seed Sample User Session
        await self.sessions.delete_many({})
        sample_session = {
            "session_id": "sme_user_001",
            "user_id": "u_somchai_01",
            "active_intent": "CASHFLOW_HEALTH_CHECK",
            "current_cash": 120000.0,
            "upcoming_debt": 70000.0,
            "created_at": now
        }
        await self.sessions.insert_one(sample_session)

        # 4. Trigger Index Creation
        await self.init_indexes()

        loan_count = await self.loan_products.count_documents({})
        stmt_count = await self.statements.count_documents({})
        session_count = await self.sessions.count_documents({})

        return {
            "status": "success",
            "database": self.db_name,
            "counts": {
                "loan_products": loan_count,
                "statements": stmt_count,
                "sessions": session_count
            },
            "message": "Seeded MongoDB successfully! Refresh MongoDB Compass to see collections and documents."
        }

db_manager = MongoDBManager()
