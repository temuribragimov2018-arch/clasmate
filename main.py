import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend.config import get_settings
from backend.database import engine, Base, SessionLocal
from backend.models import *
from backend.routers import auth, users, chats, homework, schedule, announcements, polls, events, notifications, pro, admin, collections, uploads, files, reels, coins

settings = get_settings()

# Logging (видно в Railway Deploy Logs)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("classmate")


# Rate limiter
limiter = Limiter(key_func=get_remote_address)


def seed_data():
    """Create initial data if not exists; ensure admin can always log in."""
    from backend.utils.security import get_password_hash
    db = SessionLocal()
    try:
        cls = db.query(Class).first()
        if not cls:
            cls = Class(name="Класс 10А", description="Основной класс", invite_code="CLASS10A")
            db.add(cls)
            db.flush()
            logger.info("Seed: Class CLASS10A created")


        if cls and (not cls.invite_code or cls.invite_code.strip() == ""):
            cls.invite_code = "CLASS10A"
        elif cls and cls.invite_code != "CLASS10A":
            # keep existing; also ensure at least one class has CLASS10A
            if not db.query(Class).filter(Class.invite_code == "CLASS10A").first():
                cls.invite_code = "CLASS10A"

        chat = db.query(Chat).filter(Chat.class_id == cls.id, Chat.chat_type == "general").first()
        if not chat:
            chat = Chat(name="Общий чат класса", chat_type="general", class_id=cls.id)
            db.add(chat)
            db.flush()
            logger.info("Seed: General chat created")

        def ensure_user(username, password, display_name, role):
            u = db.query(User).filter(User.username == username).first()
            if not u:
                u = User(
                    username=username,
                    hashed_password=get_password_hash(password),
                    display_name=display_name,
                    role=role if isinstance(role, str) else getattr(role, "value", str(role)),
                    is_active=True,
                )
                db.add(u)
                db.flush()
                logger.info("Seed: User %s created", username)
            else:
                # Re-hash password so login always works after bcrypt/passlib changes
                u.hashed_password = get_password_hash(password)
                u.is_active = True
                logger.info("Seed: User %s password refreshed", username)
            if not db.query(ClassMember).filter(ClassMember.user_id == u.id, ClassMember.class_id == cls.id).first():
                db.add(ClassMember(user_id=u.id, class_id=cls.id))
            if chat and not db.query(ChatMember).filter(ChatMember.chat_id == chat.id, ChatMember.user_id == u.id).first():
                db.add(ChatMember(chat_id=chat.id, user_id=u.id))
            return u

        ensure_user("admin", "admin123", "Администратор", "admin")
        ensure_user("starosta", "starosta123", "Староста Класса", "starosta")

        if not db.query(ProPlan).first():
            for name, days, price in [
                ("PRO 30 дней", 30, 199),
                ("PRO 90 дней", 90, 499),
                ("PRO 365 дней", 365, 1499),
            ]:
                db.add(ProPlan(name=name, duration_days=days, price=price, description=name))
            logger.info("Seed: PRO plans created")

        # Staff chat admin + starostas
        staff = db.query(Chat).filter(Chat.chat_type == "staff").first()
        if not staff:
            staff = Chat(name="Чат Админ ↔ Старосты", chat_type="staff", class_id=None)
            db.add(staff)
            db.flush()
            logger.info("Seed: Staff chat created")
        for u in db.query(User).filter(User.role.in_(["admin", "starosta"])).all():
            if not db.query(ChatMember).filter(ChatMember.chat_id == staff.id, ChatMember.user_id == u.id).first():
                db.add(ChatMember(chat_id=staff.id, user_id=u.id))


        from backend.models.reels import CoinPackage
        if not db.query(CoinPackage).first():
            for amt, price in [(10, 10), (50, 50), (100, 100), (500, 500), (1000, 1000)]:
                db.add(CoinPackage(amount=amt, price_smn=price))
            logger.info("Seed: Coin packages created")

        db.commit()
        logger.info("Seed ready: admin/admin123, starosta/starosta123, invite CLASS10A")
    except Exception as e:
        logger.exception("Seed error: %s", e)
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure upload dir
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    try:
        logger.info("DB init: create_all...")
        Base.metadata.create_all(bind=engine)
        logger.info("DB init: create_all done")
        try:
            from backend.utils.migrate import ensure_schema, force_user_columns, fix_chat_type_column
            summary = ensure_schema()
            logger.info("ensure_schema summary: %s", summary)
            force_summary = force_user_columns()
            logger.info("force_user_columns summary: %s", force_summary)
            chat_fix = fix_chat_type_column()
            logger.info("fix_chat_type_column: %s", chat_fix)
        except Exception as mig_e:
            logger.exception("Migrate warning: %s", mig_e)
        try:
            seed_data()
            logger.info("Seed data completed")
        except Exception as seed_e:
            logger.exception("Seed warning: %s", seed_e)
        logger.info("Database ready")
    except Exception as e:
        logger.exception("WARNING: DB init deferred: %s", e)
    yield


app = FastAPI(
    redirect_slashes=True,
    title="ClassMate API",
    description="Закрытый мессенджер для школьного класса",
    version="1.0.0",
    lifespan=lifespan
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS: при allow_origins=["*"] credentials нельзя включать
_origins = settings.cors_origins_list
_allow_credentials = "*" not in _origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins if _origins else ["*"],
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": "Validation error", "errors": exc.errors()})


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    import traceback
    traceback.print_exc()
    # Always include message so Railway logs + client can show real cause during setup
    return JSONResponse(status_code=500, content={"detail": str(exc) or "Internal server error"})


# Routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(chats.router)
app.include_router(homework.router)
app.include_router(schedule.router)
app.include_router(announcements.router)
app.include_router(polls.router)
app.include_router(events.router)
app.include_router(notifications.router)
app.include_router(pro.router)
app.include_router(admin.router)
app.include_router(collections.router)
app.include_router(uploads.router)
app.include_router(files.router)
app.include_router(reels.router)
app.include_router(coins.router)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}


# Serve frontend
frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=os.path.join(frontend_path, "static")), name="static")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

    @app.get("/")
    def index():
        index_file = os.path.join(frontend_path, "templates", "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "ClassMate API is running. Frontend not found."}

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        # SPA fallback — serve index for non-api routes
        if full_path.startswith("api/") or full_path.startswith("static/") or full_path == "health":
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        index_file = os.path.join(frontend_path, "templates", "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return JSONResponse(status_code=404, content={"detail": "Not found"})


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=settings.DEBUG)
