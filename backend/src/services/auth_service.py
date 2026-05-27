"""
Authentication service for handling user login,
registration, and Google OAuth callback.
"""
import base64
import datetime
import secrets
from typing import Optional
import uuid
import logging
import traceback



import requests
from fastapi import HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..api.schemas import auth as auth_schema
from ..api.schemas import user as user_schema
from ..config import settings as settings
from ..core import security
from ..core.security import oauth
from ..db.crud import users_crud
from ..db.models.db_user import User as UserModel
from ..db.crud import usage_crud
from ..db.database import USE_FIRESTORE


logger = logging.getLogger(__name__)


class DictToObj:
    """Wrap a dict to allow attribute access, for Firestore compatibility."""
    def __init__(self, d):
        for k, v in d.items():
            super().__setattr__(k, v)
    
    def __setattr__(self, name, value):
        super().__setattr__(name, value)

async def login_user(form_data: OAuth2PasswordRequestForm, db: Session, response: Response) -> auth_schema.APIResponseStatus:
    """Authenticates a user and returns an access token."""
    if not form_data.username or not form_data.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Username and password are required")

    now = datetime.datetime.now(datetime.timezone.utc)

    if USE_FIRESTORE:
        user_data = db.get_user_by_username(form_data.username)
        if not user_data:
            user_data = db.get_user_by_email(form_data.username)
        if not user_data or not security.verify_password(form_data.password, user_data['hashed_password']):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Incorrect username or password")
        if not user_data.get('is_active'):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Inactive user")
        user = DictToObj(user_data)
        previous_last_login = user.last_login
        db.update_user(str(user.id), {'last_login': now})
        db.create_usage_log(str(user.id), 'login')
        access_token = security.create_access_token(
            data={"sub": user.username, "user_id": user.id,
                  "is_admin": user.is_admin, "email": user.email}
        )
        refresh_token = security.create_refresh_token(
            data={"sub": user.username, "user_id": user.id,
                  "is_admin": user.is_admin, "email": user.email}
        )
        security.set_access_cookie(response, access_token)
        security.set_refresh_cookie(response, refresh_token)
        return auth_schema.APIResponseStatus(
            status="success", msg="Successfully logged in",
            data={"last_login": previous_last_login.isoformat() if previous_last_login else None}
        )

    # Check if the user exists and verify the password
    user = users_crud.get_user_by_username(db, form_data.username)
    if not user:
        user = users_crud.get_user_by_email(db, form_data.username)

    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Incorrect username or password")
    if not user.is_active: # type: ignore
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Inactive user")

    # Generate access token with user details
    access_token = security.create_access_token(
        data={"sub": user.username,
              "user_id": user.id,
              "is_admin": user.is_admin,
              "email": user.email}
    )

    refresh_token = security.create_refresh_token(
        data={"sub": user.username,
              "user_id": user.id,
              "is_admin": user.is_admin,
              "email": user.email}
    )

    # Save last login time
    previous_last_login = user.last_login
    users_crud.update_user_last_login(db, user_id=str(user.id))
    # Log the user login action
    usage_crud.log_login(db, user_id=str(user.id))

    # Set the access token in the response cookie
    security.set_access_cookie(response, access_token)
    # Set the refresh token in the response cookie
    security.set_refresh_cookie(response, refresh_token)

    return auth_schema.APIResponseStatus(status="success",
                                         msg="Successfully logged in",
                                         data={ "last_login": previous_last_login.isoformat()})

async def admin_login_as(current_user_id: str, user_id: str, db: Session, response: Response) -> auth_schema.APIResponseStatus:
    """
    Logs in as a specified user (admin only).
    
    Args:
        user_id: The ID of the user to log in as
        db: Database session
        response: FastAPI response object for setting cookies
        
    Returns:
        APIResponseStatus with login status
        
    Raises:
        HTTPException: If user not found or not active
    """
    if USE_FIRESTORE:
        user_data = db.get_user_by_id(user_id)
        if not user_data:
            logger.warning("Attempted to log in as non-existent user ID: %s", user_id)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        user = DictToObj(user_data)
        if user.is_admin:
            logger.warning("Attempted to log in as admin user: %s (ID: %s)", user.username, user.id)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Cannot log in as another admin user")
        logger.info("Admin login-as action: Admin ID: %s is logging in as user: %s (ID: %s)",
                    current_user_id, user.username, user.id)
        previous_last_login = user.last_login
        db.create_usage_log(str(user.id), 'admin_login_as', details=f"Admin {current_user_id} logged in as user {user.id}")
        access_token = security.create_access_token(
            data={"sub": user.username, "user_id": user.id,
                  "is_admin": user.is_admin, "email": user.email}
        )
        refresh_token = security.create_refresh_token(
            data={"sub": user.username, "user_id": user.id,
                  "is_admin": user.is_admin, "email": user.email}
        )
        security.set_access_cookie(response, access_token)
        security.set_refresh_cookie(response, refresh_token)
        return auth_schema.APIResponseStatus(
            status="success", msg="Successfully logged in as user",
            data={"last_login": previous_last_login.isoformat() if previous_last_login else None}
        )

    # Get the target user
    user = users_crud.get_user_by_id(db, user_id)
    if not user:
        logger.warning("Attempted to log in as non-existent user ID: %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
        
    # Check if the target user is active
    if user.is_admin:
        logger.warning("Attempted to log in as admin user: %s (ID: %s)", user.username, user.id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot log in as another admin user"
        )
        
    # Log the admin action
    logger.info(
        "Admin login-as action: Admin ID: %s is logging in as user: %s (ID: %s)",
        current_user_id, user.username, user.id
    )

    # Generate access token with user details
    access_token = security.create_access_token(
        data={
            "sub": user.username,
            "user_id": user.id,
            "is_admin": user.is_admin,
            "email": user.email
        }
    )

    refresh_token = security.create_refresh_token(
        data={
            "sub": user.username,
            "user_id": user.id,
            "is_admin": user.is_admin,
            "email": user.email
        }
    )

    # Set the access and refresh tokens in the response cookies
    security.set_access_cookie(response, access_token)
    security.set_refresh_cookie(response, refresh_token)
    
    # Update last login time
    previous_last_login = user.last_login
    # No update on last login!
    usage_crud.log_admin_login_as(db, user_who=current_user_id, user_as=str(user.id))

    return auth_schema.APIResponseStatus(
        status="success",
        msg="Successfully logged in as user",
        data={"last_login": previous_last_login.isoformat() if previous_last_login else None}
    )



async def register_user(user_data: user_schema.UserCreate, db: Session, response: Response) -> auth_schema.APIResponseStatus:
    """Registers a new user and returns the created user data."""
    
    now = datetime.datetime.now(datetime.timezone.utc)

    if USE_FIRESTORE:
        if db.get_user_by_username(user_data.username):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
        if db.get_user_by_email(user_data.email):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
        user_id = str(uuid.uuid4())
        while db.get_user_by_id(user_id):
            user_id = str(uuid.uuid4())
        hashed_password = security.get_password_hash(user_data.password)
        new_user_dict = {
            'id': user_id,
            'username': user_data.username,
            'email': user_data.email,
            'hashed_password': hashed_password,
            'is_active': True,
            'is_admin': False,
            'profile_image_base64': user_data.profile_image_base64,
            'created_at': now,
            'updated_at': now,
            'last_login': now,
        }
        db.create_user(new_user_dict, doc_id=user_id)
        new_user = DictToObj(new_user_dict)
        access_token = security.create_access_token(
            data={"sub": new_user.username, "user_id": new_user.id,
                  "is_admin": False, "email": new_user.email}
        )
        refresh_token = security.create_refresh_token(
            data={"sub": new_user.username, "user_id": new_user.id,
                  "is_admin": False, "email": new_user.email}
        )
        security.set_access_cookie(response, access_token)
        security.set_refresh_cookie(response, refresh_token)
        return auth_schema.APIResponseStatus(status="success", msg="Successfully logged in")
    
    # Check if username from incoming data (user_data.username) already exists in the DB
    db_user_by_username = users_crud.get_user_by_username(db, user_data.username)
    if db_user_by_username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")

    # Check if email from incoming data (user_data.email) already exists in the DB
    db_user_by_email = users_crud.get_user_by_email(db, user_data.email)
    if db_user_by_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    # Generate a unique string ID
    user_id = None
    while True:
        user_id = str(uuid.uuid4())
        if not users_crud.get_user_by_id(db, user_id):
            break
    
    # Create the user in the database
    # When a user is registered, created_at and last_login are set by default in the model
    new_user = users_crud.create_user(
        db = db,
        user_id = user_id,
        username = user_data.username,
        email = user_data.email,
        hashed_password = security.get_password_hash(user_data.password),
        profile_image_base64 = user_data.profile_image_base64,
    )

    # Set access cookie
    access_token = security.create_access_token(
        data={"sub": new_user.username,
              "user_id": new_user.id,
              "is_admin": False,
              "email": new_user.email}
    )

    # Set the access token in the response cookie
    refresh_token = security.create_refresh_token(
        data={"sub": new_user.username,
              "user_id": new_user.id,
              "is_admin": False,
              "email": new_user.email}
    )

    # Set the access token in the response cookie
    security.set_access_cookie(response, access_token)
    # Set the refresh token in the response cookie
    security.set_refresh_cookie(response, refresh_token)

    return auth_schema.APIResponseStatus(status="success",
                                        msg="Successfully logged in")



async def logout_user(user: user_schema.User, db: Session, response: Response) -> auth_schema.APIResponseStatus:
    """Logs out a user by clearing the access and refresh tokens."""
    
    # Clear the access token cookie
    security.clear_access_cookie(response)
    # Clear the refresh token cookie
    security.clear_refresh_cookie(response)

    if USE_FIRESTORE:
        db.create_usage_log(str(user.id), 'logout')
    else:
        usage_crud.log_logout(db, user_id=str(user.id))

    return auth_schema.APIResponseStatus(status="success", msg="Successfully logged out")
    
async def refresh_token(token: Optional[str], db: Session, response: Response) -> auth_schema.APIResponseStatus:
    """Registers a new user and returns the created user data."""
    
    # Verify the token and extract user ID
    user_id = security.verify_token(token)

    if USE_FIRESTORE:
        user_data = db.get_user_by_id(user_id)
        if not user_data or not user_data.get('is_active'):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Could not validate refresh token")
        user = DictToObj(user_data)
        access_token = security.create_access_token(
            data={"sub": user.username, "user_id": user.id,
                  "is_admin": user.is_admin, "email": user.email}
        )
        db.create_usage_log(str(user.id), 'refresh')
        security.set_access_cookie(response, access_token)
        return auth_schema.APIResponseStatus(status="success", msg="")

    # Fetch the user from the database using the user ID
    user = users_crud.get_active_user_by_id(db, user_id)

    if user is None:
        raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
    )

    access_token = security.create_access_token(
        data={"sub": user.username,
              "user_id": user.id,
              "is_admin": user.is_admin,
              "email": user.email}
    )
    # Log the user refresh action
    usage_crud.log_refresh(db, user_id=str(user.id))

    # Set the access token in the response cookie
    security.set_access_cookie(response, access_token)

    return auth_schema.APIResponseStatus(status="success", msg="")



async def handle_oauth_callback(request: Request, db: Session, website: str = "google"):
    """Handles the callback from OAuth after user authentication."""

    # Get the OAuth client
    oauth_client = getattr(oauth, website, None)

    if not oauth_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=website + "OAuth client is not configured."
        )

    # Authorize access token from 

    try:
        token = await oauth_client.authorize_access_token(request)
    except Exception as error:
        logger.error("OAuth callback error for %s: %s", website, traceback.format_exc())
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Could not validate credentials") from error

    # Fetch user info from the token
    if website == "github":
        # GitHub: fetch user info using the access token
        access_token = token.get("access_token")
        headers = {"Authorization": f"token {access_token}"}
        user_response = requests.get("https://api.github.com/user", headers=headers, timeout=10)
        user_response.raise_for_status()
        user_info = user_response.json()
        # Fetch email separately if not public
        email = user_info.get("email")
        if not email:
            emails_response = requests.get("https://api.github.com/user/emails", headers=headers, timeout=10)
            emails_response.raise_for_status()
            emails = emails_response.json()
            primary_emails = [e["email"] for e in emails if e.get("primary") and e.get("verified")]
            email = primary_emails[0] if primary_emails else None
        name = user_info.get("name") or user_info.get("login")
        picture_url = user_info.get("avatar_url")
    elif website == "google":
        user_info = token.get('userinfo')
        if not user_info or not user_info.get("email"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Could not fetch user info from {website}.")
        email = user_info["email"]
        name = user_info.get("name")
        picture_url = user_info.get("picture")
    elif website == "discord":
        access_token = token.get("access_token")
        headers = {"Authorization": f"Bearer {access_token}"}
        user_response = requests.get("https://discord.com/api/users/@me", headers=headers, timeout=10)
        user_response.raise_for_status()
        user_info = user_response.json()
        email = user_info.get("email")
        name = user_info.get("username")
        # Discord avatar URL construction
        avatar = user_info.get("avatar")
        user_id = user_info.get("id")
        if avatar and user_id:
            picture_url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar}.png"
        else:
            picture_url = None
        if not email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Could not fetch user info from {website}.")
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Unsupported OAuth provider: {website}")

    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Could not fetch user email from {website}.")

    now = datetime.datetime.now(datetime.timezone.utc)
    profile_image_base64_data = None
    if picture_url:
        try:
            response = requests.get(picture_url, timeout=10)
            response.raise_for_status()
            profile_image_base64_data = base64.b64encode(response.content).decode('utf-8')
        except requests.exceptions.RequestException:
            profile_image_base64_data = None

    if USE_FIRESTORE:
        db_user_data = db.get_user_by_email(email)
        if db_user_data:
            db_user = DictToObj(db_user_data)
        else:
            logger.info("Creating new user for %s OAuth login: %s (%s)", website, email, name)
            base_username = (name.lower().replace(" ", ".")[:40] if name else (email.split("@")[0][:40] if email else "user"))
            username_candidate = base_username[:42]
            final_username = username_candidate
            while db.get_user_by_username(final_username):
                suffix = secrets.token_hex(3)
                final_username = f"{username_candidate[:42]}.{suffix}"
            hashed_password = security.get_password_hash(secrets.token_urlsafe(16))
            new_id = secrets.token_hex(16)
            new_user = {
                'id': new_id,
                'username': final_username,
                'email': email,
                'hashed_password': hashed_password,
                'is_active': True,
                'is_admin': False,
                'profile_image_base64': profile_image_base64_data,
                'oauth_provider': website,
                'oauth_id': email,
                'created_at': now,
                'updated_at': now,
                'last_login': now,
                'login_streak': 1,
            }
            db.create_user(new_user, doc_id=new_id)
            db_user = DictToObj(new_user)

        if not db_user.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="User is inactive.")

        if profile_image_base64_data and getattr(db_user, 'profile_image_base64', None) != profile_image_base64_data:
            db.update_user(str(db_user.id), {'profile_image_base64': profile_image_base64_data})

        db.update_user(str(db_user.id), {'last_login': now})
        db.create_usage_log(str(db_user.id), 'login')

        access_token = security.create_access_token(
            data={"sub": db_user.username, "user_id": db_user.id,
                  "is_admin": db_user.is_admin, "email": db_user.email}
        )
        refresh_token = security.create_refresh_token(
            data={"sub": db_user.username, "user_id": db_user.id,
                  "is_admin": db_user.is_admin, "email": db_user.email}
        )
    else:
        db_user = db.query(UserModel).filter(UserModel.email == email).first()

        if not db_user:
            logger.info("Creating new user for %s OAuth login: %s (%s)", website, email, name)
            base_username = (name.lower().replace(" ", ".")[:40] if name else (email.split("@")[0][:40] if email else "user"))
            username_candidate = base_username[:42]
            final_username = username_candidate
            while db.query(UserModel).filter(UserModel.username == final_username).first():
                suffix = secrets.token_hex(3)
                final_username = f"{username_candidate[:42]}.{suffix}"
            hashed_password = security.get_password_hash(secrets.token_urlsafe(16))
            db_user = users_crud.create_user(db, secrets.token_hex(16), final_username, email,
                                             hashed_password, is_active=True, is_admin=False,
                                             profile_image_base64=profile_image_base64_data)
        else:
            logger.info("Using existing user %s from database for %s OAuth login.", db_user.username, website)
            if profile_image_base64_data and getattr(db_user, 'profile_image_base64', None) != profile_image_base64_data:
                users_crud.update_user_profile_image(db, db_user, profile_image_base64_data)

        if not db_user or not db_user.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="User is inactive.")

        users_crud.update_user_last_login(db, user_id=str(db_user.id))
        usage_crud.log_login(db, user_id=str(db_user.id))

        access_token = security.create_access_token(
            data={"sub": db_user.username, "user_id": db_user.id,
                  "is_admin": db_user.is_admin, "email": db_user.email}
        )
        refresh_token = security.create_refresh_token(
            data={"sub": db_user.username, "user_id": db_user.id,
                  "is_admin": db_user.is_admin, "email": db_user.email}
        )

    # Redirect to the frontend OAuth callback page (use dynamic host if behind proxy)
    original_host = request.headers.get("X-Original-Host")
    if original_host:
        scheme = request.headers.get("X-Original-Proto", "https")
        frontend_base_url = f"{scheme}://{original_host}"
    else:
        frontend_base_url = settings.FRONTEND_BASE_URL
    if not frontend_base_url:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Frontend base URL is not configured.")

    from ..core.security import _cookie_params
    cp = _cookie_params()
    logger.info("OAuth cookie params: %s", cp)

    redirect_url = f"{frontend_base_url}/oauth/callback?access_token={access_token}"
    logger.info("OAuth callback redirect URL: %s", redirect_url)

    response = RedirectResponse(url=redirect_url, status_code=302)
    response.set_cookie(
        key="access_token",
        value=access_token,
        path="/",
        httponly=True,
        **cp,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        path="/",
        httponly=True,
        **cp,
    )

    # Also set non-httponly flag cookie so frontend can detect auth state
    response.set_cookie(
        key="authenticated",
        value="true",
        path="/",
        httponly=False,
        **cp,
    )

    return response

