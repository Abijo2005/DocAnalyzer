from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.auth.dependencies import get_current_active_user
from app.auth.security import create_access_token, get_password_hash, verify_password
from app.core.logging_config import auth_logger
from app.database.session import get_db
from app.models.models import User
from app.schemas import schemas

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_in: schemas.UserCreate, db: Session = Depends(get_db)) -> User:
    """Registers a new user after verifying the email doesn't already exist."""
    existing_user = db.query(User).filter(User.email == user_in.email).first()
    if existing_user:
        auth_logger.warning(f"Registration failed: Email {user_in.email} already exists")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email is already registered",
        )

    hashed_password = get_password_hash(user_in.password)
    new_user = User(
        email=user_in.email,
        hashed_password=hashed_password,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    auth_logger.info(f"Successfully registered user: email={new_user.email}, id={new_user.id}")
    return new_user


@router.post("/login", response_model=schemas.Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
) -> dict:
    """Standard OAuth2 form login. Validates credentials and returns JWT token."""
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        auth_logger.warning(f"Login failed: invalid credentials for email {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        auth_logger.warning(f"Login rejected: user id {user.id} is inactive")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Subject of JWT token contains user's primary key ID
    access_token = create_access_token(data={"sub": str(user.id)})
    auth_logger.info(f"Successful login: email={user.email}, id={user.id}")
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=schemas.UserResponse)
def read_users_me(current_user: User = Depends(get_current_active_user)) -> User:
    """Returns the profile schema for the authenticated current user."""
    return current_user
