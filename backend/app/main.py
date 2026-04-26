from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
import uuid

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import BASE_DIR
from app.database import get_db, init_db
from app.models import Message, MessageType, RmaThread
from app.schemas import (
    BoardResponse,
    MessageRead,
    MessageUpdate,
    RmaThreadBoardItem,
    RmaThreadCreate,
    RmaThreadListResponse,
    RmaThreadRead,
    RmaThreadUpdate,
)


UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_ATTACHMENT_SIZE = 100 * 1024 * 1024
ALLOWED_ATTACHMENT_PREFIXES = ("image/", "video/")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="GPU Support RMA Log API",
    version="0.1.0",
    lifespan=lifespan,
)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def build_preview(content: str, limit: int = 120) -> str:
    normalized = " ".join(content.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


def attachment_preview(message: Message) -> str | None:
    if message.attachment_filename:
        return f"[attachment] {message.attachment_filename}"
    return None


def latest_preview_for_thread(db: Session, thread_id: str) -> str | None:
    message = db.scalar(
        select(Message)
        .where(Message.rma_thread_id == thread_id)
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    if message is None:
        return None
    if message.content:
        return build_preview(message.content)
    return attachment_preview(message)


def to_thread_read(db: Session, thread: RmaThread) -> RmaThreadRead:
    return RmaThreadRead(
        id=thread.id,
        rma_number=thread.rma_number,
        title=thread.title,
        customer_name=thread.customer_name,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        latest_message_preview=latest_preview_for_thread(db, thread.id),
    )


def thread_messages(db: Session, thread_id: str) -> list[Message]:
    return list(
        db.scalars(
            select(Message)
            .where(Message.rma_thread_id == thread_id)
            .order_by(Message.created_at.asc())
        )
    )


def thread_search_stmt(
    rma: str | None,
    rma_match: str,
    keyword: str | None,
):
    stmt = select(RmaThread)
    rma = rma.strip() if rma else None
    keyword = keyword.strip() if keyword else None

    if rma:
        if rma_match == "exact":
            stmt = stmt.where(RmaThread.rma_number == rma)
        else:
            stmt = stmt.where(RmaThread.rma_number.ilike(f"%{rma}%"))

    if keyword:
        stmt = (
            stmt.join(Message)
            .where(Message.content.ilike(f"%{keyword}%"))
            .distinct()
        )

    return stmt


def save_attachment(file: UploadFile | None) -> dict[str, str | int] | None:
    if file is None or not file.filename:
        return None

    mime_type = file.content_type or "application/octet-stream"
    if not mime_type.startswith(ALLOWED_ATTACHMENT_PREFIXES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="only image and video attachments are allowed",
        )

    original_name = Path(file.filename).name
    suffix = Path(original_name).suffix.lower()
    stored_name = f"{uuid.uuid4()}{suffix}"
    stored_path = UPLOAD_DIR / stored_name
    total = 0

    with stored_path.open("wb") as output:
        while chunk := file.file.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_ATTACHMENT_SIZE:
                output.close()
                stored_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="attachment must be 100MB or smaller",
                )
            output.write(chunk)

    return {
        "attachment_url": f"/uploads/{stored_name}",
        "attachment_filename": original_name,
        "attachment_mime_type": mime_type,
        "attachment_size": total,
    }


def attachment_file_path(message: Message) -> Path | None:
    if not message.attachment_url or not message.attachment_url.startswith("/uploads/"):
        return None

    filename = Path(message.attachment_url).name
    path = UPLOAD_DIR / filename
    try:
        resolved = path.resolve()
        upload_root = UPLOAD_DIR.resolve()
    except OSError:
        return None

    if resolved.parent != upload_root:
        return None
    return resolved


def remove_attachment_files(paths: list[Path]) -> None:
    for path in paths:
        path.unlink(missing_ok=True)


@app.post(
    "/rma-threads",
    response_model=RmaThreadRead,
    status_code=status.HTTP_201_CREATED,
)
def create_rma_thread(
    payload: RmaThreadCreate,
    db: Session = Depends(get_db),
) -> RmaThreadRead:
    exists = db.scalar(
        select(RmaThread).where(RmaThread.rma_number == payload.rma_number)
    )
    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="rma_number already exists",
        )

    thread = RmaThread(
        rma_number=payload.rma_number,
        title=payload.title,
        customer_name=payload.customer_name,
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return to_thread_read(db, thread)


@app.get("/rma-threads/{rma_number}", response_model=RmaThreadRead)
def get_rma_thread(
    rma_number: str,
    db: Session = Depends(get_db),
) -> RmaThreadRead:
    thread = db.scalar(select(RmaThread).where(RmaThread.rma_number == rma_number))
    if thread is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="rma_thread not found",
        )
    return to_thread_read(db, thread)


@app.patch("/rma-threads/{rma_number}", response_model=RmaThreadRead)
def update_rma_thread(
    rma_number: str,
    payload: RmaThreadUpdate,
    db: Session = Depends(get_db),
) -> RmaThreadRead:
    thread = db.scalar(select(RmaThread).where(RmaThread.rma_number == rma_number))
    if thread is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="rma_thread not found",
        )

    thread.title = payload.title
    thread.customer_name = payload.customer_name
    thread.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(thread)
    return to_thread_read(db, thread)


@app.delete("/rma-threads/{rma_number}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rma_thread(
    rma_number: str,
    db: Session = Depends(get_db),
) -> Response:
    thread = db.scalar(select(RmaThread).where(RmaThread.rma_number == rma_number))
    if thread is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="rma_thread not found",
        )

    attachment_paths = [
        path
        for message in thread_messages(db, thread.id)
        if (path := attachment_file_path(message)) is not None
    ]
    db.delete(thread)
    db.commit()
    remove_attachment_files(attachment_paths)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/rma-threads", response_model=RmaThreadListResponse)
def list_rma_threads(
    rma: str | None = Query(default=None, description="Partial RMA number match"),
    rma_match: str = Query(default="partial", pattern="^(partial|exact)$"),
    keyword: str | None = Query(default=None, description="Message content keyword"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> RmaThreadListResponse:
    stmt = thread_search_stmt(rma, rma_match, keyword)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    threads = db.scalars(
        stmt.order_by(RmaThread.updated_at.desc()).limit(limit).offset(offset)
    ).all()

    return RmaThreadListResponse(
        items=[to_thread_read(db, thread) for thread in threads],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get("/board", response_model=BoardResponse)
def get_board(
    rma: str | None = Query(default=None, description="RMA number match"),
    rma_match: str = Query(default="partial", pattern="^(partial|exact)$"),
    keyword: str | None = Query(default=None, description="Message content keyword"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> BoardResponse:
    stmt = thread_search_stmt(rma, rma_match, keyword)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    threads = db.scalars(
        stmt.order_by(RmaThread.updated_at.desc()).limit(limit).offset(offset)
    ).all()

    items = []
    for thread in threads:
        base = to_thread_read(db, thread)
        items.append(
            RmaThreadBoardItem(
                **base.model_dump(),
                messages=thread_messages(db, thread.id),
            )
        )

    return BoardResponse(items=items, total=total, limit=limit, offset=offset)


@app.get("/rma-threads/{rma_number}/messages", response_model=list[MessageRead])
def list_messages(
    rma_number: str,
    db: Session = Depends(get_db),
) -> list[MessageRead]:
    thread = db.scalar(select(RmaThread).where(RmaThread.rma_number == rma_number))
    if thread is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="rma_thread not found",
        )

    return thread_messages(db, thread.id)


@app.post(
    "/rma-threads/{rma_number}/messages",
    response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
)
def add_message(
    rma_number: str,
    type: MessageType = Form(...),
    content: str = Form(default=""),
    attachment: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> MessageRead:
    thread = db.scalar(select(RmaThread).where(RmaThread.rma_number == rma_number))
    if thread is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="rma_thread not found",
        )

    content = content.strip()
    attachment_data = save_attachment(attachment)
    if not content and attachment_data is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="content or attachment is required",
        )

    message = Message(
        rma_thread_id=thread.id,
        type=type.value,
        content=content,
        **(attachment_data or {}),
    )
    thread.updated_at = datetime.now(timezone.utc)

    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@app.patch("/messages/{message_id}", response_model=MessageRead)
def update_message(
    message_id: str,
    payload: MessageUpdate,
    db: Session = Depends(get_db),
) -> MessageRead:
    message = db.scalar(select(Message).where(Message.id == message_id))
    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="message not found",
        )

    if not payload.content and not message.attachment_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="content or attachment is required",
        )

    message.type = payload.type.value
    message.content = payload.content
    thread = db.scalar(select(RmaThread).where(RmaThread.id == message.rma_thread_id))
    if thread is not None:
        thread.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(message)
    return message


@app.delete("/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message(
    message_id: str,
    db: Session = Depends(get_db),
) -> Response:
    message = db.scalar(select(Message).where(Message.id == message_id))
    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="message not found",
        )

    thread = db.scalar(select(RmaThread).where(RmaThread.id == message.rma_thread_id))
    attachment_path = attachment_file_path(message)
    db.delete(message)
    if thread is not None:
        thread.updated_at = datetime.now(timezone.utc)
    db.commit()
    if attachment_path is not None:
        remove_attachment_files([attachment_path])
    return Response(status_code=status.HTTP_204_NO_CONTENT)
