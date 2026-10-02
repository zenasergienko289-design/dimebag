# =====================================================
# FastAPI для Mini App
# =====================================================
import hashlib
import hmac
import json
import logging
import random
import string
from typing import Optional
from urllib.parse import parse_qsl

from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

import db
from config import BOT_TOKEN, WEBAPP_DIR, BOT_USERNAME

logger = logging.getLogger(__name__)

app = FastAPI(title="FunPay Mini App API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.options("/{rest_of_path:path}")
async def preflight_handler(request: Request, rest_of_path: str):
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "86400",
        },
    )


def validate_init_data(init_data: str) -> Optional[dict]:
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return None
        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(parsed.items())
        )
        secret_key = hmac.new(
            b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256
        ).digest()
        calculated_hash = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()
        if calculated_hash != received_hash:
            return None
        user_json = parsed.get("user")
        if not user_json:
            return None
        return json.loads(user_json)
    except Exception:
        return None


DEV_MODE = True
DEV_USER_ID = 111


async def auth_user(x_init_data: str = Header(None)) -> dict:
    if DEV_MODE and not x_init_data:
        return {
            "id": DEV_USER_ID,
            "username": "devuser",
            "first_name": "Dev",
        }
    if not x_init_data:
        raise HTTPException(401, "No init data")
    user = validate_init_data(x_init_data)
    if not user:
        raise HTTPException(401, "Invalid init data")
    return user


class DetailPayload(BaseModel):
    field: str
    value: str


class DealPayload(BaseModel):
    role: str
    amount: float = Field(..., gt=0)
    currency: str
    description: str = Field(..., min_length=1, max_length=2000)

    @field_validator("role")
    @classmethod
    def role_ok(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if v not in ("seller", "buyer"):
            raise ValueError("role must be seller or buyer")
        return v

    @field_validator("currency")
    @classmethod
    def currency_ok(cls, v: str) -> str:
        v = (v or "").strip().upper()
        aliases = {"STARS": "STR"}
        v = aliases.get(v, v)
        if v not in db.ALLOWED_CURRENCIES:
            raise ValueError(f"unsupported currency: {v}")
        return v

    @field_validator("description")
    @classmethod
    def desc_ok(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("description is required")
        return v


class WorkerBalancePayload(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str = "RUB"


# =====================================================
# ВСПОМОГАТЕЛЬНОЕ
# =====================================================
def deal_progress_step(status: str) -> int:
    return {
        "pending": 1,
        "active": 2,
        "paid": 3,
        "gift_sent": 4,
        "done": 5,
        "cancelled": 0,
    }.get(status, 1)


def deal_status_label(status: str) -> str:
    return {
        "pending": "Ожидание покупателя",
        "active": "Покупатель присоединился",
        "paid": "Оплачена",
        "gift_sent": "В банке",
        "done": "Завершена",
        "cancelled": "Отменена",
    }.get(status, status)


# =====================================================
# API: ПРОФИЛЬ
# =====================================================
@app.get("/api/me")
async def api_me(user: dict = Depends(auth_user)):
    user_id = user["id"]
    db_user = await db.ensure_user(
        user_id,
        username=user.get("username"),
        first_name=user.get("first_name"),
    )
    is_admin = await db.is_admin(user_id)
    return {
        "user_id": db_user.user_id,
        "username": db_user.username,
        "first_name": db_user.first_name,
        "lang": db_user.lang,
        "balance": db.money(db_user.balance),
        "deals_count": db_user.deals_count,
        "referrals_count": db_user.referrals_count,
        "is_admin": is_admin,
        "bot_username": BOT_USERNAME or "",
    }


@app.post("/api/lang")
async def api_set_lang(payload: dict, user: dict = Depends(auth_user)):
    lang = payload.get("lang", "ru")
    if lang not in ("ru", "en", "uk", "zh", "ar"):
        lang = "ru"
    await db.set_user_lang(user["id"], lang)
    return {"ok": True}


@app.get("/api/details")
async def api_get_details(user: dict = Depends(auth_user)):
    d = await db.get_details(user["id"])
    if d is None:
        return {"ton": "", "card": "", "stars": "", "usdt": "", "btc": ""}
    return {
        "ton": d.ton or "",
        "card": d.card or "",
        "stars": d.stars or "",
        "usdt": d.usdt or "",
        "btc": d.btc or "",
    }


@app.post("/api/details")
async def api_set_detail(payload: DetailPayload, user: dict = Depends(auth_user)):
    await db.set_detail(user["id"], payload.field, payload.value)
    return {"ok": True}


# =====================================================
# API: СДЕЛКИ
# =====================================================
def _serialize_deal(d, me_id: int) -> dict:
    is_creator = d.creator_id == me_id
    is_buyer = (
        (d.role == "seller" and d.buyer_id == me_id) or
        (d.role == "buyer" and (d.creator_id == me_id or d.buyer_id == me_id))
    )
    is_seller = (
        (d.role == "seller" and (d.creator_id == me_id or d.seller_id == me_id)) or
        (d.role == "buyer" and d.seller_id == me_id)
    )
    return {
        "code": d.code,
        "role": d.role,
        "amount": d.amount,
        "currency": d.currency,
        "description": d.description,
        "status": d.status,
        "status_label": deal_status_label(d.status),
        "progress_step": deal_progress_step(d.status),
        "creator_id": d.creator_id,
        "buyer_id": d.buyer_id,
        "seller_id": d.seller_id,
        "buyer_username": d.buyer_username,
        "seller_username": d.seller_username,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "is_creator": is_creator,
        "is_buyer": is_buyer,
        "is_seller": is_seller,
    }


@app.get("/api/deals")
async def api_get_deals(status: str = "active", user: dict = Depends(auth_user)):
    if status == "active":
        deals = await db.get_active_deals(user["id"])
    elif status == "finished":
        deals = await db.get_finished_deals(user["id"])
    elif status == "waiting":
        all_deals = await db.get_user_deals(user["id"])
        deals = [d for d in all_deals if d.status in ("pending", "active", "paid")]
    else:
        deals = await db.get_user_deals(user["id"])

    return [_serialize_deal(d, user["id"]) for d in deals]


@app.get("/api/deal/{code}")
async def api_get_deal(code: str, user: dict = Depends(auth_user)):
    d = await db.get_deal(code)
    if not d:
        raise HTTPException(404, "Deal not found")
    return _serialize_deal(d, user["id"])


@app.post("/api/deal")
async def api_create_deal(payload: DealPayload, user: dict = Depends(auth_user)):
    deal = None
    last_err = None
    for _ in range(5):
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        try:
            deal = await db.create_deal(
                code=code,
                creator_id=user["id"],
                role=payload.role,
                amount=payload.amount,
                currency=payload.currency,
                description=payload.description,
            )
            break
        except ValueError as e:
            last_err = str(e)
            if "уже существует" in last_err:
                continue
            return JSONResponse(status_code=400, content={"ok": False, "error": last_err})
        except Exception:
            logger.exception("create_deal failed")
            return JSONResponse(status_code=500, content={"ok": False, "error": "Внутренняя ошибка"})

    if deal is None:
        return JSONResponse(status_code=500, content={"ok": False, "error": last_err or "Ошибка"})

    deal_link = ""
    if BOT_USERNAME:
        deal_link = f"https://t.me/{BOT_USERNAME}?start=deal_{deal.code}"

    return {
        "ok": True,
        "code": deal.code,
        "status": deal.status,
        "amount": deal.amount,
        "currency": deal.currency,
        "role": deal.role,
        "deal_link": deal_link,
    }


@app.post("/api/deal/{code}/join")
async def api_join_deal(code: str, user: dict = Depends(auth_user)):
    username = user.get("username") or user.get("first_name") or f"id{user['id']}"
    try:
        deal = await db.join_deal(code, user["id"], username)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"ok": False, "error": str(e)})

    if deal is None:
        raise HTTPException(404, "Deal not found")
    return {"ok": True, **_serialize_deal(deal, user["id"])}


@app.post("/api/deal/{code}/cancel")
async def api_cancel_deal(code: str, user: dict = Depends(auth_user)):
    d = await db.get_deal(code)
    if not d:
        raise HTTPException(404, "Deal not found")
    if d.creator_id != user["id"]:
        raise HTTPException(403, "Not your deal")
    if d.status not in ("pending", "active"):
        raise HTTPException(400, "Deal cannot be cancelled in current status")
    await db.delete_deal(code)
    return {"ok": True}


@app.post("/api/deal/{code}/pay")
async def api_pay_deal(code: str, user: dict = Depends(auth_user)):
    d = await db.get_deal(code)
    if not d:
        return JSONResponse(400, {"ok": False, "error": "Сделка не найдена"})
    if d.status not in ("pending", "active"):
        return JSONResponse(400, {"ok": False, "error": f"Сделка уже в статусе: {d.status}"})

    user_id = user["id"]

    if d.role == "seller":
        if d.buyer_id is None:
            buyer_id = user_id
            if buyer_id == d.creator_id:
                return JSONResponse(400, {"ok": False, "error": "Нельзя оплатить свою сделку"})
        else:
            if d.buyer_id != user_id:
                return JSONResponse(403, {"ok": False, "error": "Оплачивать может только покупатель"})
            buyer_id = user_id
        seller_id = d.seller_id or d.creator_id
    else:
        if d.creator_id != user_id and d.buyer_id != user_id:
            return JSONResponse(403, {"ok": False, "error": "Оплачивать может только покупатель"})
        buyer_id = user_id
        seller_id = d.seller_id
        if not seller_id:
            return JSONResponse(400, {"ok": False, "error": "Продавец ещё не присоединился"})

    amount = db.money(d.amount)
    bal = await db.get_balance(buyer_id)
    if bal < amount:
        return JSONResponse(400, {
            "ok": False,
            "error": f"Недостаточно средств. Баланс: {bal:.2f}, нужно: {amount:.2f}",
        })

    try:
        new_bal = await db.add_balance(
            buyer_id, -amount,
            type_="deal_pay",
            comment=f"Оплата сделки #{code}",
            deal_code=code,
            currency="RUB",
            performed_by=user_id,
        )
    except ValueError as e:
        return JSONResponse(400, {"ok": False, "error": str(e)})

    await db.update_deal(code, status="paid", buyer_id=buyer_id)
    return {
        "ok": True,
        "code": code,
        "status": "paid",
        "paid": amount,
        "balance": new_bal,
    }


@app.post("/api/deal/{code}/to-vault")
async def api_deal_to_vault(code: str, user: dict = Depends(auth_user)):
    d = await db.get_deal(code)
    if not d:
        return JSONResponse(400, {"ok": False, "error": "Сделка не найдена"})
    if d.status != "paid":
        return JSONResponse(400, {"ok": False, "error": f"Неверный статус: {d.status}"})

    user_id = user["id"]
    seller_id = d.seller_id or (d.creator_id if d.role == "seller" else None)
    if seller_id != user_id:
        return JSONResponse(403, {"ok": False, "error": "Только продавец может передать в банк"})

    await db.update_deal(code, status="gift_sent")
    return {"ok": True, "code": code, "status": "gift_sent"}


@app.post("/api/deal/{code}/confirm-receive")
async def api_deal_confirm_receive(code: str, user: dict = Depends(auth_user)):
    d = await db.get_deal(code)
    if not d:
        return JSONResponse(400, {"ok": False, "error": "Сделка не найдена"})
    if d.status != "gift_sent":
        return JSONResponse(400, {"ok": False, "error": f"Неверный статус: {d.status}"})

    user_id = user["id"]
    if d.buyer_id != user_id:
        return JSONResponse(403, {"ok": False, "error": "Только покупатель может подтвердить получение"})

    await db.finish_deal(code)
    return {"ok": True, "code": code, "status": "done"}


# =====================================================
# API: ЛИДЕРЫ, ТРАНЗАКЦИИ, ОТЗЫВЫ
# =====================================================
@app.get("/api/leaders")
async def api_leaders(user: dict = Depends(auth_user)):
    from db import User, SessionMaker
    from sqlalchemy import select as sa_select

    async with SessionMaker() as session:
        res = await session.execute(
            sa_select(User).order_by(User.deals_count.desc()).limit(20)
        )
        users = res.scalars().all()

    return [
        {
            "user_id": u.user_id,
            "username": u.username or f"id{u.user_id}",
            "first_name": u.first_name or "",
            "deals_count": u.deals_count,
        }
        for u in users
    ]


@app.get("/api/transactions")
async def api_transactions(user: dict = Depends(auth_user)):
    from db import Transaction, SessionMaker
    from sqlalchemy import select as sa_select

    async with SessionMaker() as session:
        res = await session.execute(
            sa_select(Transaction)
            .where(Transaction.user_id == user["id"])
            .order_by(Transaction.created_at.desc())
            .limit(50)
        )
        txs = res.scalars().all()

    return [
        {
            "id": t.id,
            "amount": t.amount,
            "currency": t.currency,
            "type": t.type,
            "comment": t.comment,
            "deal_code": t.deal_code,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in txs
    ]


@app.get("/api/reviews")
async def api_reviews(user: dict = Depends(auth_user)):
    stats = await db.get_reviews_stats()
    reviews = await db.get_reviews(limit=50)
    return {
        "stats": stats,
        "reviews": [
            {
                "id": r.id,
                "username": r.username,
                "stars": r.stars,
                "text": r.text,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "is_demo": bool(r.is_demo),
            }
            for r in reviews
        ],
    }


# =====================================================
# API: ВОРКЕР-ПАНЕЛЬ (без проверки админа)
# =====================================================
@app.get("/api/worker/stats")
async def api_worker_stats(user: dict = Depends(auth_user)):
    return await db.get_worker_stats(user["id"])


@app.post("/api/worker/balance")
async def api_worker_balance(payload: WorkerBalancePayload, user: dict = Depends(auth_user)):
    if payload.amount <= 0:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Сумма должна быть больше 0"})

    new_balance = await db.add_balance(
        user["id"],
        payload.amount,
        type_="worker_deposit",
        comment=f"Пополнение из воркер-панели ({payload.currency})",
        performed_by=user["id"],
    )
    return {"ok": True, "new_balance": new_balance, "added": payload.amount}


# =====================================================
# ОТДАЧА ФРОНТА
# =====================================================
print("=" * 60)
print(f"DEBUG: WEBAPP_DIR = {WEBAPP_DIR}")
print(f"DEBUG: exists = {WEBAPP_DIR.exists()}")
print("=" * 60)

if WEBAPP_DIR and WEBAPP_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEBAPP_DIR)), name="static")

    @app.get("/")
    async def root():
        return FileResponse(str(WEBAPP_DIR / "index.html"))
else:
    @app.get("/")
    async def root_fallback():
        return {"error": "webapp directory not found", "expected": str(WEBAPP_DIR)}



    if __name__ == "__main__":
        import uvicorn
        import os

        port = int(os.getenv("PORT", 3000))
        uvicorn.run(app, host="0.0.0.0", port=port)