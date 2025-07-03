import json
import logging
import httpx
import azure.functions as func


async def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Azure Function to evaluate intake progress based on collected fields.
    
    Calculates a weighted score and determines if enough data has been collected.
    """
    logging.info('evaluate_intake_progress function processed a request.')
    
    try:
        # Parse JSON input
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
        
        if not req_body:
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": "Request body is required."
                }),
                status_code=400,
                mimetype="application/json"
            )
        
        # Validate required fields
        if "session_id" not in req_body:
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": "Missing required field: 'session_id'."
                }),
                status_code=400,
                mimetype="application/json"
            )
        
        if "fields" not in req_body:
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": "Missing required field: 'fields'."
                }),
                status_code=400,
                mimetype="application/json"
            )
        
        fields = req_body["fields"]
        if not isinstance(fields, dict):
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": "Invalid input: 'fields' must be an object."
                }),
                status_code=400,
                mimetype="application/json"
            )
        
        # Define field weights
        field_weights = {
            "symptoms": 3,
            "duration": 2,
            "triggers": 2,
            "intensity": 1,
            "frequency": 1,
            "impact_on_life": 2,
            "coping_mechanisms": 1
        }
        
        # Calculate score
        score = 0
        for field_name, weight in field_weights.items():
            field_value = fields.get(field_name)
            if is_field_non_empty(field_value):
                score += weight
        
        # Determine if enough data collected (threshold: 6 out of 12)
        enough_data = score >= 6
        
        # Return success response
        return func.HttpResponse(
            json.dumps({
                "status": "ok",
                "score": score,
                "enough_data": enough_data
            }),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Unexpected error in evaluate_intake_progress: {str(e)}")
        return func.HttpResponse(
            json.dumps({
                "status": "error",
                "message": "Internal server error occurred."
            }),
            status_code=500,
            mimetype="application/json"
        )


def is_field_non_empty(value) -> bool:
    """Check if a field value is non-empty (non-null, non-whitespace string)."""
    return value is not None and isinstance(value, str) and value.strip() != ""

