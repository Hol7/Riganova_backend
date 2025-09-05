from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.auth.auth import get_current_user, get_current_active_user, get_admin_user
from app.models.models import User, UserRole

# Configuration du bearer token
security = HTTPBearer()


def require_role(required_role: UserRole):
    """Décorateur pour exiger un rôle spécifique"""
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accès refusé. Rôle requis: {required_role.value}"
            )
        return current_user
    return role_checker

def require_roles(required_roles: list):
    """Décorateur pour exiger un des rôles spécifiés"""
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in required_roles:
            roles_str = ", ".join([role.value for role in required_roles])
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accès refusé. Rôles autorisés: {roles_str}"
            )
        return current_user
    return role_checker
