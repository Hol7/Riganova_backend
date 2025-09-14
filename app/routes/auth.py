from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.auth.auth import verify_password, get_password_hash, create_access_token
from app.models.models import User
from app.models import UserRole
from app.schemas.schemas import UserCreate, UserLogin, User as UserSchema, Token
from app.services.email_services import email_service
import asyncio

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserSchema)
def register(user: UserCreate, db: Session = Depends(get_db)):
    """Créer un nouveau compte utilisateur"""
    
    # Vérifier si l'email existe déjà
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cet email est déjà utilisé"
        )
    
    # Vérifier si le téléphone existe déjà
    db_user = db.query(User).filter(User.telephone == user.telephone).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce numéro de téléphone est déjà utilisé"
        )
    
    # Créer le nouvel utilisateur
    hashed_password = get_password_hash(user.mot_de_passe)
    db_user = User(
        nom=user.nom,
        email=user.email,
        telephone=user.telephone,
        mot_de_passe=hashed_password,
        adresse=user.adresse,
        role=user.role
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Envoyer email de bienvenue en arrière-plan
    try:
        asyncio.create_task(email_service.send_welcome_email(
            email=db_user.email,
            nom=db_user.nom,
            telephone=db_user.telephone
        ))
    except Exception as e:
        print(f"Erreur envoi email bienvenue: {e}")
    
    return db_user

@router.post("/token", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """OAuth2 compatible token endpoint for Swagger UI"""
    from app.auth.auth import authenticate_user
    
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Téléphone ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": str(user.id)})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@router.post("/login", response_model=Token)
def login(user_credentials: UserLogin, db: Session = Depends(get_db)):
    """Connexion utilisateur"""
    
    # Trouver l'utilisateur par téléphone
    user = db.query(User).filter(User.telephone == user_credentials.telephone).first()
    
    if not user or not verify_password(user_credentials.mot_de_passe, user.mot_de_passe):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Téléphone ou mot de passe incorrect"
        )
    
    # Créer le token d'accès
    access_token = create_access_token(data={"sub": str(user.id)})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@router.post("/forget-password")
async def forget_password(email: str, db: Session = Depends(get_db)):
    """Réinitialiser le mot de passe"""
    
    # Trouver l'utilisateur par email
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun compte trouvé avec cet email"
        )
    
    # Générer un nouveau mot de passe temporaire
    import secrets
    import string
    new_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))
    
    # Mettre à jour le mot de passe
    user.mot_de_passe = get_password_hash(new_password)
    db.commit()
    
    # Envoyer l'email avec le nouveau mot de passe
    try:
        await email_service.send_password_reset_email(email, new_password)
        return {"message": "Nouveau mot de passe envoyé par email"}
    except Exception as e:
        # En cas d'erreur email, on peut quand même retourner le mot de passe
        # (à des fins de test, en production on ne ferait pas ça)
        return {
            "message": "Erreur envoi email, voici votre nouveau mot de passe temporaire",
            "temporary_password": new_password
        }