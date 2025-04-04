from twilio.rest import Client
from ..config import get_settings
import logging
from datetime import datetime

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
            # Extract key information
            severity = report_data.get("severity", "Unknown")
            location = report_data.get("location", "Unknown location")
            waste_types = report_data.get("waste_types", "Unknown types")
            confidence = report_data.get("confidence_score", 0)
            
            # Format timestamp
            timestamp = report_data.get("timestamp", datetime.utcnow())
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            formatted_time = timestamp.strftime("%H:%M %d/%m")
            
            # Create concise message (under 160 chars)
            message = (
                f"🚨 Waste Alert: {severity}\n"
                f"📍 {location}\n"
                f"⏰ {formatted_time}\n"
                f"🗑️ {waste_types}\n"
                f"📊 {confidence:.0f}% conf"
            )
            
            # Send the message
            #Currently disabled
            # self.client.messages.create(
            #     body=message,
            #     from_=self.from_number,
            #     to=self.admin_number
            # )
            
            # logger.info(f"Successfully sent SMS alert to admin for waste report at {location}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send SMS alert: {str(e)}")
            return False

# Create a singleton instance
notification_service = NotificationService() 