from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from src.settings import settings
from google.genai import types

import json

from sqlalchemy.orm import Session
from src.db import get_db
from src.model import User, UserSession
from src.schema import GeneratedRevisionResponse, GeneratedQuestion
import cloudinary.uploader

from src.google_config import client
from src.prompts.revision_prompt import build_revision_prompt


security = HTTPBearer()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
TIME_LIMIT = settings.ACCESS_TOKEN_EXPIRE_MINUTES

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=TIME_LIMIT)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str = Depends(oauth2_scheme)):
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    username = payload.get("sub")

    if username is None:
        raise HTTPException(status_code=401)

    return username


def upload_file(file, resource_type="auto"):

    result = cloudinary.uploader.upload(
        file,
        resource_type=resource_type
    )

    return {
        "url": result["secure_url"],
        "public_id": result["public_id"]
    }


def get_current_user(

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

        # username = payload.get("sub")
        user_id = payload.get("sub")

        session_id = payload.get("session_id")

        if not user_id or not session_id:

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
            detail="Session expired or logged out"
        )

    # CHECK SESSION EXPIRY

    if (
        session.expires_at and
        session.expires_at < datetime.utcnow()
    ):

        session.is_active = False

        db.commit()

        raise HTTPException(
            status_code=401,
            detail="Session expired"
        )

    # OPTIONAL:
    # update last activity timestamp

    session.last_used_at = datetime.utcnow()

    db.commit()

    # FIND USER

    user = db.query(User).filter(
        User.id == int(user_id)
    ).first()

    if not user:

        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return user



async def generate_revision_content(
    title: str,
    description: str
):
    prompt = build_revision_prompt(
        title,
        description
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            thinking_config=types.ThinkingConfig(
                thinking_budget=256
            )
        )
    )


    data = json.loads(response.text)
    print(data)
    return data