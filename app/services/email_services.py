import httpx
import os
from fastapi import HTTPException, status
import asyncio

class EmailService:
    def __init__(self):
        self.brevo_api_key = os.environ.get("BREVO_API_KEY", "")
        self.brevo_api_url = "https://api.brevo.com/v3/smtp/email"
        
        if not self.brevo_api_key:
            raise ValueError("BREVO_API_KEY n'est pas définie dans les variables d'environnement")
    
    async def send_welcome_email(self, email: str, nom: str, telephone: str):
        """Envoyer un email de bienvenue après inscription"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.brevo_api_url,
                    json={
                        "to": [{"email": email, "name": nom}],
                        "templateId": 1,  # Remplacez par votre template ID Brevo
                        "params": {
                            "nom": nom,
                            "telephone": telephone
                        }
                    },
                    headers={
                        "api-key": self.brevo_api_key,
                        "content-type": "application/json",
                        "accept": "application/json"
                    }
                )
                
                if response.status_code not in [200, 201]:
                    print(f"Erreur envoi email: {response.text}")
                    
        except Exception as error:
            print(f"Erreur envoi email: {error}")
            # Ne pas faire échouer l'inscription si l'email ne part pas
    
    async def send_password_reset_email(self, email: str, new_password: str):
        """Envoyer un email de réinitialisation de mot de passe"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.brevo_api_url,
                    json={
                        "to": [{"email": email}],
                        "templateId": 6,  # Remplacez par votre template ID Brevo
                        "params": {
                            "password": new_password
                        }
                    },
                    headers={
                        "api-key": self.brevo_api_key,
                        "content-type": "application/json",
                        "accept": "application/json"
                    }
                )
                
                if response.status_code not in [200, 201]:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Erreur lors de l'envoi de l'email"
                    )
                    
        except HTTPException:
            raise
        except Exception as error:
            print(f"Erreur envoi email reset: {error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de l'envoi de l'email de réinitialisation"
            )

# Instance globale du service email
email_service = EmailService()