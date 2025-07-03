"""
Azure Function: save_session_summary

Persists a finalized summary of the session, provided by the Assistant Summary agent,
into a NocoDB table called `summaries`.
"""

import json
import logging
import datetime
import azure.functions as func
from shared.common import nocodb_upsert


async def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Save session summary to NocoDB.
    
    Expected input JSON:
    {
        "session_id": "abc123",
        "summary": "The user expressed concerns about persistent anxiety and lack of sleep."
    }
    
    Returns:
    {
        "status": "ok"
    }
    """
    logging.info('Processing save_session_summary request')
    
    try:
        # Parse request body
        try:
            req_body = req.get_json()
        except ValueError:
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": "Invalid JSON in request body"
                }),
                status_code=400,
                mimetype="application/json"
            )
        
        if not req_body:
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": "Request body is required"
                }),
                status_code=400,
                mimetype="application/json"
            )
        
        # Validate required fields
        session_id = req_body.get("session_id")
        summary = req_body.get("summary")
        
        if not session_id or not isinstance(session_id, str) or not session_id.strip():
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": "Missing 'session_id' field or NocoDB request failed."
                }),
                status_code=400,
                mimetype="application/json"
            )
        
        if not summary or not isinstance(summary, str) or not summary.strip():
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": "Missing 'summary' field or NocoDB request failed."
                }),
                status_code=400,
                mimetype="application/json"
            )
        
        # Truncate summary if longer than 2000 characters
        if len(summary) > 2000:
            summary = summary[:2000]
            logging.info('Summary truncated to 2000 characters')
        
        # Generate updated_at timestamp
        updated_at = datetime.datetime.utcnow().isoformat(timespec='seconds') + 'Z'
        
        # Save to NocoDB using shared function
        try:
            await nocodb_upsert(session_id.strip(), summary.strip(), updated_at)
            logging.info('Successfully saved summary')
            
            return func.HttpResponse(
                json.dumps({"status": "ok"}),
                status_code=200,
                mimetype="application/json"
            )
            
        except Exception as e:
            logging.error(f'Failed to save summary: {str(e)}')
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": "Missing 'summary' field or NocoDB request failed."
                }),
                status_code=500,
                mimetype="application/json"
            )
    
    except Exception as e:
        logging.error(f'Unexpected error in save_session_summary: {str(e)}')
        return func.HttpResponse(
            json.dumps({
                "status": "error",
                "message": "Missing 'summary' field or NocoDB request failed."
            }),
            status_code=500,
            mimetype="application/json"
        )

