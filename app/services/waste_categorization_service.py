import os
import base64
import httpx
from datetime import datetime
from typing import Dict, Any
from app.config import get_settings
import logging
import json

settings = get_settings()
logger = logging.getLogger(__name__)

async def analyze_waste_image(image: str) -> Dict[str, Any]:
    """
    Analyze a waste image to categorize waste types and determine recyclability
    
    Args:
        image: Base64 encoded image string
        
    Returns:
        Dict containing waste categorization and recyclability analysis
    """
    # Ensure the image is properly formatted for Gemini
    if "base64," in image:
        image = image.split("base64,")[1]
    
    # Construct the prompt for Gemini
    prompt = """
    Analyze this image of waste and provide detailed categorization and recyclability information.
    
    Instructions:
    1. First, determine the MAIN CATEGORY of waste in the image. Choose ONLY ONE from:
       - DRY WASTE (paper, plastic, metal, glass, etc.)
       - WET WASTE (food waste, organic matter, etc.)
       - E-WASTE (electronic items, batteries, etc.)
       - HAZARDOUS WASTE (chemicals, medical waste, etc.)
       - CONSTRUCTION WASTE (debris, rubble, etc.)
       - MIXED WASTE (combination of multiple categories)
    
    2. Then, identify and categorize the specific waste types present in the image
    3. For each waste type, determine:
       - Material composition
       - Potential recyclability
       - Recycling process if applicable
       - Estimated recycling value
       - Environmental impact
    4. Provide a comprehensive recyclability assessment
    
    RESPOND ONLY WITH VALID JSON. Do not include any explanations or markdown formatting.
    The response must be a valid JSON object that can be parsed directly.
    
    Your response MUST follow this exact JSON schema:
    {
        "main_category": "string (DRY WASTE/WET WASTE/E-WASTE/HAZARDOUS WASTE/CONSTRUCTION WASTE/MIXED WASTE)",
        "main_category_confidence": 0-100,
        "waste_categories": [
            {
                "type": "string (e.g., Plastic, Paper, Metal, etc.)",
                "material": "string (specific material type)",
                "is_recyclable": true/false,
                "recycling_process": "string (how it can be recycled)",
                "recycling_value": "string (low/medium/high)",
                "environmental_impact": "string (brief impact description)"
            }
        ],
        "overall_analysis": {
            "total_recyclable_percentage": 0-100,
            "primary_material": "string",
            "recycling_recommendation": "string",
            "environmental_notes": "string"
        },
        "confidence_score": 0-100
    }
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
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(api_url, json=data, headers=headers)
            
            if response.status_code != 200:
                error_detail = f"Gemini API error: {response.status_code} - {response.text}"
                logger.error(error_detail)
                return {
                    "error": error_detail,
                    "main_category": "UNKNOWN",
                    "main_category_confidence": 0,
                    "waste_categories": [],
                    "overall_analysis": {
                        "total_recyclable_percentage": 0,
                        "primary_material": "Unknown",
                        "recycling_recommendation": "Unable to analyze",
                        "environmental_notes": "Analysis failed"
                    },
                    "confidence_score": 0
                }
            
            response.raise_for_status()
            result = response.json()
            
            # Extract the text from the response
            response_text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
            
            # Log the raw response for debugging
            logger.debug(f"Raw Gemini response: {response_text[:500]}...")
            
            # Clean up the response text
            cleaned_text = response_text.strip()
            
            # Remove any markdown code blocks if present
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text.split("```json", 1)[1]
                if "```" in cleaned_text:
                    cleaned_text = cleaned_text.split("```", 1)[0]
            elif cleaned_text.startswith("```"):
                cleaned_text = cleaned_text.split("```", 1)[1]
                if "```" in cleaned_text:
                    cleaned_text = cleaned_text.split("```", 1)[0]
            
            cleaned_text = cleaned_text.strip()
            
            # Try to parse the JSON
            try:
                analysis_result = json.loads(cleaned_text)
                
                # Validate the structure
                if not isinstance(analysis_result, dict):
                    raise ValueError("Response is not a JSON object")
                
                # Ensure required fields are present
                if "main_category" not in analysis_result:
                    analysis_result["main_category"] = "UNKNOWN"
                if "main_category_confidence" not in analysis_result:
                    analysis_result["main_category_confidence"] = 0
                if "waste_categories" not in analysis_result:
                    analysis_result["waste_categories"] = []
                if "overall_analysis" not in analysis_result:
                    analysis_result["overall_analysis"] = {
                        "total_recyclable_percentage": 0,
                        "primary_material": "Unknown",
                        "recycling_recommendation": "Not analyzed",
                        "environmental_notes": "Not analyzed"
                    }
                if "confidence_score" not in analysis_result:
                    analysis_result["confidence_score"] = 0
                
                return analysis_result
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error: {str(e)}")
                logger.error(f"Cleaned text that failed to parse: {cleaned_text[:500]}...")
                return {
                    "error": f"Failed to parse JSON response: {str(e)}",
                    "main_category": "UNKNOWN",
                    "main_category_confidence": 0,
                    "waste_categories": [],
                    "overall_analysis": {
                        "total_recyclable_percentage": 0,
                        "primary_material": "Unknown",
                        "recycling_recommendation": "Unable to analyze",
                        "environmental_notes": "Analysis failed"
                    },
                    "confidence_score": 0
                }
                
    except Exception as e:
        logger.error(f"Error analyzing waste image: {str(e)}")
        return {
            "error": str(e),
            "main_category": "UNKNOWN",
            "main_category_confidence": 0,
            "waste_categories": [],
            "overall_analysis": {
                "total_recyclable_percentage": 0,
                "primary_material": "Unknown",
                "recycling_recommendation": "Unable to analyze",
                "environmental_notes": "Analysis failed"
            },
            "confidence_score": 0
        } 