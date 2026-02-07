from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import timedelta
import asyncpg
import logging

from app.db.database import get_connection
from app.users.models import User
from app.users.schemas import UserCreate, UserOut, Token, UserResponse, TokenResponse
from app.users import service as user_service
from app.core.security import create_access_token, verify_token
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/token")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    conn: asyncpg.Connection = Depends(get_connection)
) -> User:
    """Dependency to get the current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    username = verify_token(token)
    if username is None:
        raise credentials_exception
    
    # Use service layer to get user
    user = await user_service.get_user_by_username(conn, username)
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    return user


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    conn: asyncpg.Connection = Depends(get_connection)
):
    """Register a new user."""
    logger.info(f"Registration attempt for username: {user_data.username}")
    try:
        user = await user_service.create_user(
            conn=conn,
            username=user_data.username,
            password=user_data.password
        )
        logger.info(f"Registration successful for username: {user_data.username}, user_id: {user.id}")
        return {
            "status": "success",
            "message": "User registered successfully",
            "data": user
        }
    except ValueError as e:
        logger.warning(f"Registration failed for username: {user_data.username} - {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
                "data": None
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error during registration for username: {user_data.username} - {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "An error occurred during registration",
                "data": None
            }
        )


@router.post("/token", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    conn: asyncpg.Connection = Depends(get_connection)
):
    """Login and get JWT token."""
    user = await user_service.authenticate_user(
        conn=conn,
        username=form_data.username,
        password=form_data.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "message": "Incorrect username or password",
                "data": None
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    return {
        "status": "success",
        "message": "Login successful",
        "data": {
            "access_token": access_token,
            "token_type": "bearer"
        }
    }


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return {
        "status": "success",
        "message": "User retrieved successfully",
        "data": current_user
    }
