from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.dependencies.dependencies import get_current_user, require_roles
from app.models.models import User, Delivery
from app.models import UserRole, DeliveryStatus
from app.schemas.schemas import DeliveryWithClientInfo
from typing import List
import json

router = APIRouter(prefix="/webhook", tags=["webhooks"])

# Store webhook URLs for external services
webhook_subscribers = {
    "delivery_created": [],
    "delivery_assigned": [],
    "delivery_status_changed": [],
    "delivery_cancelled": []
}

@router.post("/deliveries/subscribe")
def subscribe_to_delivery_webhooks(
    webhook_url: str,
    events: List[str],
    current_user: User = Depends(require_roles([UserRole.MANAGER, UserRole.ADMIN]))
):
    """Subscribe to delivery webhook events"""
    import re
    
    valid_events = ["delivery_created", "delivery_assigned", "delivery_status_changed", "delivery_cancelled"]
    
    # Validate webhook URL format
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    if not url_pattern.match(webhook_url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook URL format. Must be a valid HTTP/HTTPS URL (localhost allowed for development)"
        )
    
    for event in events:
        if event not in valid_events:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid event: {event}. Valid events: {valid_events}"
            )
        
        if webhook_url not in webhook_subscribers[event]:
            webhook_subscribers[event].append(webhook_url)
    
    return {
        "message": "Successfully subscribed to webhook events",
        "webhook_url": webhook_url,
        "events": events,
        "note": "localhost URLs are supported for development. Use production URLs when deployed."
    }

@router.get("/deliveries/subscribers")
def get_webhook_subscribers(
    current_user: User = Depends(require_roles([UserRole.MANAGER, UserRole.ADMIN]))
):
    """Get all webhook subscribers"""
    return webhook_subscribers

@router.delete("/deliveries/unsubscribe")
def unsubscribe_from_delivery_webhooks(
    webhook_url: str,
    events: List[str] = None,
    current_user: User = Depends(require_roles([UserRole.MANAGER, UserRole.ADMIN]))
):
    """Unsubscribe from delivery webhook events"""
    if events is None:
        # Remove from all events
        for event_list in webhook_subscribers.values():
            if webhook_url in event_list:
                event_list.remove(webhook_url)
    else:
        # Remove from specific events
        for event in events:
            if event in webhook_subscribers and webhook_url in webhook_subscribers[event]:
                webhook_subscribers[event].remove(webhook_url)
    
    return {
        "message": "Successfully unsubscribed from webhook events",
        "webhook_url": webhook_url
    }

@router.get("/deliveries/events")
def get_recent_delivery_events(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.MANAGER, UserRole.ADMIN]))
):
    """Get recent delivery events for webhook testing"""
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
        .order_by(Delivery.created_at.desc())
        .limit(limit)
        .all()
    )
    
    events = []
    for delivery in deliveries:
        # Get livreur info if exists
        livreur_nom = None
        livreur_telephone = None
        if delivery.livreur_id:
            livreur = db.query(User).filter(User.id == delivery.livreur_id).first()
            if livreur:
                livreur_nom = livreur.nom
                livreur_telephone = livreur.telephone
        
        event = {
            "type": "delivery_created",
            "delivery_id": delivery.id,
            "client_id": delivery.client_id,
            "client_nom": delivery.client_nom,
            "client_telephone": delivery.client_telephone,
            "livreur_id": delivery.livreur_id,
            "livreur_nom": livreur_nom,
            "livreur_telephone": livreur_telephone,
            "type_colis": delivery.type_colis.value,
            "adresse_pickup": delivery.adresse_pickup,
            "adresse_dropoff": delivery.adresse_dropoff,
            "status": delivery.statut.value,
            "prix": delivery.prix,
            "created_at": delivery.created_at.isoformat(),
            "updated_at": delivery.updated_at.isoformat() if delivery.updated_at else None
        }
        events.append(event)
    
    return {
        "events": events,
        "total": len(events)
    }

# Webhook utility function to send HTTP requests
async def send_webhook_notification(event_type: str, data: dict):
    """Send webhook notification to all subscribers"""
    import httpx
    import asyncio
    
    if event_type not in webhook_subscribers:
        return
    
    urls = webhook_subscribers[event_type]
    if not urls:
        return
    
    async def send_to_url(url: str):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    json={
                        "event": event_type,
                        "timestamp": data.get("created_at", ""),
                        "data": data
                    },
                    headers={"Content-Type": "application/json"}
                )
                print(f"Webhook sent to {url}: {response.status_code}")
        except Exception as e:
            print(f"Failed to send webhook to {url}: {e}")
    
    # Send to all URLs concurrently
    tasks = [send_to_url(url) for url in urls]
    await asyncio.gather(*tasks, return_exceptions=True)
