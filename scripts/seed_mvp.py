
import asyncio
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models.client import Client
from app.models.rule import Rule
from app.models.user import User
from app.core.security import hash_password
from app.config import settings

# Use direct connection for seeding
DATABASE_URL = settings.database_url_direct

engine = create_async_engine(DATABASE_URL)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def seed():
    async with SessionLocal() as session:
        print("Seeding data...")
        
        # 1. Create SuperAdmin
        result = await session.execute(select(User).where(User.username == "admin"))
        if not result.scalar_one_or_none():
            admin = User(
                username="admin",
                email="admin@apeiron.com",
                hashed_password=hash_password("admin123"),
                role="super_admin",
                is_active=True
            )
            session.add(admin)
            print("Created SuperAdmin user.")
        
        # 2. Create Test Client
        result = await session.execute(select(Client).where(Client.code == "TEST01"))
        client = result.scalar_one_or_none()
        if not client:
            client = Client(
                name="Test Client Alpha",
                code="TEST01",
                config={"detect_duplicates": True}
            )
            session.add(client)
            await session.flush()
            print(f"Created Test Client: {client.id}")
        else:
            print(f"Test Client exists: {client.id}")

        # 3. Create Duplicate Rule (Single Field)
        rule_name = "Dup Invoice Check"
        result = await session.execute(select(Rule).where(Rule.name == rule_name))
        if not result.scalar_one_or_none():
            rule = Rule(
                client_id=client.id,
                rule_type="duplicate",
                name=rule_name,
                primary_field="invoice_number",
                severity="error",
                enabled=True,
                created_by="admin",
                approved_by="admin"
            )
            session.add(rule)
            print("Created Single Field Duplicate Rule.")

        # 4. Create Composite Key Rule
        composite_rule_name = "Dup Invoice+Carrier Check"
        result = await session.execute(select(Rule).where(Rule.name == composite_rule_name))
        if not result.scalar_one_or_none():
            rule = Rule(
                client_id=client.id,
                rule_type="duplicate",
                name=composite_rule_name,
                primary_field="invoice_number,carrier_code",
                severity="warning",
                enabled=True,
                created_by="admin",
                approved_by="admin"
            )
            session.add(rule)
            print("Created Composite Key Duplicate Rule.")

        await session.commit()
        print("Seeding complete.")

if __name__ == "__main__":
    asyncio.run(seed())
