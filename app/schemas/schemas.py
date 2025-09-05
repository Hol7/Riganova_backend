from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from app.models import UserRole, DeliveryStatus, DeliveryType

# Schémas pour l'authentification
class UserCreate(BaseModel):
    nom: str
    email: EmailStr
    telephone: str
    mot_de_passe: str
    adresse: Optional[str] = None
    role: UserRole

class UserLogin(BaseModel):
    telephone: str
    mot_de_passe: str

class User(BaseModel):
    id: int
    nom: str
    email: str
    telephone: str
    adresse: Optional[str]
    role: UserRole
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    user: User

# Schémas pour les livraisons
class DeliveryCreate(BaseModel):
    type_colis: DeliveryType
    description: Optional[str] = None
    adresse_pickup: str
    adresse_dropoff: str

class DeliveryUpdate(BaseModel):
    statut: DeliveryStatus

class DeliveryAssign(BaseModel):
    livreur_id: int

class Delivery(BaseModel):
    id: int
    type_colis: DeliveryType
    description: Optional[str]
    adresse_pickup: str
    adresse_dropoff: str
    statut: DeliveryStatus
    prix: int
    client_id: int
    livreur_id: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class DeliveryWithUsers(Delivery):
    client: User
    livreur: Optional[User] = None
