from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum

class UserRole(enum.Enum):
    CLIENT = "client"
    LIVREUR = "livreur"
    MANAGER = "manager"
    ADMIN = "admin"

class DeliveryStatus(enum.Enum):
    EN_ATTENTE = "en_attente"
    ASSIGNE = "assigne"
    EN_ROUTE_PICKUP = "en_route_pickup"
    ARRIVE_PICKUP = "arrive_pickup"
    COLIS_RECUPERE = "colis_recupere"
    EN_ROUTE_LIVRAISON = "en_route_livraison"
    LIVRE = "livre"
    ANNULE = "annule"

class DeliveryType(enum.Enum):
    DOCUMENT = "document"
    REPAS = "repas"
    COLIS = "colis"
    AUTRE = "autre"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    telephone = Column(String, unique=True, index=True, nullable=False)
    mot_de_passe = Column(String, nullable=False)
    adresse = Column(Text)
    role = Column(Enum(UserRole), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relations
    deliveries_client = relationship("Delivery", foreign_keys="Delivery.client_id", back_populates="client")
    deliveries_livreur = relationship("Delivery", foreign_keys="Delivery.livreur_id", back_populates="livreur")

class Delivery(Base):
    __tablename__ = "deliveries"

    id = Column(Integer, primary_key=True, index=True)
    type_colis = Column(Enum(DeliveryType), nullable=False)
    description = Column(Text)
    adresse_pickup = Column(Text, nullable=False)
    adresse_dropoff = Column(Text, nullable=False)
    statut = Column(Enum(DeliveryStatus), default=DeliveryStatus.EN_ATTENTE)
    prix = Column(Integer, default=0)  # Prix en centimes
    
    # Relations
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    livreur_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    client = relationship("User", foreign_keys=[client_id], back_populates="deliveries_client")
    livreur = relationship("User", foreign_keys=[livreur_id], back_populates="deliveries_livreur")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
