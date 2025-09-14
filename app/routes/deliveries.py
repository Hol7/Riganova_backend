from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.dependencies.dependencies import get_current_user, require_roles
from app.models.models import User, Delivery
from app.models import UserRole, DeliveryStatus, DeliveryType
from app.schemas.schemas import DeliveryCreate, DeliveryUpdate, DeliveryAssign, Delivery as DeliverySchema, DeliveryWithClientInfo
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
    
    # Broadcast new delivery creation
    try:
        from app.routes.websockets import manager as websocket_manager
        import asyncio
        import threading
        
        def broadcast_in_background():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(websocket_manager.broadcast({
                    "type": "new_delivery",
                    "delivery_id": delivery.id,
                    "client_id": delivery.client_id,
                    "client_nom": current_user.nom,
                    "client_telephone": current_user.telephone,
                    "type_colis": delivery.type_colis.value,
                    "adresse_pickup": delivery.adresse_pickup,
                    "adresse_dropoff": delivery.adresse_dropoff,
                    "status": delivery.statut.value,
                    "created_at": delivery.created_at.isoformat()
                }))
                loop.close()
            except Exception as e:
                print(f"WebSocket broadcast error: {e}")
        
        thread = threading.Thread(target=broadcast_in_background)
        thread.daemon = True
        thread.start()
    except Exception as e:
        print(f"WebSocket setup error: {e}")
    
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
    try:
        from app.routes.websockets import manager as websocket_manager
        import asyncio
        import threading
        
        def broadcast_in_background():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(websocket_manager.broadcast({
                    "type": "assigned",
                    "delivery_id": delivery.id,
                    "livreur_id": livreur.id,
                    "status": delivery.statut.value
                }))
                loop.close()
            except Exception as e:
                print(f"WebSocket broadcast error: {e}")
        
        thread = threading.Thread(target=broadcast_in_background)
        thread.daemon = True
        thread.start()
    except Exception as e:
        print(f"WebSocket setup error: {e}")
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
    try:
        from app.routes.websockets import manager as websocket_manager
        import asyncio
        import threading
        
        def broadcast_in_background():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(websocket_manager.broadcast({
                    "type": "status_update",
                    "delivery_id": delivery.id,
                    "status": delivery.statut.value
                }))
                loop.close()
            except Exception as e:
                print(f"WebSocket broadcast error: {e}")
        
        thread = threading.Thread(target=broadcast_in_background)
        thread.daemon = True
        thread.start()
    except Exception as e:
        print(f"WebSocket setup error: {e}")
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
    """Cancel delivery - clients can cancel unassigned deliveries, managers/admins can cancel any delivery"""
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if not delivery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Livraison introuvable"
        )
    
    # Check if delivery is already cancelled or delivered
    if delivery.statut in [DeliveryStatus.ANNULE, DeliveryStatus.LIVRE]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible d'annuler une livraison déjà terminée"
        )
    
    # Permission checks
    is_client_owner = current_user.role == UserRole.CLIENT and delivery.client_id == current_user.id
    is_manager_admin = current_user.role in [UserRole.MANAGER, UserRole.ADMIN]
    
    if not (is_client_owner or is_manager_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé"
        )
    
    # Clients can only cancel unassigned deliveries, managers/admins can cancel any
    if current_user.role == UserRole.CLIENT and delivery.livreur_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible d'annuler une livraison déjà assignée. Contactez un manager."
        )
    
    delivery.statut = DeliveryStatus.ANNULE
    db.commit()
    
    # Broadcast cancellation
    try:
        from app.routes.websockets import manager as websocket_manager
        import asyncio
        import threading
        
        def broadcast_in_background():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(websocket_manager.broadcast({
                    "type": "cancelled",
                    "delivery_id": delivery.id,
                    "status": delivery.statut.value
                }))
                loop.close()
            except Exception as e:
                print(f"WebSocket broadcast error: {e}")
        
        thread = threading.Thread(target=broadcast_in_background)
        thread.daemon = True
        thread.start()
    except Exception as e:
        print(f"WebSocket setup error: {e}")
    
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

@router.get("/", response_model=list[DeliveryWithClientInfo])
def get_deliveries(
    db: Session = Depends(get_db),
    manager: User = Depends(require_roles([UserRole.MANAGER, UserRole.ADMIN]))
):
    """Get all deliveries with client and livreur contact info"""
    deliveries = (
        db.query(
            Delivery.id,
            Delivery.type_colis,
            Delivery.description,
            Delivery.adresse_pickup,
            Delivery.adresse_dropoff,
            Delivery.statut,
            Delivery.prix,
            Delivery.client_id,
            User.nom.label('client_nom'),
            User.telephone.label('client_telephone'),
            Delivery.livreur_id,
            Delivery.created_at,
            Delivery.updated_at
        )
        .join(User, Delivery.client_id == User.id)
        .all()
    )
    
    result = []
    for delivery in deliveries:
        # Get livreur info if exists
        livreur_nom = None
        livreur_telephone = None
        if delivery.livreur_id:
            livreur = db.query(User).filter(User.id == delivery.livreur_id).first()
            if livreur:
                livreur_nom = livreur.nom
                livreur_telephone = livreur.telephone
        
        result.append(DeliveryWithClientInfo(
            id=delivery.id,
            type_colis=delivery.type_colis,
            description=delivery.description,
            adresse_pickup=delivery.adresse_pickup,
            adresse_dropoff=delivery.adresse_dropoff,
            statut=delivery.statut,
            prix=delivery.prix,
            client_id=delivery.client_id,
            client_nom=delivery.client_nom,
            client_telephone=delivery.client_telephone,
            livreur_id=delivery.livreur_id,
            livreur_nom=livreur_nom,
            livreur_telephone=livreur_telephone,
            created_at=delivery.created_at,
            updated_at=delivery.updated_at
        ))
    
    return result

@router.get("/history", response_model=list[DeliveryWithClientInfo])
def get_history(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Get delivery history with client and livreur contact info"""
    if current_user.role == UserRole.CLIENT:
        deliveries = (
            db.query(
                Delivery.id,
                Delivery.type_colis,
                Delivery.description,
                Delivery.adresse_pickup,
                Delivery.adresse_dropoff,
                Delivery.statut,
                Delivery.prix,
                Delivery.client_id,
                User.nom.label('client_nom'),
                User.telephone.label('client_telephone'),
                Delivery.livreur_id,
                Delivery.created_at,
                Delivery.updated_at
            )
            .join(User, Delivery.client_id == User.id)
            .filter(Delivery.client_id == current_user.id)
            .all()
        )
    elif current_user.role == UserRole.LIVREUR:
        deliveries = (
            db.query(
                Delivery.id,
                Delivery.type_colis,
                Delivery.description,
                Delivery.adresse_pickup,
                Delivery.adresse_dropoff,
                Delivery.statut,
                Delivery.prix,
                Delivery.client_id,
                User.nom.label('client_nom'),
                User.telephone.label('client_telephone'),
                Delivery.livreur_id,
                Delivery.created_at,
                Delivery.updated_at
            )
            .join(User, Delivery.client_id == User.id)
            .filter(Delivery.livreur_id == current_user.id)
            .all()
        )
    elif current_user.role in [UserRole.MANAGER, UserRole.ADMIN]:
        deliveries = (
            db.query(
                Delivery.id,
                Delivery.type_colis,
                Delivery.description,
                Delivery.adresse_pickup,
                Delivery.adresse_dropoff,
                Delivery.statut,
                Delivery.prix,
                Delivery.client_id,
                User.nom.label('client_nom'),
                User.telephone.label('client_telephone'),
                Delivery.livreur_id,
                Delivery.created_at,
                Delivery.updated_at
            )
            .join(User, Delivery.client_id == User.id)
            .all()
        )
    else:
        deliveries = []
    
    result = []
    for delivery in deliveries:
        # Get livreur info if exists
        livreur_nom = None
        livreur_telephone = None
        if delivery.livreur_id:
            livreur = db.query(User).filter(User.id == delivery.livreur_id).first()
            if livreur:
                livreur_nom = livreur.nom
                livreur_telephone = livreur.telephone
        
        result.append(DeliveryWithClientInfo(
            id=delivery.id,
            type_colis=delivery.type_colis,
            description=delivery.description,
            adresse_pickup=delivery.adresse_pickup,
            adresse_dropoff=delivery.adresse_dropoff,
            statut=delivery.statut,
            prix=delivery.prix,
            client_id=delivery.client_id,
            client_nom=delivery.client_nom,
            client_telephone=delivery.client_telephone,
            livreur_id=delivery.livreur_id,
            livreur_nom=livreur_nom,
            livreur_telephone=livreur_telephone,
            created_at=delivery.created_at,
            updated_at=delivery.updated_at
        ))
    
    return result
