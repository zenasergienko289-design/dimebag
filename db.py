# =====================================================
# ПОДКЛЮЧЕНИЕ К БАЗЕ
# =====================================================
from datetime import datetime, timedelta
from typing import Optional
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import (
    BigInteger, String, Float, Integer, DateTime, Text, select, func
)
from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from config import DB_URL


class Base(DeclarativeBase):
    pass


def money(value) -> float:
    """Безопасное округление денежных сумм до 2 знаков."""
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# =====================================================
# ТАБЛИЦЫ
# =====================================================

class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    lang: Mapped[str] = mapped_column(String(4), default="ru")
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    deals_count: Mapped[int] = mapped_column(Integer, default=0)
    referrals_count: Mapped[int] = mapped_column(Integer, default=0)
    referrer_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    registered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserDetails(Base):
    __tablename__ = "user_details"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ton: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    card: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    stars: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    usdt: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    btc: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Deal(Base):
    __tablename__ = "deals"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    creator_id: Mapped[int] = mapped_column(BigInteger, index=True)
    role: Mapped[str] = mapped_column(String(8))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    buyer_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    seller_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    buyer_username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    seller_username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="RUB")
    type: Mapped[str] = mapped_column(String(16))
    deal_code: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BalanceHistory(Base):
    __tablename__ = "balance_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    old_balance: Mapped[float] = mapped_column(Float)
    amount: Mapped[float] = mapped_column(Float)
    new_balance: Mapped[float] = mapped_column(Float)
    op_type: Mapped[str] = mapped_column(String(32))
    performed_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64))
    stars: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_demo: Mapped[int] = mapped_column(Integer, default=1)


class Admin(Base):
    __tablename__ = "admins"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


engine = create_async_engine(DB_URL, echo=False)
SessionMaker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_demo_reviews()


# =====================================================
# ПОЛЬЗОВАТЕЛИ
# =====================================================

async def ensure_user(
    user_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    referrer_id: Optional[int] = None,
) -> User:
    async with SessionMaker() as session:
        user = await session.get(User, user_id)

        if user is None:
            user = User(
                user_id=user_id,
                username=username,
                first_name=first_name,
                referrer_id=referrer_id,
            )
            session.add(user)

            # Бонус рефереру
            if referrer_id and referrer_id != user_id:
                ref = await session.get(User, referrer_id)
                if ref:
                    old = money(ref.balance)
                    ref.balance = money(old + 50.0)
                    ref.referrals_count += 1
                    session.add(Transaction(
                        user_id=referrer_id,
                        amount=50.0,
                        currency="RUB",
                        type="referral",
                        comment=f"Бонус за реферала {user_id}",
                    ))
                    session.add(BalanceHistory(
                        user_id=referrer_id,
                        old_balance=old,
                        amount=50.0,
                        new_balance=ref.balance,
                        op_type="referral",
                        performed_by=None,
                        comment=f"Бонус за реферала {user_id}",
                    ))

            # ⚠️ try/except чтобы не упасть, если бот и API создают юзера ОДНОВРЕМЕННО
            try:
                await session.commit()
                await session.refresh(user)
            except Exception as e:
                await session.rollback()
                user = await session.get(User, user_id)
                if user is None:
                    raise e
        else:
            if username and user.username != username:
                user.username = username
            if first_name and user.first_name != first_name:
                user.first_name = first_name
            try:
                await session.commit()
            except Exception:
                await session.rollback()

        return user


async def get_user(user_id: int) -> Optional[User]:
    async with SessionMaker() as session:
        return await session.get(User, user_id)


async def set_user_lang(user_id: int, lang: str) -> None:
    async with SessionMaker() as session:
        user = await session.get(User, user_id)
        if user:
            user.lang = lang
            await session.commit()


async def get_balance(user_id: int) -> float:
    async with SessionMaker() as session:
        user = await session.get(User, user_id)
        return money(user.balance) if user else 0.0


async def add_balance(
    user_id: int,
    amount: float,
    type_: str = "deposit",
    comment: Optional[str] = None,
    deal_code: Optional[str] = None,
    currency: str = "RUB",
    performed_by: Optional[int] = None,
) -> float:
    amount = money(amount)
    if amount == 0:
        raise ValueError("Сумма изменения не может быть 0")

    async with SessionMaker() as session:
        user = await session.get(User, user_id)
        if user is None:
            user = User(user_id=user_id)
            session.add(user)
            await session.flush()

        old = money(user.balance)
        new = money(old + amount)
        if new < 0:
            raise ValueError(f"Недостаточно средств. Баланс: {old:.2f}")

        user.balance = new
        session.add(Transaction(
            user_id=user_id,
            amount=amount,
            currency=currency,
            type=type_,
            comment=comment,
            deal_code=deal_code,
        ))
        session.add(BalanceHistory(
            user_id=user_id,
            old_balance=old,
            amount=amount,
            new_balance=new,
            op_type=type_,
            performed_by=performed_by,
            comment=comment,
        ))
        await session.commit()
        return new


async def increment_deals_count(user_id: int) -> None:
    async with SessionMaker() as session:
        user = await session.get(User, user_id)
        if user:
            user.deals_count += 1
            await session.commit()


# =====================================================
# РЕКВИЗИТЫ
# =====================================================

async def get_details(user_id: int) -> Optional[UserDetails]:
    async with SessionMaker() as session:
        return await session.get(UserDetails, user_id)


async def set_detail(user_id: int, field: str, value: str) -> None:
    if field not in {"ton", "card", "stars", "usdt", "btc"}:
        raise ValueError(f"Неизвестное поле реквизита: {field}")
    async with SessionMaker() as session:
        details = await session.get(UserDetails, user_id)
        if details is None:
            details = UserDetails(user_id=user_id)
            session.add(details)
        setattr(details, field, value)
        details.updated_at = datetime.utcnow()
        await session.commit()


async def get_detail(user_id: int, field: str) -> Optional[str]:
    details = await get_details(user_id)
    if details is None:
        return None
    return getattr(details, field, None)


# =====================================================
# СДЕЛКИ
# =====================================================

ALLOWED_CURRENCIES = {
    "RUB", "KZT", "UAH", "BYN", "USD", "USDT", "TON", "BTC", "STR",
    "EUR", "GBP", "CNY", "JPY", "TRY", "ETH",
}
ALLOWED_ROLES = {"seller", "buyer"}


async def create_deal(
    code: str,
    creator_id: int,
    role: str,
    amount: float,
    currency: str,
    description: str,
) -> Deal:
    role = (role or "").strip().lower()
    currency = (currency or "").strip().upper()
    description = (description or "").strip()
    amount = money(amount)

    if role not in ALLOWED_ROLES:
        raise ValueError(f"Недопустимая роль: {role}. Допустимо: seller, buyer")
    if currency not in ALLOWED_CURRENCIES:
        raise ValueError(f"Недопустимая валюта: {currency}")
    if amount <= 0:
        raise ValueError("Сумма должна быть больше 0")
    if not description:
        raise ValueError("Описание обязательно")
    if len(description) > 2000:
        raise ValueError("Описание слишком длинное (макс. 2000 символов)")
    if not code or len(code) > 16:
        raise ValueError("Некорректный код сделки")

    creator = await ensure_user(creator_id)
    creator_username = creator.username or creator.first_name or str(creator_id)

    async with SessionMaker() as session:
        existing = await session.get(Deal, code)
        if existing is not None:
            raise ValueError(f"Сделка с кодом {code} уже существует")

        deal = Deal(
            code=code,
            creator_id=creator_id,
            role=role,
            amount=amount,
            currency=currency,
            description=description,
            status="pending",
            seller_id=creator_id if role == "seller" else None,
            buyer_id=creator_id if role == "buyer" else None,
            seller_username=creator_username if role == "seller" else None,
            buyer_username=creator_username if role == "buyer" else None,
        )
        session.add(deal)
        await session.commit()
        await session.refresh(deal)
        return deal


async def get_deal(code: str) -> Optional[Deal]:
    async with SessionMaker() as session:
        return await session.get(Deal, code)


async def update_deal(code: str, **fields) -> None:
    async with SessionMaker() as session:
        deal = await session.get(Deal, code)
        if deal is None:
            return
        for key, value in fields.items():
            setattr(deal, key, value)
        if fields.get("status") in ("done", "cancelled"):
            deal.finished_at = datetime.utcnow()
        await session.commit()


async def join_deal(code: str, user_id: int, username: str) -> Optional[Deal]:
    async with SessionMaker() as session:
        deal = await session.get(Deal, code)
        if deal is None:
            return None

        if deal.creator_id == user_id:
            raise ValueError("Вы не можете присоединиться к своей сделке")

        if deal.role == "seller":
            if deal.buyer_id and deal.buyer_id != user_id:
                raise ValueError("В сделке уже есть покупатель")
            deal.buyer_id = user_id
            deal.buyer_username = username
        else:
            if deal.seller_id and deal.seller_id != user_id:
                raise ValueError("В сделке уже есть продавец")
            deal.seller_id = user_id
            deal.seller_username = username

        if deal.status == "pending":
            deal.status = "active"
        await session.commit()
        await session.refresh(deal)
        return deal


async def delete_deal(code: str) -> None:
    async with SessionMaker() as session:
        deal = await session.get(Deal, code)
        if deal:
            await session.delete(deal)
            await session.commit()


async def get_user_deals(user_id: int) -> list:
    async with SessionMaker() as session:
        result = await session.execute(
            select(Deal).where(
                (Deal.creator_id == user_id)
                | (Deal.buyer_id == user_id)
                | (Deal.seller_id == user_id)
            ).order_by(Deal.created_at.desc())
        )
        return list(result.scalars().all())


async def get_active_deals(user_id: int) -> list:
    async with SessionMaker() as session:
        result = await session.execute(
            select(Deal).where(
                ((Deal.creator_id == user_id)
                 | (Deal.buyer_id == user_id)
                 | (Deal.seller_id == user_id))
                & (Deal.status.in_(("pending", "active", "paid", "gift_sent")))
            ).order_by(Deal.created_at.desc())
        )
        return list(result.scalars().all())


async def get_finished_deals(user_id: int) -> list:
    async with SessionMaker() as session:
        result = await session.execute(
            select(Deal).where(
                ((Deal.creator_id == user_id)
                 | (Deal.buyer_id == user_id)
                 | (Deal.seller_id == user_id))
                & (Deal.status.in_(("done", "cancelled")))
            ).order_by(Deal.created_at.desc())
        )
        return list(result.scalars().all())


async def finish_deal(code: str) -> Optional[Deal]:
    async with SessionMaker() as session:
        deal = await session.get(Deal, code)
        if deal is None or deal.status == "done":
            return deal

        amount = money(deal.amount)
        commission = money(amount * 0.01)
        seller_income = money(amount - commission)
        buyer_bonus = money(amount * 0.002)

        seller_id = deal.seller_id or deal.creator_id
        buyer_id = deal.buyer_id

        seller = await session.get(User, seller_id)
        if seller is None:
            seller = User(user_id=seller_id)
            session.add(seller)
            await session.flush()
        old_s = money(seller.balance)
        seller.balance = money(old_s + seller_income)
        seller.deals_count += 1
        session.add(Transaction(
            user_id=seller_id,
            amount=seller_income,
            currency="RUB",
            type="deal_income",
            deal_code=code,
            comment=f"Доход по сделке {code} (комиссия {commission:.2f})",
        ))
        session.add(BalanceHistory(
            user_id=seller_id,
            old_balance=old_s,
            amount=seller_income,
            new_balance=seller.balance,
            op_type="deal_income",
            comment=f"Доход по сделке {code}",
        ))

        if buyer_id and buyer_id != seller_id:
            buyer = await session.get(User, buyer_id)
            if buyer is None:
                buyer = User(user_id=buyer_id)
                session.add(buyer)
                await session.flush()
            old_b = money(buyer.balance)
            buyer.balance = money(old_b + buyer_bonus)
            buyer.deals_count += 1
            session.add(Transaction(
                user_id=buyer_id,
                amount=buyer_bonus,
                currency="RUB",
                type="deal_income",
                deal_code=code,
                comment=f"Бонус за сделку {code}",
            ))
            session.add(BalanceHistory(
                user_id=buyer_id,
                old_balance=old_b,
                amount=buyer_bonus,
                new_balance=buyer.balance,
                op_type="deal_bonus",
                comment=f"Бонус за сделку {code}",
            ))

        deal.status = "done"
        deal.finished_at = datetime.utcnow()
        await session.commit()
        await session.refresh(deal)
        return deal


# =====================================================
# ОТЗЫВЫ
# =====================================================

DEMO_REVIEWS = [
    {"username": "Dunay", "stars": 4, "text": "Все быстро, только не было 25 звёзд на передачу", "days_ago": 12},
    {"username": "Swim1x", "stars": 5, "text": "Прекрасно, вывел деньги моментально.", "days_ago": 8},
    {"username": "kirill_fx", "stars": 5, "text": "Сделка прошла без сюрпризов, менеджер на связи.", "days_ago": 3},
    {"username": "masha.r", "stars": 5, "text": "Удобно, всё понятно с первого раза.", "days_ago": 5},
    {"username": "ton_trader", "stars": 4, "text": "Норм, чуть долго ждал подтверждение оплаты.", "days_ago": 7},
    {"username": "AlexGifts", "stars": 5, "text": "Вывел на карту за 10 минут. Рекомендую.", "days_ago": 2},
    {"username": "nightowl", "stars": 3, "text": "Работает, но интерфейс местами запутанный.", "days_ago": 15},
    {"username": "VeraK", "stars": 5, "text": "Первая сделка — всё ок, бонус приятный.", "days_ago": 1},
    {"username": "crypto_lev", "stars": 4, "text": "Быстро, но хотелось бы больше валют в одном экране.", "days_ago": 9},
    {"username": "sasha_pro", "stars": 5, "text": "Отлично. Подарок дошёл, деньги на балансе.", "days_ago": 4},
]


async def seed_demo_reviews() -> None:
    async with SessionMaker() as session:
        count = await session.scalar(select(func.count()).select_from(Review))
        if count and count > 0:
            return
        now = datetime.utcnow()
        for item in DEMO_REVIEWS:
            session.add(Review(
                username=item["username"],
                stars=item["stars"],
                text=item["text"],
                created_at=now - timedelta(days=item["days_ago"]),
                is_demo=1,
            ))
        await session.commit()


async def get_reviews(limit: int = 50, offset: int = 0) -> list:
    async with SessionMaker() as session:
        result = await session.execute(
            select(Review)
            .order_by(Review.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())


async def get_reviews_stats() -> dict:
    async with SessionMaker() as session:
        total = await session.scalar(select(func.count()).select_from(Review)) or 0
        avg = await session.scalar(select(func.avg(Review.stars))) or 0.0
        dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        rows = await session.execute(
            select(Review.stars, func.count()).group_by(Review.stars)
        )
        for stars, cnt in rows.all():
            if stars in dist:
                dist[int(stars)] = int(cnt)
        return {
            "total": int(total),
            "average": round(float(avg), 2) if total else 0.0,
            "distribution": dist,
        }


# =====================================================
# АДМИНЫ
# =====================================================

async def add_admin(user_id: int) -> None:
    async with SessionMaker() as session:
        if await session.get(Admin, user_id) is None:
            session.add(Admin(user_id=user_id))
            await session.commit()


async def is_admin(user_id: int) -> bool:
    async with SessionMaker() as session:
        return (await session.get(Admin, user_id)) is not None


# =====================================================
# ВОРКЕР-ПАНЕЛЬ
# =====================================================

async def get_worker_stats(user_id: int) -> dict:
    async with SessionMaker() as session:
        user = await session.get(User, user_id)
        if user is None:
            user = User(user_id=user_id)
            session.add(user)
            try:
                await session.commit()
                await session.refresh(user)
            except Exception:
                await session.rollback()
                user = await session.get(User, user_id)

        total_result = await session.execute(
            select(func.count()).select_from(Deal).where(Deal.creator_id == user_id)
        )
        total = total_result.scalar() or 0

        done_result = await session.execute(
            select(func.count()).select_from(Deal).where(
                (Deal.creator_id == user_id) & (Deal.status == "done")
            )
        )
        done = done_result.scalar() or 0

        cancelled_result = await session.execute(
            select(func.count()).select_from(Deal).where(
                (Deal.creator_id == user_id) & (Deal.status == "cancelled")
            )
        )
        cancelled = cancelled_result.scalar() or 0

        success = done

        turnover_result = await session.execute(
            select(func.sum(Deal.amount)).where(
                (Deal.creator_id == user_id) & (Deal.status == "done")
            )
        )
        turnover = float(turnover_result.scalar() or 0)

        return {
            "success": int(success),
            "done": int(done),
            "cancelled": int(cancelled),
            "total": int(total),
            "turnover": round(turnover, 2),
            "balance": money(user.balance) if user else 0.0,
        }
