from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from sqlalchemy.orm import Session

from src.crud import (
    get_current_user,
    SECRET_KEY,
    ALGORITHM
)


from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, case, distinct, text
from src.schema import UserLogin,LearningItemView,LearningItemViewResponse, CreateLabel, UpdateLabel, DashboardSummaryResponse , LearningItemsSummaryResponse , GenerateRevisionRequest, GenerateRevisionResponse, deleteLearningItem
# DB + Models
from src.db import get_db
from src.model import User, LearningItem, Label, LearningItemLabel, Question, RevisionSession, UserAttempt, Media, UserSession
from fastapi import Form, File, UploadFile
from typing import List
import json
import uuid


# Auth
from src.crud import create_access_token, upload_file, get_current_user, generate_revision_content

router = APIRouter()


security = HTTPBearer()


@router.post("/register")
def register(username: str, email: str, password: str, db: Session = Depends(get_db)):
    existing = db.query(User).filter(
        (User.username == username) | (User.email == email)
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="User exists")

    user = User(
        username=username,
        email=email,
        password_hash=password 
    )

    db.add(user)
    db.commit()

    userData = db.query(User).filter(
        User.username == user.username,
        user.password_hash == user.password_hash
    ).first()

    # GENERATE SESSION ID
    session_id = str(uuid.uuid4())

    # SESSION EXPIRY
    expires_at = datetime.utcnow() + timedelta(minutes=30)

    # CREATE SESSION ENTRY
    session = UserSession(
        user_id=userData.id,
        session_id=session_id,
        expires_at=expires_at
    )

    db.add(session)
    db.commit()

    # CREATE JWT
    token = create_access_token({
        "sub": str(userData.id),
        "session_id": session_id
    })

    return {
        "message": "registration successfull",
        "access_token": token,
        "token_type": "bearer"
    }


@router.post("/login")
def login(
    data: UserLogin,
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(
        User.username == data.username
    ).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    # TEMPORARY PASSWORD CHECK
    # later replace with bcrypt verify
    if user.password_hash != data.password:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    # GENERATE SESSION ID
    session_id = str(uuid.uuid4())

    # SESSION EXPIRY
    expires_at = datetime.utcnow() + timedelta(minutes=30)

    # CREATE SESSION ENTRY
    session = UserSession(
        user_id=user.id,
        session_id=session_id,
        expires_at=expires_at
    )

    db.add(session)
    db.commit()

    # CREATE JWT
    token = create_access_token({
        "sub": str(user.id),
        "session_id": session_id
    })

    return {
        "access_token": token,
        "token_type": "bearer"
    }



@router.post("/logout")
def logout(

    current_user: User = Depends(get_current_user),

    credentials:
    HTTPAuthorizationCredentials = Depends(security),

    db: Session = Depends(get_db)

):

    token = credentials.credentials

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        session_id = payload.get("session_id")

        if not session_id:

            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )

    except JWTError:

        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )

    session = db.query(UserSession).filter(
        UserSession.session_id == session_id,
        UserSession.is_active == True
    ).first()

    if not session:

        raise HTTPException(
            status_code=401,
            detail="Session already inactive"
        )

    session.is_active = False

    db.commit()

    return {
        "message": "Logged out successfully"
    }





@router.get("/labels")
def get_labels(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db)
):

    labels = db.query(Label).filter(
        Label.user_id == current_user.id
    ).all()

    return labels



@router.post("/labels")
def create_label(data: CreateLabel,current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):

    label = Label(
        user_id=current_user.id,
        label_name=data.label_name
    )

    db.add(label)
    db.commit()
    db.refresh(label)

    return {
        "message": "Label created",
        "label": label
    }



@router.patch("/labels")
def update_label(
    data: UpdateLabel,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)

):

    label = db.query(Label).filter(
        Label.id == data.id,
        Label.user_id == current_user.id
    ).first()

    if not label:
        raise HTTPException(
            status_code=404,
            detail="Label not found"
        )

    label.label_name = data.label_name
    db.commit()
    db.refresh(label)
    return {
        "message": "Label updated",
        "label": label
    }



@router.post("/learning-items")
async def create_learning_item(

    title: str = Form(...),
    description_text: str = Form(...),
    labels: str = Form(...),
    images: List[UploadFile] = File([]),
    pdfs: List[UploadFile] = File([]),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)

):

    label_ids = json.loads(labels)

    learning_item = LearningItem(
        user_id=current_user.id,
        title=title,
        description_text=description_text,
        theory=None
    )

    db.add(learning_item)

    db.commit()

    db.refresh(learning_item)

    for label_id in label_ids:

        relation = LearningItemLabel(
            learning_item_id=learning_item.id,
            label_id=label_id
        )

        db.add(relation)

    for image in images:

        uploaded = upload_file(
            image.file,
            resource_type="image"
        )

        media = Media(
            learning_item_id=learning_item.id,
            type="image",
            url=uploaded["url"],
            public_id=uploaded["public_id"]
        )

        db.add(media)

    for pdf in pdfs:

        uploaded = upload_file(
            pdf.file,
            resource_type="raw"
        )

        media = Media(
            learning_item_id=learning_item.id,
            type="pdf",
            url=uploaded["url"],
            public_id=uploaded["public_id"]
        )

        db.add(media)

    db.commit()

    return {
        "message": "Learning item created"
    }


@router.delete("/learning-items")
async def delete_learning_item(
    data: deleteLearningItem,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    log = db.query(LearningItem).filter(LearningItem.id == data.id).first()
    db.delete(log)
    db.commit()


@router.get(
    "/dashboard/summary",
    response_model=DashboardSummaryResponse
)
def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # TOTAL LEARNING ITEMS

    total_items = db.query(
        LearningItem
    ).filter(
        LearningItem.user_id == current_user.id
    ).count()

    # TOTAL LABELS

    total_labels = db.query(
        Label
    ).filter(
        Label.user_id == current_user.id
    ).count()

    # LOGIN STREAK
    # TEMPORARY SIMPLE VERSION

    login_sessions = db.query(
        UserSession
    ).filter(
        UserSession.user_id == current_user.id
    ).order_by(
        UserSession.created_at.desc()
    ).all()

    unique_days = set()

    for session in login_sessions:

        if session.created_at:

            unique_days.add(
                session.created_at.date()
            )

    login_streak = len(unique_days)

    return {
        "username": current_user.username,
        "total_items": total_items,
        "total_labels": total_labels,
        "login_streak": login_streak
    }
    



@router.get(
    "/dashboard/learning-items-summary",
    response_model=LearningItemsSummaryResponse
)
def get_learning_items_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    learning_items = db.query(

        LearningItem.id,
        LearningItem.title,
        LearningItem.description_text,
        func.group_concat(
            distinct(Label.label_name)
        ).label("labels"),

        func.group_concat(
            case(
                (
                    Media.type == "image",
                    Media.url
                ),
                else_=None
            )
        ).label("image_urls"),

        func.min(
            case(
                (
                    Media.type == "image",
                    Media.url
                ),
                else_=None
            )
        ).label("first_image_url"),

        func.count(

            distinct(
                case(
                    (
                        Media.type == "image",
                        Media.id
                    ),
                    else_=None
                )
            )

        ).label("image_count"),

        func.count(
            distinct(
                case(
                    (
                        Media.type == "pdf",
                        Media.id
                    ),
                    else_=None
                )
            )

        ).label("pdf_count"),
        func.timestampdiff(
            text("HOUR"),
            LearningItem.created_at,
            func.now()
        ).label("hours_ago")
    ).outerjoin(
        LearningItemLabel,
        LearningItem.id == LearningItemLabel.learning_item_id
    ).outerjoin(
        Label,
        LearningItemLabel.label_id == Label.id

    ).outerjoin(

        Media,
        LearningItem.id == Media.learning_item_id
    ).filter(
        LearningItem.user_id == current_user.id
    ).group_by(
        LearningItem.id
    ).all()

    formatted_learning_items = []

    for item in learning_items:
        formatted_learning_items.append({

            "id": item.id,
            "title": item.title,
            "description_text": item.description_text,
            "labels": item.labels,
            "image_urls": item.image_urls,
            "first_image_url": item.first_image_url,
            "image_count": item.image_count,
            "pdf_count": item.pdf_count,
            "hours_ago": item.hours_ago

        })

    return {

        "message": "Learning items summary returned successfully",
        "data": formatted_learning_items

    }



@router.get(
    "/learning-item/{item_id}",
    response_model=LearningItemViewResponse
)
def get_learning_item(
    item_id: int,
    # current_user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    learning_item = db.query(

        LearningItem.id,
        LearningItem.title,
        LearningItem.description_text,
        func.group_concat(
            distinct(Label.label_name)
        ).label("labels"),

        func.group_concat(
            case(
                (
                    Media.type == "image",
                    Media.url
                ),
                else_=None
            )
        ).label("image_urls"),

        func.group_concat(
            case(
                (
                    Media.type == "pdf",
                    Media.url
                ),
                else_=None
            )
        ).label("pdf_urls"),

        func.min(
            case(
                (
                    Media.type == "image",
                    Media.url
                ),
                else_=None
            )
        ).label("first_image_url"),

        func.count(

            distinct(
                case(
                    (
                        Media.type == "image",
                        Media.id
                    ),
                    else_=None
                )
            )

        ).label("image_count"),

        func.count(
            distinct(
                case(
                    (
                        Media.type == "pdf",
                        Media.id
                    ),
                    else_=None
                )
            )
        ).label("pdf_count"),
        func.timestampdiff(
            text("HOUR"),
            LearningItem.created_at,
            func.now()
        ).label("hours_ago"),

        LearningItem.theory,
        LearningItem.created_at,
        LearningItem.updated_at

    ).outerjoin(
        LearningItemLabel,
        LearningItem.id == LearningItemLabel.learning_item_id
    ).outerjoin(
        Label,
        LearningItemLabel.label_id == Label.id

    ).outerjoin(

        Media,
        LearningItem.id == Media.learning_item_id
    ).filter(
        LearningItem.user_id == current_user.id,
        # LearningItem.user_id == current_user_id,
        LearningItem.id == item_id

    ).group_by(
        LearningItem.id
    ).first()


    return {
        "message": "Learning item data fetched successfully",
        "data": learning_item
    }
    



@router.post(
    "/generate"
)
async def generate_revision(
    request: GenerateRevisionRequest
):
    result = await generate_revision_content(
        title=request.title,
        description=request.description
    )

    
    print(result["theory"])
    for point in result["key_points"]:
        print(point)

    # return {"result":result}
    return result