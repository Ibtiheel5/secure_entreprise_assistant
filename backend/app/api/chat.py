from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.agent import run_agent
from app.audit.service import log_access
from app.auth.deps import AuthContext, require_permission
from app.database.models import ChatMessage, ChatSession
from app.database.session import get_db
from app.rag.llm import LLMUnavailable
from app.rag.pipeline import answer_question

router = APIRouter(prefix="/api", tags=["chat"])


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: int | None = None
    department: str | None = Field(default=None, pattern="^(HR|IT|FINANCE|POLICIES)$")


class ChatOut(BaseModel):
    session_id: int
    answer: str
    citations: list[dict]
    grounded: bool


class SessionOut(BaseModel):
    id: int
    title: str
    created_at: datetime


class MessageOut(BaseModel):
    role: str
    content: str
    citations: list | None
    created_at: datetime


class SessionDetail(SessionOut):
    messages: list[MessageOut]


def _own_session(db: Session, ctx: AuthContext, sid: int, request: Request) -> ChatSession:
    s = db.scalar(select(ChatSession).where(ChatSession.id == sid, ChatSession.user_id == ctx.user.id))
    if s is None:  # la session d'un autre utilisateur est indiscernable d'une session inexistante
        log_access(db, action="chat.session_access", allowed=False, user_id=ctx.user.id, resource_type="chat_session",
                   resource_id=sid, reason="not_found_or_forbidden", request=request)
        raise HTTPException(404, "Session not found")
    return s


@router.post("/chat", response_model=ChatOut)
def chat(body: ChatIn, request: Request, ctx: AuthContext = Depends(require_permission("chat:use")),
         db: Session = Depends(get_db)):
    session = _own_session(db, ctx, body.session_id, request) if body.session_id else None
    try:
        result = answer_question(db, ctx, body.message, body.department, request)
    except LLMUnavailable as exc:
        raise HTTPException(503, str(exc))
    if session is None:
        session = ChatSession(user_id=ctx.user.id, title=body.message[:80])
        db.add(session)
        db.flush()
    db.add(ChatMessage(session_id=session.id, role="user", content=body.message))
    db.add(ChatMessage(session_id=session.id, role="assistant", content=result.answer, citations=result.citations))
    db.commit()
    return ChatOut(session_id=session.id, answer=result.answer, citations=result.citations, grounded=result.grounded)


@router.post("/agent/chat")
def agent_chat(body: ChatIn, ctx: AuthContext = Depends(require_permission("chat:use")), db: Session = Depends(get_db)):
    try:
        return run_agent(db, ctx, body.message)
    except LLMUnavailable as exc:
        raise HTTPException(503, str(exc))


@router.get("/chat/sessions", response_model=list[SessionOut])
def list_sessions(ctx: AuthContext = Depends(require_permission("chat:use")), db: Session = Depends(get_db)):
    rows = db.scalars(select(ChatSession).where(ChatSession.user_id == ctx.user.id)
                      .order_by(ChatSession.created_at.desc()).limit(50)).all()
    return [SessionOut(id=s.id, title=s.title, created_at=s.created_at) for s in rows]


@router.get("/chat/sessions/{sid}", response_model=SessionDetail)
def get_session(sid: int, request: Request, ctx: AuthContext = Depends(require_permission("chat:use")),
                db: Session = Depends(get_db)):
    s = _own_session(db, ctx, sid, request)
    msgs = db.scalars(select(ChatMessage).where(ChatMessage.session_id == s.id).order_by(ChatMessage.id)).all()
    return SessionDetail(id=s.id, title=s.title, created_at=s.created_at,
                         messages=[MessageOut(role=m.role, content=m.content, citations=m.citations,
                                              created_at=m.created_at) for m in msgs])
