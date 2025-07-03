import json
import logging
import azure.functions as func
from shared.common import get_openai_client


async def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Azure Function: risk_escalation_check
    
    Evaluates user messages using OpenAI's moderation endpoint
    and returns a flag if any content is deemed high risk.
    
    Input JSON:
    {
        "session_id": "abc123",
        "message": "I sometimes feel like hurting myself."
    }
    
    Output JSON:
    {
        "status": "ok",
        "flag": "self-harm" | "violence" | null
    }
    """
    
    try:
        # Parse request body
        try:
            req_body = req.get_json()
        except ValueError:
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": "Invalid JSON in request body."
                }),
                status_code=400,
                mimetype="application/json"
            )
        
        # Validate required fields
        if not req_body or "message" not in req_body:
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": "Missing required field: message."
                }),
                status_code=400,
                mimetype="application/json"
            )
        
        message = req_body.get("message", "").strip()
        session_id = req_body.get("session_id", "")
        
        if not message:
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": "Message cannot be empty."
                }),
                status_code=400,
                mimetype="application/json"
            )
        
        # Get OpenAI client
        client = get_openai_client()
        
        # Call OpenAI moderation API
        try:
            moderation_response = await client.moderations.create(input=message)
            
            # Extract moderation results
            results = moderation_response.results[0]
            categories = results.categories
            flagged = results.flagged
            
            # Determine risk flag based on categories
            flag = None
            
            if flagged:
                # Check for self-harm related categories (maps to user's "self-harm" and "suicide")
                if (getattr(categories, 'self_harm', False) or 
                    getattr(categories, 'self_harm_intent', False)):
                    flag = "self-harm"
                # Check for violence related categories (maps to user's "violence" and "threatening")
                elif (getattr(categories, 'violence', False) or 
                      getattr(categories, 'harassment_threatening', False)):
                    flag = "violence"
            
            # Log session info (but not message content)
            logging.info(f"Risk check completed for session: {session_id}, flag: {flag}")
            
            return func.HttpResponse(
                json.dumps({
                    "status": "ok",
                    "flag": flag
                }),
                status_code=200,
                mimetype="application/json"
            )
            
        except Exception as openai_error:
            logging.error(f"OpenAI moderation API error: {str(openai_error)}")
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": "Moderation API failed or invalid input."
                }),
                status_code=500,
                mimetype="application/json"
            )
    
    except Exception as e:
        logging.error(f"Unexpected error in risk_escalation_check: {str(e)}")
        return func.HttpResponse(
            json.dumps({
                "status": "error",
                "message": "Internal server error."
            }),
            status_code=500,
            mimetype="application/json"
        )

