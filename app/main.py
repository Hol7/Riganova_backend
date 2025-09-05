from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.database.database import engine, get_db
from app.routes import auth, deliveries, users
from app.routes import websockets
from app.models.models import User, Delivery, DeliveryStatus

# Les tables sont créées par Alembic

# Créer l'application FastAPI
app = FastAPI(
    title="API Livraison Moto",
    description="API pour l'application de livraison à moto",
    version="1.0.0"
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production, spécifier les domaines autorisés
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclure les routeurs
app.include_router(auth.router)
app.include_router(deliveries.router)
app.include_router(users.router)
app.include_router(websockets.router)

@app.get("/")
def read_root():
    """Route de base pour vérifier que l'API fonctionne"""
    return {"message": "API Livraison Moto - Fonctionnelle ✅"}

@app.get("/health")
def health_check():
    """Vérification de santé de l'API"""
    return {"status": "healthy", "service": "livraison-api"}

# Route pour obtenir les statistiques (Admin/Manager)
@app.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """Obtenir des statistiques de base"""
    total_users = db.query(User).count()
    total_deliveries = db.query(Delivery).count()
    pending_deliveries = db.query(Delivery).filter(
        Delivery.statut == DeliveryStatus.EN_ATTENTE
    ).count()
    
    return {
        "total_users": total_users,
        "total_deliveries": total_deliveries,
        "pending_deliveries": pending_deliveries
    }