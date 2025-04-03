from twilio.rest import Client
from ..config import get_settings
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        self.from_number = settings.TWILIO_PHONE_NUMBER
        self.admin_number = settings.ADMIN_PHONE_NUMBER

    async def send_waste_report_alert(self, report_data: dict) -> bool:
        """
        Send SMS alert to admin about a new waste report
        
        Args:
            report_data: The waste report data
            
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        try:
            # Format the message
            severity = report_data.get("severity", "Unknown")
            location = report_data.get("location", "Unknown location")
            description = report_data.get("description", "No description provided")
            waste_types = report_data.get("waste_types", "Unknown types")
            
            message = (
                f"🚨 New Waste Report Alert!\n\n"
                f"Severity: {severity}\n"
                f"Location: {location}\n"
                f"Description: {description}\n"
                f"Waste Types: {waste_types}\n\n"
                f"Please check the dashboard for details."
            )
            
            # Send the message
            self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=self.admin_number
            )
            
            logger.info(f"Successfully sent SMS alert to admin for waste report at {location}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send SMS alert: {str(e)}")
            return False

# Create a singleton instance
notification_service = NotificationService() 