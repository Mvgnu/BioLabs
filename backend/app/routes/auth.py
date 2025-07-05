from fastapi import APIRouter, Depends, HTTPException, Request
import os
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import uuid
import pyotp
from ..database import get_db
from .. import models, schemas, notify, audit
from ..auth import get_password_hash, verify_password, create_access_token, get_current_user
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
testing = os.getenv("TESTING") == "1"

def rate_limit(limit: str):
    if testing:
        def wrapper(func):
            return func
        return wrapper
    return limiter.limit(limit)

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/register", response_model=schemas.Token)
@rate_limit("5/minute")
async def register(request: Request, user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    db_user = models.User(
        email=user.email,
        hashed_password=get_password_hash(user.password),
        full_name=user.full_name,
        phone_number=user.phone_number,
        orcid_id=user.orcid_id,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    audit.log_action(db, str(db_user.id), "register", "user", str(db_user.id))
    token = create_access_token({"sub": db_user.email})
    return schemas.Token(access_token=token)


@router.post("/request-password-reset")
async def request_password_reset(data: schemas.PasswordResetRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == data.email).first()
    if user:
        token = uuid.uuid4().hex
        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        db_token = models.PasswordResetToken(user_id=user.id, token=token, expires_at=expires)
        db.add(db_token)
        db.commit()
        notify.send_email(user.email, "Password Reset", f"Use this code to reset: {token}")
    return {"status": "sent"}


@router.post("/reset-password")
async def reset_password(data: schemas.PasswordResetConfirm, db: Session = Depends(get_db)):
    record = (
        db.query(models.PasswordResetToken)
        .filter(models.PasswordResetToken.token == data.token, models.PasswordResetToken.used == False)
        .first()
    )
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if not record or expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    user = db.get(models.User, record.user_id)
    user.hashed_password = get_password_hash(data.new_password)
    record.used = True
    db.add_all([user, record])
    db.commit()
    return {"status": "password updated"}


@router.post("/enable-2fa", response_model=schemas.TwoFactorEnableOut)
async def enable_two_factor(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    secret = pyotp.random_base32()
    current_user.two_factor_secret = secret
    db.add(current_user)
    db.commit()
    url = pyotp.totp.TOTP(secret).provisioning_uri(name=current_user.email, issuer_name="BioLabs")
    return schemas.TwoFactorEnableOut(secret=secret, otpauth_url=url)


@router.post("/verify-2fa")
async def verify_two_factor(
    data: schemas.TwoFactorVerifyIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not current_user.two_factor_secret:
        raise HTTPException(status_code=400, detail="2FA not initiated")
    totp = pyotp.TOTP(current_user.two_factor_secret)
    if not totp.verify(data.code, valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid code")
    current_user.two_factor_enabled = True
    db.add(current_user)
    db.commit()
    return {"status": "enabled"}

@router.post("/login", response_model=schemas.Token)
@rate_limit("10/minute")
async def login(request: Request, user: schemas.LoginRequest, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if db_user.two_factor_enabled:
        if not user.otp_code:
            raise HTTPException(status_code=401, detail="Two-factor code required")
        totp = pyotp.TOTP(db_user.two_factor_secret)
        if not totp.verify(user.otp_code, valid_window=1):
            raise HTTPException(status_code=401, detail="Invalid two-factor code")
    token = create_access_token({"sub": db_user.email})
    audit.log_action(db, str(db_user.id), "login", "user", str(db_user.id))
    return schemas.Token(access_token=token)
