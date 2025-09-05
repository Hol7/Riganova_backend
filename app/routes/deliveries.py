from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.dependencies.dependencies import get_current_user, require_roles
from app.models.models import User, Delivery
from app.models import UserRole, DeliveryStatus, DeliveryType
from app.schemas.schemas import DeliveryCreate, DeliveryUpdate, DeliveryAssign, Delivery as DeliverySchema

router = APIRouter(prefix="/deliveries", tags=["deliveries"])

@router.post("/create", response_model=DeliverySchema)
def create_delivery(
    payload: DeliveryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.CLIENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seuls les clients peuvent créer une demande",
        )

    delivery = Delivery(
        type_colis=payload.type_colis,
        description=payload.description,
        adresse_pickup=payload.adresse_pickup,
        adresse_dropoff=payload.adresse_dropoff,
        client_id=current_user.id,
        statut=DeliveryStatus.EN_ATTENTE,
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    return delivery

@router.post("/{delivery_id}/assign")
def assign_delivery(
    delivery_id: int,
    assign: DeliveryAssign,
    db: Session = Depends(get_db),
    manager: User = Depends(
        require_roles([UserRole.MANAGER, UserRole.ADMIN])
    ),
):
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if not delivery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Livraison introuvable"
        )

    livreur = (
        db.query(User)
        .filter(
            User.id == assign.livreur_id,
            User.role == UserRole.LIVREUR,
        )
        .first()
    )
    if not livreur:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Livreur invalide"
        )

    delivery.livreur_id = livreur.id
    delivery.statut = DeliveryStatus.EN_ROUTE_PICKUP
    db.commit()
    db.refresh(delivery)
    return {"message": "Course assignée", "delivery_id": delivery.id}

@router.post("/{delivery_id}/status", response_model=DeliverySchema)
def update_status(
    delivery_id: int,
    update: DeliverySchemaUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if not delivery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Livraison introuvable"
        )

    # Permissions: assigned courier or manager/admin
    is_assigned_courier = (
        current_user.role == UserRole.LIVREUR
        and delivery.livreur_id == current_user.id
    )
    is_manager = current_user.role in [UserRole.MANAGER, UserRole.ADMIN]
    if not (is_assigned_courier or is_manager):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé"
        )

    delivery.statut = update.statut
    db.commit()
    db.refresh(delivery)
    return delivery

@router.get("/history", response_model=list[DeliverySchema])
def get_history(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    if current_user.role == UserRole.CLIENT:
        deliveries = (
            db.query(Delivery)
            .filter(Delivery.client_id == current_user.id)
            .all()
        )
    elif current_user.role == UserRole.LIVREUR:
        deliveries = (
            db.query(Delivery)
            .filter(Delivery.livreur_id == current_user.id)
            .all()
        )
    elif current_user.role in [UserRole.MANAGER, UserRole.ADMIN]:
        deliveries = db.query(Delivery).all()
    else:
        deliveries = []
    return deliveries
