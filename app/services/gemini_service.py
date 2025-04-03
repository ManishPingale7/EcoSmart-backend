import os
import base64
import httpx
from datetime import datetime
from typing import Dict, Any, Optional
from app.config import get_settings
import io
try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    print("WARNING: Pillow library not available. Image resizing disabled.")

settings = get_settings()

def resize_image_base64(base64_image: str, max_size: int = 1024, quality: int = 85) -> str:
    """
    Resize a base64-encoded image to optimize it for API requests
    
    Args:
        base64_image: Base64 encoded image string
        max_size: Maximum width/height in pixels
        quality: JPEG quality (0-100)
        
    Returns:
        Resized image as base64 string
    """
    if not PILLOW_AVAILABLE:
        print("Pillow not available, skipping image resize")
        return base64_image
        
    try:
        # Decode base64 image
        image_data = base64.b64decode(base64_image)
        image = Image.open(io.BytesIO(image_data))
        
        # Get original size
        width, height = image.size
        original_size_kb = len(image_data) / 1024
        
        # Only resize if the image is larger than max_size
        if width > max_size or height > max_size:
            # Calculate new dimensions
            if width > height:
                new_width = max_size
                new_height = int(height * (max_size / width))
            else:
                new_height = max_size
                new_width = int(width * (max_size / height))
                
            # Resize the image
            image = image.resize((new_width, new_height), Image.LANCZOS)
            
            # Convert back to base64
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=quality)
            resized_data = output.getvalue()
            resized_base64 = base64.b64encode(resized_data).decode('utf-8')
            
            # Log the size reduction
            resized_size_kb = len(resized_data) / 1024
            reduction_percent = ((original_size_kb - resized_size_kb) / original_size_kb) * 100
            print(f"Resized image from {width}x{height} to {new_width}x{new_height}")
            print(f"Size reduced from {original_size_kb:.2f}KB to {resized_size_kb:.2f}KB ({reduction_percent:.1f}% reduction)")
            
            return resized_base64
        else:
            print(f"Image already smaller than {max_size}px, no resize needed")
            return base64_image
    except Exception as e:
        print(f"Error resizing image: {str(e)}")
        # Return original if resize fails
        return base64_image

async def validate_waste_image(
    image: str,  # Base64 encoded image
    description: Optional[str],
    location: str,
    timestamp: datetime,
    optimize_image: bool = True  # New parameter to control optimization
) -> Dict[str, Any]:
    """
    Validate a waste image using Google's Gemini API
    
    Args:
        image: Base64 encoded image
        description: Optional description of the waste
        location: Location where the image was taken
        timestamp: When the image was taken
        optimize_image: Whether to resize large images for better performance
        
    Returns:
        Dict containing validation results
    """
    # Ensure the image is properly formatted for Gemini
    if "base64," in image:
        # Extract the actual base64 content if it includes the data URL prefix
        image = image.split("base64,")[1]
    
    # Check image size - Gemini has limits
    image_size_bytes = len(image)
    image_size_mb = image_size_bytes / (1024 * 1024)
    print(f"Image size: {image_size_mb:.2f} MB ({image_size_bytes} bytes)")
    
    # Optimize image if it's large and optimization is enabled
    if optimize_image and image_size_mb > 1.0 and PILLOW_AVAILABLE:
        print("Image larger than 1MB, attempting to optimize...")
        try:
            # Calculate max size based on image size to preserve detail
            # when possible while still reducing very large images
            if image_size_mb > 4.0:
                max_size = 1024  # Aggressive reduction for very large images
            elif image_size_mb > 2.0:
                max_size = 1536  # Medium reduction
            else:
                max_size = 2048  # Light reduction for slightly large images
                
            # Resize the image
            image = resize_image_base64(image, max_size=max_size)
            
            # Check new size
            new_size_bytes = len(image)
            new_size_mb = new_size_bytes / (1024 * 1024)
            print(f"Optimized image size: {new_size_mb:.2f} MB ({new_size_bytes} bytes)")
        except Exception as e:
            print(f"Error optimizing image: {str(e)}")
    
    # Warn if image is too large (Gemini usually has a limit around 20MB)
    if image_size_mb > 10:
        print(f"WARNING: Image size ({image_size_mb:.2f} MB) may be too large for Gemini API")
    
    # Validate image base64 content
    try:
        # Check if the image can be decoded
        decoded_image = base64.b64decode(image)
        print(f"Successfully decoded base64 image, size: {len(decoded_image)} bytes")
    except Exception as e:
        print(f"ERROR: Invalid base64 image data: {str(e)}")
        return {
            "is_valid": False,
            "message": f"Error with image data: Invalid base64 encoding - {str(e)}",
            "confidence_score": 0,
            "waste_types": [],
            "severity": None,
            "dustbins": [],
            "recyclable_items": [],
            "time_analysis": {},
            "description_match": {},
            "additional_data": {"error": f"Invalid base64 image: {str(e)}"}
        }
    
    # Check for API key issues
    if not settings.GOOGLE_API_KEY or settings.GOOGLE_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        print("ERROR: No valid GOOGLE_API_KEY found in your .env file!")
        return {
            "is_valid": False,
            "message": "Configuration error: Missing or invalid Gemini API key",
            "confidence_score": 0,
            "waste_types": [],
            "severity": "Clean",
            "dustbins": [],
            "recyclable_items": [],
            "time_analysis": {},
            "description_match": {},
            "additional_data": {
                "error": "Please add a valid GOOGLE_API_KEY to your .env file. Get one from https://ai.google.dev/",
                "help": "After getting your API key, restart the server for changes to take effect."
            }
        }
    
    # Construct the prompt for Gemini
    prompt = f"""
    Analyze this image of a potentially dirty/unclean area. 
    
    Additional context:
    - Location: {location}
    - Time taken: {timestamp.isoformat()}
    - Description: {description or 'No description provided'}
    
    Instructions:
    1. Is this image clearly showing a dirty or unclean area? Answer yes only if dustbins are overflowing or there is significant waste outside designated areas.
    2. Calculate a confidence score (0-100) based on image clarity, time, and location. Be conservative with high scores.
    3. Identify specific waste types visible in the image as comma-separated values.
    4. Categorize the severity of the waste/dirt into one of these levels:
       - "Clean" (0-25%): Properly maintained dustbins, minimal or no litter outside bins
       - "Low" (26-50%): Some litter but mostly contained, dustbins not overflowing
       - "Medium" (51-75%): Noticeable waste outside containers, but pathways clear
       - "High" (76-90%): Significant waste, some pathways affected
       - "Critical" (91-100%): Major public health concern, completely blocked pathways
    5. Identify if there are any dustbins present in the image. If yes, determine if they are full or empty, and estimate what percentage they are full (0-100%).
    6. Check if there is any waste visible outside of dustbins and describe it.
    7. Analyze the recyclability of the waste visible in the image. Identify which items could be recycled.
    8. Validate if the image time makes sense (e.g., if it appears to be a night scene but timestamp suggests daytime, flag it).
    9. Consider the provided description and assess if it matches what's visible in the image.
    
    RESPOND ONLY WITH VALID JSON. Do not include any explanations, markdown formatting, or code blocks. Return just the raw JSON.
    
    Your response MUST follow this exact JSON schema:
    {{
        "is_valid": true/false,
        "message": "Your analysis summary here",
        "confidence_score": 0-100,
        "waste_types": [
            {{ "type": "waste type name", "confidence": 0.0-1.0 }},
            ...
        ],
        "severity": "Clean/Low/Medium/High/Critical",
        "dustbins": [
            {{
                "is_present": true/false,
                "is_full": true/false,
                "fullness_percentage": 0-100,
                "waste_outside": true/false,
                "waste_outside_description": "Description of waste outside bins"
            }}
        ],
        "recyclable_items": [
            {{ "item": "item name", "recyclable": true/false, "notes": "recycling notes" }}
        ],
        "time_analysis": {{
            "time_appears_valid": true/false,
            "lighting_condition": "day/night/indoor/unclear",
            "notes": "Any notes about time discrepancies"
        }},
        "description_match": {{
            "matches_image": true/false,
            "confidence": 0-100,
            "notes": "Notes about how well description matches the image"
        }},
        "additional_data": {{
            "key1": "value1",
            "key2": "value2"
        }}
    }}
    
    If the image is not of sufficient quality or does not show a dirty area, set is_valid to false and provide an appropriate message.
    """
    
    # Construct the request to Gemini
    model = "gemini-2.0-flash"
    api_url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": settings.GOOGLE_API_KEY
    }
    
    data = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": image
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "topK": 32,
            "topP": 0.95,
            "maxOutputTokens": 4096,
        }
    }
    
    # Print API key details for debugging (first 4 characters only)
    api_key_prefix = settings.GOOGLE_API_KEY[:4] if settings.GOOGLE_API_KEY else "None"
    print(f"Using Gemini API Key (prefix): {api_key_prefix}***")
    print(f"Using model: {model}")
    print(f"Sending request to URL: {api_url}")
    
    try:
        # Use a longer timeout for the API request (60 seconds instead of default)
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(api_url, json=data, headers=headers)
            
            # Check if the response is an error
            if response.status_code != 200:
                error_detail = f"Gemini API error: {response.status_code} - {response.text}"
                print(f"Error: {error_detail}")
                return {
                    "is_valid": False,
                    "message": f"Error from Gemini API: HTTP {response.status_code}",
                    "confidence_score": 0,
                    "waste_types": [],
                    "severity": None,
                    "dustbins": [],
                    "recyclable_items": [],
                    "time_analysis": {},
                    "description_match": {},
                    "additional_data": {"error": error_detail, "url": api_url}
                }
                
            response.raise_for_status()
            
            result = response.json()
            
            # Extract the text from the response
            response_text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
            
            # Print raw response for debugging
            print(f"Raw response from Gemini: {response_text[:200]}...")
            
            # Parse the JSON from the text response
            import json
            try:
                # Try to clean up the response if it's not proper JSON
                cleaned_text = response_text.strip()
                # If response starts with markdown code block, extract the content
                if cleaned_text.startswith("```json"):
                    cleaned_text = cleaned_text.split("```json", 1)[1]
                    if "```" in cleaned_text:
                        cleaned_text = cleaned_text.split("```", 1)[0]
                elif cleaned_text.startswith("```"):
                    cleaned_text = cleaned_text.split("```", 1)[1]
                    if "```" in cleaned_text:
                        cleaned_text = cleaned_text.split("```", 1)[0]
                
                cleaned_text = cleaned_text.strip()
                print(f"Cleaned text: {cleaned_text[:200]}...")
                
                validation_result = json.loads(cleaned_text)
                
                # Ensure the validation result has all required fields
                if "is_valid" not in validation_result:
                    validation_result["is_valid"] = True
                if "message" not in validation_result:
                    validation_result["message"] = "Analysis completed successfully"
                if "confidence_score" not in validation_result:
                    validation_result["confidence_score"] = 0
                if "waste_types" not in validation_result:
                    validation_result["waste_types"] = []
                if "severity" not in validation_result:
                    validation_result["severity"] = "Clean"
                if "dustbins" not in validation_result:
                    validation_result["dustbins"] = []
                if "recyclable_items" not in validation_result:
                    validation_result["recyclable_items"] = []
                if "time_analysis" not in validation_result:
                    validation_result["time_analysis"] = {}
                if "description_match" not in validation_result:
                    validation_result["description_match"] = {}
                if "additional_data" not in validation_result:
                    validation_result["additional_data"] = {}
                
                return validation_result
            except json.JSONDecodeError as e:
                # If Gemini didn't return valid JSON, try manual parsing
                print(f"Failed to parse JSON: {str(e)}")
                print(f"Attempting to manually extract information from response")
                
                # Very basic manual extraction
                manually_parsed = {
                    "is_valid": "yes" in response_text.lower(),
                    "message": "Manually extracted from non-JSON response",
                    "confidence_score": 50,  # Default score
                    "waste_types": [],
                    "severity": "Clean",  # Default to Clean instead of Unknown
                    "dustbins": [{
                        "is_present": "dustbin" in response_text.lower(),
                        "is_full": False,
                        "fullness_percentage": 0,
                        "waste_outside": False,
                        "waste_outside_description": ""
                    }],
                    "recyclable_items": [],
                    "time_analysis": {
                        "time_appears_valid": True,
                        "lighting_condition": "day/night/indoor/unclear",
                        "notes": ""
                    },
                    "description_match": {
                        "matches_image": True,
                        "confidence": 0,
                        "notes": ""
                    },
                    "additional_data": {
                        "raw_response": response_text[:500],
                        "note": "This response was manually parsed due to JSON parsing failure"
                    }
                }
                
                # Try to extract waste types
                if "waste type" in response_text.lower():
                    waste_section = response_text.lower().split("waste type", 1)[1]
                    if ":" in waste_section:
                        waste_types_text = waste_section.split(":", 1)[1].strip()
                        waste_types = [wt.strip() for wt in waste_types_text.split(",") if wt.strip()]
                        manually_parsed["waste_types"] = [{"type": wt, "confidence": 0.5} for wt in waste_types]
                
                # Try to extract severity
                for severity in ["clean", "low", "medium", "high", "critical"]:
                    if severity in response_text.lower():
                        manually_parsed["severity"] = severity.capitalize()
                        break
                
                print(f"Manually extracted data: {manually_parsed}")
                return manually_parsed
                
    except Exception as e:
        error_msg = str(e) if str(e) else "Unknown error occurred" 
        print(f"Error: {error_msg}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback_str = traceback.format_exc()
        print(f"Traceback: {traceback_str}")
        
        return {
            "is_valid": False,
            "message": f"Error validating image: {error_msg}",
            "confidence_score": 0,
            "waste_types": [],
            "severity": None,
            "dustbins": [],
            "recyclable_items": [],
            "time_analysis": {},
            "description_match": {},
            "additional_data": {
                "error": error_msg,
                "error_type": type(e).__name__,
                "traceback": traceback_str
            }
        } 