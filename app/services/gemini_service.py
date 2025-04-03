import os
import base64
import httpx
from datetime import datetime
from typing import Dict, Any, Optional, List
from app.config import get_settings
from fastapi import HTTPException   
import io
import json
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
            "waste_types": {"types": "", "confidence": 0.0},
            "severity": "Clean",
            "dustbins": {
                "is_present": False,
                "is_full": False,
                "fullness_percentage": 0,
                "waste_outside": False,
                "waste_outside_description": ""
            },
            "recyclable_items": {
                "items": "",
                "recyclable": False,
                "notes": ""
            },
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
            "waste_types": {"types": "", "confidence": 0.0},
            "severity": "Clean",
            "dustbins": {
                "is_present": False,
                "is_full": False,
                "fullness_percentage": 0,
                "waste_outside": False,
                "waste_outside_description": ""
            },
            "recyclable_items": {
                "items": "",
                "recyclable": False,
                "notes": ""
            },
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
    3. Identify specific waste types visible in the image as comma-separated values, and provide confidence scores (0-1) for each type as comma-separated values.
    4. Categorize the severity of the waste/dirt into one of these levels:
       - "Clean" (0-25%): Properly maintained dustbins, minimal or no litter outside bins
       - "Low" (26-50%): Some litter but mostly contained, dustbins not overflowing
       - "Medium" (51-75%): Noticeable waste outside containers, but pathways clear
       - "High" (76-90%): Significant waste, some pathways affected
       - "Critical" (91-100%): Major public health concern, completely blocked pathways
    5. Identify if there are any dustbins present in the image. If yes, determine if they are full or empty, and estimate what percentage they are full (0-100%).
    6. Check if there is any waste visible outside of dustbins and describe it.
    7. Analyze the recyclability of the waste visible in the image. List recyclable items as comma-separated values.
    8. Validate if the image time makes sense (e.g., if it appears to be a night scene but timestamp suggests daytime, flag it).
    9. Consider the provided description and assess if it matches what's visible in the image.
    
    RESPOND ONLY WITH VALID JSON. Do not include any explanations, markdown formatting, or code blocks. Return just the raw JSON.
    
    Your response MUST follow this exact JSON schema:
    {{
        "is_valid": true/false,
        "message": "Your analysis summary here",
        "confidence_score": 0-100,
        "waste_types": {{
            "types": "waste type 1, waste type 2, waste type 3",
            "confidence": "0.8, 0.7, 0.9"  # Confidence scores matching each waste type
        }},
        "severity": "Clean/Low/Medium/High/Critical",
        "dustbins": {{
            "is_present": true/false,
            "is_full": true/false,
            "fullness_percentage": 0-100,
            "waste_outside": true/false,
            "waste_outside_description": "Description of waste outside bins"
        }},
        "recyclable_items": {{
            "items": "item 1, item 2, item 3",
            "recyclable": true/false,
            "notes": "recycling notes"
        }},
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
                    "waste_types": {"types": "", "confidence": 0.0},
                    "severity": "Clean",
                    "dustbins": {
                        "is_present": False,
                        "is_full": False,
                        "fullness_percentage": 0,
                        "waste_outside": False,
                        "waste_outside_description": ""
                    },
                    "recyclable_items": {
                        "items": "",
                        "recyclable": False,
                        "notes": ""
                    },
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
                    validation_result["waste_types"] = {"types": "", "confidence": ""}
                if "severity" not in validation_result:
                    validation_result["severity"] = "Clean"
                if "dustbins" not in validation_result:
                    validation_result["dustbins"] = {
                        "is_present": False,
                        "is_full": False,
                        "fullness_percentage": 0,
                        "waste_outside": False,
                        "waste_outside_description": ""
                    }
                if "recyclable_items" not in validation_result:
                    validation_result["recyclable_items"] = {
                        "items": "",
                        "recyclable": False,
                        "notes": ""
                    }
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
                    "waste_types": {"types": "", "confidence": 0.0},
                    "severity": "Clean",  # Default to Clean instead of Unknown
                    "dustbins": {
                        "is_present": "dustbin" in response_text.lower(),
                        "is_full": False,
                        "fullness_percentage": 0,
                        "waste_outside": False,
                        "waste_outside_description": ""
                    },
                    "recyclable_items": {
                        "items": "",
                        "recyclable": False,
                        "notes": ""
                    },
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
                        manually_parsed["waste_types"] = {"types": ", ".join(waste_types), "confidence": 0.5}
                
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
            "waste_types": {"types": "", "confidence": 0.0},
            "severity": "Clean",
            "dustbins": {
                "is_present": False,
                "is_full": False,
                "fullness_percentage": 0,
                "waste_outside": False,
                "waste_outside_description": ""
            },
            "recyclable_items": {
                "items": "",
                "recyclable": False,
                "notes": ""
            },
            "time_analysis": {},
            "description_match": {},
            "additional_data": {
                "error": error_msg,
                "error_type": type(e).__name__,
                "traceback": traceback_str
            }
        } 

async def compare_cleanup_images(before_image: str, after_image: str) -> dict:
    """
    Compare before and after images to verify cleanup with comprehensive AI-based validations.
    """
    try:
        print("\n=== Starting Image Comparison Process ===")
        print(f"Before image length: {len(before_image)}")
        print(f"After image length: {len(after_image)}")
        
        # Check if images are identical
        if before_image == after_image:
            print("✓ Detected identical images")
            return {
                "is_same_location": True,
                "is_clean": False,
                "improvement_percentage": 0,
                "verification_details": {
                    "location_confidence": 100,
                    "location_reasons": ["Identical images detected"],
                    "waste_analysis": {
                        "before_types": [],
                        "after_types": [],
                        "waste_removed": False,
                        "new_waste": False
                    },
                    "cleanup_quality": {
                        "is_thorough": False,
                        "remaining_issues": ["No cleanup performed - identical images"],
                        "sanitization_level": "poor"
                    },
                    "temporal_analysis": {
                        "is_recent": False,
                        "lighting_consistent": True,
                        "recent_activity": False
                    },
                    "overall_confidence": 100,
                    "notes": "Identical images detected - no cleanup performed"
                }
            }

        # Validate image formats
        try:
            # Check if images are valid base64
            before_decoded = base64.b64decode(before_image)
            after_decoded = base64.b64decode(after_image)
            print("✓ Both images are valid base64")
        except Exception as e:
            print(f"✗ Invalid base64 image: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid image format")

        # Prepare detailed prompt for Gemini
        print("\n=== Preparing Gemini Prompt ===")
        prompt = f"""
        Analyze these two images of a waste cleanup operation:
        1. Before image (showing waste/dirty area)
        2. After image (showing cleaned area)

        IMPORTANT LOCATION VERIFICATION RULES:
        1. Be VERY lenient with location matching
        2. Consider it the same location if ANY of these are true:
           - Same general area is visible
           - Any landmarks match (even partially)
           - Similar viewing angle
           - Similar lighting conditions
           - Same type of surface/ground
        3. Only mark as different location if COMPLETELY different area

        Perform the following validations:

        1. Location Verification (BE LENIENT):
           - Look for ANY matching features
           - Consider general area similarity
           - Check viewing angle (roughly similar is okay)
           - Verify lighting (similar is okay)
           - Look for ANY unique features in both

        2. Waste Detection and Analysis:
           - Identify types of waste in before image
           - Check if those specific waste items are gone in after image
           - Look for any new waste that might have appeared
           - Verify proper disposal (not just moved elsewhere)

        3. Cleanup Quality Assessment:
           - Check if cleaning was thorough
           - Look for any remaining traces of waste
           - Verify if the area is properly sanitized
           - Check for proper waste disposal methods

        4. Temporal Analysis:
           - Check if lighting conditions are consistent
           - Verify if the cleanup appears recent
           - Look for signs of recent cleaning activity

        Provide your analysis in this JSON format:
        {{
            "is_same_location": boolean,
            "location_match_confidence": number (0-100),
            "location_match_reasons": ["reason1", "reason2"],
            "waste_analysis": {{
                "before_waste_types": ["type1", "type2"],
                "after_waste_types": ["type1", "type2"],
                "waste_removed": boolean,
                "new_waste_detected": boolean
            }},
            "cleanup_quality": {{
                "is_thorough": boolean,
                "remaining_issues": ["issue1", "issue2"],
                "sanitization_level": "poor/fair/good/excellent"
            }},
            "temporal_analysis": {{
                "is_recent": boolean,
                "lighting_consistent": boolean,
                "recent_activity_signs": boolean
            }},
            "overall_verification": {{
                "verified": boolean,
                "confidence_score": number (0-100),
                "verification_notes": "string"
            }}
        }}
        """
        print("✓ Prompt prepared")

        # Call Gemini API
        print("\n=== Calling Gemini API ===")
        start_time = datetime.now()
        response = await call_gemini_api(prompt, [before_image, after_image])
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        print(f"✓ Gemini API call completed in {duration:.2f} seconds")
        print(f"Raw response length: {len(response)}")
        
        # Parse the response
        print("\n=== Parsing Gemini Response ===")
        try:
            result = json.loads(response)
            print("✓ Successfully parsed JSON response")
            print(f"Response keys: {list(result.keys())}")
            
            # Extract and validate all fields
            is_same_location = bool(result.get("is_same_location", False))
            location_confidence = float(result.get("location_match_confidence", 0))
            location_reasons = result.get("location_match_reasons", [])
            
            print(f"\n=== Location Analysis ===")
            print(f"Initial is_same_location: {is_same_location}")
            print(f"Location confidence: {location_confidence}")
            print(f"Location reasons: {location_reasons}")
            
            # If location confidence is high enough, consider it same location
            if location_confidence >= 30:  # Lower threshold for location matching
                is_same_location = True
                print("✓ Location confidence threshold met, marking as same location")
            
            waste_analysis = result.get("waste_analysis", {})
            before_waste = waste_analysis.get("before_waste_types", [])
            after_waste = waste_analysis.get("after_waste_types", [])
            waste_removed = bool(waste_analysis.get("waste_removed", False))
            new_waste = bool(waste_analysis.get("new_waste_detected", False))
            
            print(f"\n=== Waste Analysis ===")
            print(f"Before waste types: {before_waste}")
            print(f"After waste types: {after_waste}")
            print(f"Waste removed: {waste_removed}")
            print(f"New waste detected: {new_waste}")
            
            cleanup_quality = result.get("cleanup_quality", {})
            is_thorough = bool(cleanup_quality.get("is_thorough", False))
            remaining_issues = cleanup_quality.get("remaining_issues", [])
            sanitization = cleanup_quality.get("sanitization_level", "poor")
            
            print(f"\n=== Cleanup Quality ===")
            print(f"Is thorough: {is_thorough}")
            print(f"Remaining issues: {remaining_issues}")
            print(f"Sanitization level: {sanitization}")
            
            temporal = result.get("temporal_analysis", {})
            is_recent = bool(temporal.get("is_recent", False))
            lighting_ok = bool(temporal.get("lighting_consistent", False))
            activity_signs = bool(temporal.get("recent_activity_signs", False))
            
            print(f"\n=== Temporal Analysis ===")
            print(f"Is recent: {is_recent}")
            print(f"Lighting consistent: {lighting_ok}")
            print(f"Activity signs: {activity_signs}")
            
            overall = result.get("overall_verification", {})
            verified = bool(overall.get("verified", False))
            confidence = float(overall.get("confidence_score", 0))
            notes = overall.get("verification_notes", "")
            
            print(f"\n=== Overall Verification ===")
            print(f"Verified: {verified}")
            print(f"Confidence score: {confidence}")
            print(f"Notes: {notes}")
            
            # Calculate improvement percentage based on multiple factors
            improvement_factors = [
                location_confidence / 100,
                1.0 if waste_removed else 0.0,
                0.0 if new_waste else 1.0,
                1.0 if is_thorough else 0.5,
                0.8 if sanitization in ["good", "excellent"] else 0.4,
                1.0 if is_recent else 0.7,
                1.0 if lighting_ok else 0.6,
                1.0 if activity_signs else 0.5
            ]
            improvement_percentage = sum(improvement_factors) / len(improvement_factors) * 100
            
            print(f"\n=== Final Results ===")
            print(f"Final is_same_location: {is_same_location}")
            print(f"Final is_clean: {verified and is_thorough and not new_waste}")
            print(f"Improvement percentage: {improvement_percentage:.2f}%")
            
            return {
                "is_same_location": is_same_location,
                "is_clean": verified and is_thorough and not new_waste,
                "improvement_percentage": improvement_percentage,
                "verification_details": {
                    "location_confidence": location_confidence,
                    "location_reasons": location_reasons,
                    "waste_analysis": {
                        "before_types": before_waste,
                        "after_types": after_waste,
                        "waste_removed": waste_removed,
                        "new_waste": new_waste
                    },
                    "cleanup_quality": {
                        "is_thorough": is_thorough,
                        "remaining_issues": remaining_issues,
                        "sanitization_level": sanitization
                    },
                    "temporal_analysis": {
                        "is_recent": is_recent,
                        "lighting_consistent": lighting_ok,
                        "recent_activity": activity_signs
                    },
                    "overall_confidence": confidence,
                    "notes": notes
                }
            }
            
        except json.JSONDecodeError as e:
            print(f"✗ Error parsing JSON response: {str(e)}")
            print(f"Raw response: {response[:500]}...")  # Print first 500 chars of response
            return {
                "is_same_location": False,
                "is_clean": False,
                "improvement_percentage": 0,
                "verification_details": {
                    "error": "Failed to parse AI response"
                }
            }

    except Exception as e:
        print(f"✗ Error in compare_cleanup_images: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return {
            "is_same_location": False,
            "is_clean": False,
            "improvement_percentage": 0,
            "verification_details": {
                "error": str(e)
            }
        } 

async def call_gemini_api(prompt: str, images: List[str]) -> str:
    """
    Make an API call to Gemini with the given prompt and images.
    Returns the raw response text from Gemini.
    """
    try:
        # Construct the request to Gemini
        model = "gemini-2.0-flash"
        api_url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": settings.GOOGLE_API_KEY
        }

        # Prepare the content parts
        content_parts = [{"text": prompt}]
        
        # Add images to the content parts
        for image in images:
            content_parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": image
                }
            })

        data = {
            "contents": [{
                "role": "user",
                "parts": content_parts
            }],
            "generationConfig": {
                "temperature": 0.2,
                "topK": 32,
                "topP": 0.95,
                "maxOutputTokens": 4096,
            }
        }

        print(f"\n=== Making Gemini API Request ===")
        print(f"Using model: {model}")
        print(f"API URL: {api_url}")
        print(f"Number of images: {len(images)}")
        print(f"Prompt length: {len(prompt)}")

        # Make the API request
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(api_url, json=data, headers=headers)
            
            if response.status_code != 200:
                error_detail = f"Gemini API error: {response.status_code} - {response.text}"
                print(f"✗ API Error: {error_detail}")
                raise HTTPException(status_code=500, detail=error_detail)
            
            result = response.json()
            response_text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
            
            print(f"✓ API Response received")
            print(f"Response length: {len(response_text)}")
            
            # Clean the response text if it contains markdown formatting
            if "```json" in response_text:
                # Extract JSON from markdown code block
                json_start = response_text.find("```json") + 7
                json_end = response_text.rfind("```")
                if json_end > json_start:
                    response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                # Extract JSON from generic code block
                json_start = response_text.find("```") + 3
                json_end = response_text.rfind("```")
                if json_end > json_start:
                    response_text = response_text[json_start:json_end].strip()
            
            print(f"Cleaned response length: {len(response_text)}")
            return response_text

    except Exception as e:
        print(f"✗ Error in call_gemini_api: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Error calling Gemini API: {str(e)}"
        ) 