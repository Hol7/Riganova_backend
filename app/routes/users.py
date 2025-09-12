from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.dependencies.dependencies import get_current_user, require_roles
from app.models.models import User
from app.models import UserRole
from app.schemas.schemas import User as UserSchema

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserSchema)
def read_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.get("/", response_model=list[UserSchema])
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles([UserRole.ADMIN])),
):
    return db.query(User).all()

@router.get("/clients", response_model=list[UserSchema])
def list_clients(
    db: Session = Depends(get_db),
    manager: User = Depends(require_roles([UserRole.MANAGER, UserRole.ADMIN]))
):
    """List all clients for assignment purposes"""
    clients = db.query(User).filter(User.role == UserRole.CLIENT).all()
    return clients

@router.get("/livreurs", response_model=list[UserSchema])
def list_livreurs(
    db: Session = Depends(get_db),
    manager: User = Depends(require_roles([UserRole.MANAGER, UserRole.ADMIN]))
):
    """List all livreurs for assignment purposes"""
    livreurs = db.query(User).filter(User.role == UserRole.LIVREUR).all()
    return livreurs

