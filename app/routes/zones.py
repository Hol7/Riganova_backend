from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.auth.auth import get_current_user, get_admin_user
from app.models.models import User
from app.models.zone import DeliveryZone
from app.models import UserRole
from app.schemas.schemas import ZoneCreate, ZoneUpdate, Zone

router = APIRouter(prefix="/zones", tags=["zones"])

@router.post("/", response_model=Zone)
def create_zone(
    zone: ZoneCreate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Create a new delivery zone (Admin only)"""
    db_zone = DeliveryZone(**zone.dict())
    db.add(db_zone)
    db.commit()
    db.refresh(db_zone)
    return db_zone

@router.get("/", response_model=list[Zone])
def list_zones(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all active delivery zones"""
    zones = db.query(DeliveryZone).filter(DeliveryZone.is_active == True).all()
    return zones

@router.get("/public", response_model=list[Zone])
def list_zones_public(
    db: Session = Depends(get_db)
):
    """Public endpoint: list all active delivery zones without authentication"""
    zones = db.query(DeliveryZone).filter(DeliveryZone.is_active == True).all()
    return zones

@router.get("/{zone_id}", response_model=Zone)
def get_zone(
    zone_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get specific zone details"""
    zone = db.query(DeliveryZone).filter(DeliveryZone.id == zone_id).first()
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone introuvable"
        )
    return zone

@router.put("/{zone_id}", response_model=Zone)
def update_zone(
    zone_id: int,
    zone_update: ZoneUpdate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Update delivery zone (Admin only)"""
    zone = db.query(DeliveryZone).filter(DeliveryZone.id == zone_id).first()
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone introuvable"
        )
    
    update_data = zone_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(zone, field, value)
    
    db.commit()
    db.refresh(zone)
    return zone

@router.delete("/{zone_id}")
def delete_zone(
    zone_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Soft delete delivery zone (Admin only)"""
    zone = db.query(DeliveryZone).filter(DeliveryZone.id == zone_id).first()
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone introuvable"
        )
    
    zone.is_active = False
    db.commit()
    return {"message": "Zone supprimée avec succès"}
