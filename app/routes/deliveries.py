from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.dependencies.dependencies import get_current_user, require_roles
from app.models.models import User, Delivery
from app.models import UserRole, DeliveryStatus, DeliveryType
from app.schemas.schemas import DeliveryCreate, DeliveryUpdate, DeliveryAssign, Delivery as DeliverySchema
from app.routes.websockets import manager

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
    # Broadcast assignment
    import asyncio
    from app.routes.websockets import manager as websocket_manager
    asyncio.create_task(websocket_manager.broadcast({
        "type": "assigned",
        "delivery_id": delivery.id,
        "livreur_id": livreur.id,
        "status": delivery.statut.value
    }))
    return {"message": "Course assignée", "delivery_id": delivery.id}

@router.post("/{delivery_id}/status", response_model=DeliverySchema)
def update_status(
    delivery_id: int,
    update: DeliveryUpdate,
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
    # Broadcast status update
    import asyncio
    from app.routes.websockets import manager as websocket_manager
    asyncio.create_task(websocket_manager.broadcast({
        "type": "status_update",
        "delivery_id": delivery.id,
        "status": delivery.statut.value
    }))
    return delivery

@router.get("/my-deliveries", response_model=list[DeliverySchema])
def get_my_deliveries(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Get deliveries for current client"""
    if current_user.role != UserRole.CLIENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seuls les clients peuvent voir leurs livraisons"
        )
    
    deliveries = (
        db.query(Delivery)
        .filter(Delivery.client_id == current_user.id)
        .order_by(Delivery.created_at.desc())
        .all()
    )
    return deliveries

@router.post("/{delivery_id}/cancel")
def cancel_delivery(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cancel delivery if not yet assigned"""
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if not delivery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Livraison introuvable"
        )
    
    # Only client who created it can cancel
    if delivery.client_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous ne pouvez annuler que vos propres livraisons"
        )
    
    # Can only cancel if not assigned yet
    if delivery.livreur_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible d'annuler une livraison déjà assignée"
        )
    
    delivery.statut = DeliveryStatus.ANNULE
    db.commit()
    
    # Broadcast cancellation
    import asyncio
    from app.routes.websockets import manager as websocket_manager
    asyncio.create_task(websocket_manager.broadcast({
        "type": "cancelled",
        "delivery_id": delivery.id,
        "status": delivery.statut.value
    }))
    
    return {"message": "Livraison annulée avec succès"}

@router.get("/{delivery_id}/status")
def get_delivery_status(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get real-time status of specific delivery"""
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if not delivery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Livraison introuvable"
        )
    
    # Check permissions
    is_client = current_user.role == UserRole.CLIENT and delivery.client_id == current_user.id
    is_livreur = current_user.role == UserRole.LIVREUR and delivery.livreur_id == current_user.id
    is_manager = current_user.role in [UserRole.MANAGER, UserRole.ADMIN]
    
    if not (is_client or is_livreur or is_manager):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé"
        )
    
    return {
        "delivery_id": delivery.id,
        "status": delivery.statut.value,
        "updated_at": delivery.updated_at
    }

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
