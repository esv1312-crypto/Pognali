import os
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, FastAPI, HTTPException, Header
from pydantic import BaseModel, ConfigDict
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./pognali_dev.db")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    provider: Mapped[str] = mapped_column(String(30), default="dev")
    provider_user_id: Mapped[str] = mapped_column(String(200), unique=True)
    city: Mapped[str] = mapped_column(String(120), default="Симферополь")
    birth_date: Mapped[Optional[date]] = mapped_column(nullable=True)
    bio: Mapped[str] = mapped_column(Text, default="")
    photo_url: Mapped[str] = mapped_column(String(500), default="")

class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(120), default="Симферополь")
    location: Mapped[str] = mapped_column(String(300))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    capacity: Mapped[int] = mapped_column(Integer, default=10)
    description: Mapped[str] = mapped_column(Text, default="")
    lat: Mapped[float] = mapped_column(Float, default=44.9521)
    lon: Mapped[float] = mapped_column(Float, default=34.1024)
    organizer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    organizer: Mapped[User] = relationship()

class EventParticipant(Base):
    __tablename__ = "event_participants"
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    target_type: Mapped[str] = mapped_column(String(20))
    target_id: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Block(Base):
    __tablename__ = "blocks"
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    blocked_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

Base.metadata.create_all(engine)
app = FastAPI(title="Погнали API", version="1.3")

class DevLogin(BaseModel):
    name: str
    provider_user_id: str = "demo"

class EventCreate(BaseModel):
    title: str
    city: str = "Симферополь"
    location: str
    starts_at: datetime
    capacity: int = 10
    description: str = ""
    lat: float = 44.9521
    lon: float = 34.1024

class MessageCreate(BaseModel):
    text: str

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    city: str
    birth_date: Optional[date] = None
    bio: str = ""
    photo_url: str = ""

class UserUpdate(BaseModel):
    name: Optional[str] = None
    city: Optional[str] = None
    birth_date: Optional[date] = None
    bio: Optional[str] = None
    photo_url: Optional[str] = None

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

def db():
    with SessionLocal() as session:
        yield session

def make_token(user: User) -> str:
    return jwt.encode({"sub": str(user.id), "exp": datetime.now(timezone.utc) + timedelta(days=30)}, JWT_SECRET, algorithm="HS256")

def current_user(authorization: Optional[str] = Header(default=None), session: Session = Depends(db)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Нужна авторизация")
    try:
        payload = jwt.decode(authorization.split(" ", 1)[1], JWT_SECRET, algorithms=["HS256"])
        uid = int(payload["sub"])
    except Exception:
        raise HTTPException(401, "Недействительный токен")
    user = session.get(User, uid)
    if not user:
        raise HTTPException(401, "Пользователь не найден")
    return user

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.4"}


@app.get("/auth/providers")
def auth_providers():
    """Public discovery endpoint. Real OAuth credentials are supplied via env vars."""
    return {
        "google": bool(os.getenv("GOOGLE_CLIENT_ID")),
        "vkontakte": bool(os.getenv("VK_CLIENT_ID")),
        "dev": True,
    }


@app.get("/auth/{provider}/start")
def oauth_start(provider: str):
    """OAuth entrypoint placeholder. Returns configuration status until real credentials are installed."""
    provider = provider.lower()
    if provider not in {"google", "vkontakte"}:
        raise HTTPException(404, "Неизвестный провайдер")
    configured = bool(os.getenv("GOOGLE_CLIENT_ID" if provider == "google" else "VK_CLIENT_ID"))
    if not configured:
        raise HTTPException(503, "OAuth пока не настроен: нужны ключи провайдера")
    return {"provider": provider, "status": "ready", "message": "OAuth redirect can be wired here"}

@app.post("/auth/dev", response_model=TokenOut)
def dev_login(data: DevLogin, session: Session = Depends(db)):
    user = session.scalar(select(User).where(User.provider == "dev", User.provider_user_id == data.provider_user_id))
    if not user:
        user = User(name=data.name, provider="dev", provider_user_id=data.provider_user_id)
        session.add(user); session.commit(); session.refresh(user)
    elif data.name and user.name != data.name:
        user.name = data.name; session.commit()
    return {"access_token": make_token(user), "user": user}

@app.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user

@app.patch("/me", response_model=UserOut)
def update_me(data: UserUpdate, user: User = Depends(current_user), session: Session = Depends(db)):
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is not None:
        if not changes["name"].strip():
            raise HTTPException(400, "Имя не может быть пустым")
        changes["name"] = changes["name"].strip()[:120]
    if "city" in changes and changes["city"] is not None:
        changes["city"] = changes["city"].strip()[:120]
    if "bio" in changes and changes["bio"] is not None:
        changes["bio"] = changes["bio"].strip()[:1000]
    if "photo_url" in changes and changes["photo_url"] is not None:
        changes["photo_url"] = changes["photo_url"].strip()[:500]
    for key, value in changes.items():
        setattr(user, key, value)
    session.commit()
    session.refresh(user)
    return user

@app.get("/me/events")
def my_events(user: User = Depends(current_user), session: Session = Depends(db)):
    rows = session.scalars(select(Event).where(Event.organizer_id == user.id).order_by(Event.starts_at)).all()
    return [{"id": e.id, "title": e.title, "location": e.location, "starts_at": e.starts_at, "capacity": e.capacity} for e in rows]

@app.get("/me/participations")
def my_participations(user: User = Depends(current_user), session: Session = Depends(db)):
    ids = session.scalars(select(EventParticipant.event_id).where(EventParticipant.user_id == user.id)).all()
    if not ids:
        return []
    rows = session.scalars(select(Event).where(Event.id.in_(ids)).order_by(Event.starts_at)).all()
    return [{"id": e.id, "title": e.title, "location": e.location, "starts_at": e.starts_at, "capacity": e.capacity} for e in rows]

@app.get("/events")
def list_events(session: Session = Depends(db)):
    rows = session.scalars(select(Event).order_by(Event.starts_at)).all()
    out=[]
    for e in rows:
        count = session.scalar(select(EventParticipant).where(EventParticipant.event_id == e.id).count()) if False else len(session.scalars(select(EventParticipant).where(EventParticipant.event_id == e.id)).all())
        out.append({"id":e.id,"title":e.title,"city":e.city,"location":e.location,"starts_at":e.starts_at,"capacity":e.capacity,"participants":count,"description":e.description,"lat":e.lat,"lon":e.lon})
    return out

@app.get("/events/{event_id}")
def get_event(event_id: int, authorization: Optional[str] = Header(default=None), session: Session = Depends(db)):
    e = session.get(Event, event_id)
    if not e:
        raise HTTPException(404, "Событие не найдено")
    participants = session.scalars(select(EventParticipant).where(EventParticipant.event_id == e.id)).all()
    current_id = None
    if authorization and authorization.lower().startswith("bearer "):
        try:
            payload = jwt.decode(authorization.split(" ", 1)[1], JWT_SECRET, algorithms=["HS256"])
            current_id = int(payload["sub"])
        except Exception:
            current_id = None
    participant_ids = {p.user_id for p in participants}
    return {
        "id": e.id, "title": e.title, "city": e.city, "location": e.location,
        "starts_at": e.starts_at, "capacity": e.capacity, "participants": len(participants),
        "description": e.description, "lat": e.lat, "lon": e.lon,
        "organizer_id": e.organizer_id, "is_joined": current_id in participant_ids if current_id else False,
        "is_full": len(participants) >= e.capacity,
    }

@app.get("/events/{event_id}/participants")
def event_participants(event_id: int, session: Session = Depends(db)):
    if not session.get(Event, event_id):
        raise HTTPException(404, "Событие не найдено")
    rows = session.scalars(select(EventParticipant).where(EventParticipant.event_id == event_id)).all()
    users = []
    for row in rows:
        u = session.get(User, row.user_id)
        if u:
            users.append({"id": u.id, "name": u.name, "city": u.city, "photo_url": u.photo_url})
    return users

@app.post("/events")
def create_event(data: EventCreate, user: User=Depends(current_user), session: Session=Depends(db)):
    if not data.title.strip() or not data.location.strip():
        raise HTTPException(400, "Нужно указать что и где")
    if data.capacity < 2 or data.capacity > 100:
        raise HTTPException(400, "Лимит участников: от 2 до 100")
    if data.starts_at <= datetime.now(timezone.utc):
        raise HTTPException(400, "Событие должно быть в будущем")
    data.title = data.title.strip()
    data.location = data.location.strip()
    data.description = data.description.strip()
    e=Event(**data.model_dump(),organizer_id=user.id)
    session.add(e); session.commit(); session.refresh(e)
    session.add(EventParticipant(event_id=e.id,user_id=user.id)); session.commit()
    return {"id":e.id,"title":e.title}

@app.post("/events/{event_id}/join")
def join(event_id:int,user:User=Depends(current_user),session:Session=Depends(db)):
    e=session.get(Event,event_id)
    if not e: raise HTTPException(404,"Событие не найдено")
    existing=session.get(EventParticipant,(event_id,user.id))
    if existing: return {"status":"already_joined"}
    count=len(session.scalars(select(EventParticipant).where(EventParticipant.event_id==event_id)).all())
    if count>=e.capacity: raise HTTPException(409,"Мест нет")
    session.add(EventParticipant(event_id=event_id,user_id=user.id)); session.commit()
    return {"status":"joined"}

@app.post("/events/{event_id}/leave")
def leave(event_id:int,user:User=Depends(current_user),session:Session=Depends(db)):
    p=session.get(EventParticipant,(event_id,user.id))
    if p: session.delete(p); session.commit()
    return {"status":"left"}

@app.get("/events/{event_id}/participants", response_model=list[UserOut])
def participants(event_id:int,session:Session=Depends(db)):
    ids=session.scalars(select(EventParticipant.user_id).where(EventParticipant.event_id==event_id)).all()
    return session.scalars(select(User).where(User.id.in_(ids))).all() if ids else []

@app.get("/events/{event_id}/messages")
def messages(event_id:int,user:User=Depends(current_user),session:Session=Depends(db)):
    if not session.get(EventParticipant,(event_id,user.id)): raise HTTPException(403,"Только участники")
    rows=session.scalars(select(Message).where(Message.event_id==event_id).order_by(Message.created_at)).all()
    return [{"id":m.id,"user_id":m.user_id,"text":m.text,"created_at":m.created_at} for m in rows]

@app.post("/events/{event_id}/messages")
def send_message(event_id:int,data:MessageCreate,user:User=Depends(current_user),session:Session=Depends(db)):
    if not session.get(EventParticipant,(event_id,user.id)): raise HTTPException(403,"Только участники")
    if not data.text.strip(): raise HTTPException(400,"Пустое сообщение")
    m=Message(event_id=event_id,user_id=user.id,text=data.text.strip()); session.add(m); session.commit(); session.refresh(m)
    return {"id":m.id,"user_id":m.user_id,"name":user.name,"text":m.text,"created_at":m.created_at}


# --- Moderation / safety MVP ---
from pydantic import Field
from enum import Enum

class ReportTarget(str, Enum):
    USER = "user"
    EVENT = "event"
    MESSAGE = "message"

class ReportIn(BaseModel):
    target_type: ReportTarget
    target_id: int
    reason: str = Field(min_length=3, max_length=500)

class BlockIn(BaseModel):
    user_id: int

@app.post("/reports", status_code=201)
def create_report(data: ReportIn, user: User = Depends(current_user), session: Session = Depends(db)):
    if data.target_type == ReportTarget.USER and data.target_id == user.id:
        raise HTTPException(400, "Нельзя пожаловаться на самого себя")
    report = Report(reporter_id=user.id, target_type=data.target_type.value, target_id=data.target_id, reason=data.reason.strip())
    session.add(report); session.commit(); session.refresh(report)
    return {"id": report.id, "status": report.status}

@app.post("/blocks", status_code=201)
def block_user(data: BlockIn, user: User = Depends(current_user), session: Session = Depends(db)):
    if data.user_id == user.id:
        raise HTTPException(400, "Нельзя заблокировать самого себя")
    if not session.get(User, data.user_id):
        raise HTTPException(404, "Пользователь не найден")
    existing = session.get(Block, (user.id, data.user_id))
    if not existing:
        session.add(Block(owner_id=user.id, blocked_user_id=data.user_id)); session.commit()
    return {"blocked": True, "user_id": data.user_id}

@app.delete("/blocks/{user_id}")
def unblock_user(user_id: int, user: User = Depends(current_user), session: Session = Depends(db)):
    existing = session.get(Block, (user.id, user_id))
    if existing:
        session.delete(existing); session.commit()
    return {"blocked": False, "user_id": user_id}

@app.get("/blocks")
def list_blocks(user: User = Depends(current_user), session: Session = Depends(db)):
    ids = session.scalars(select(Block.blocked_user_id).where(Block.owner_id == user.id)).all()
    return [{"user_id": uid} for uid in ids]
