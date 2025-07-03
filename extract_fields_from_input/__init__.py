import azure.functions as func
import json
import logging
from shared.common import get_openai_client


async def main(req: func.HttpRequest) -> func.HttpResponse:
    """Extract structured fields from user messages using OpenAI gpt-4o-mini."""
    try:
        # Parse and validate request
        try:
            req_body = req.get_json()
        except ValueError:
            return func.HttpResponse(
                json.dumps({"status": "error", "message": "Missing 'message' field or OpenAI call failed."}),
                status_code=400,
                mimetype="application/json"
            )
        
        if not req_body or not req_body.get("message"):
            return func.HttpResponse(
                json.dumps({"status": "error", "message": "Missing 'message' field or OpenAI call failed."}),
                status_code=400,
                mimetype="application/json"
            )
        
        message = req_body["message"]
        session_id = req_body.get("session_id")
        
        # Log session_id but not message content for privacy
        logging.info(f"Processing field extraction for session: {session_id}")
        
        # Extract fields using OpenAI
        fields = await extract_fields_with_openai(message)
        
        return func.HttpResponse(
            json.dumps({"status": "ok", "fields": fields}),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Error in extract_fields_from_input: {str(e)}")
        return func.HttpResponse(
            json.dumps({"status": "error", "message": "Missing 'message' field or OpenAI call failed."}),
            status_code=500,
            mimetype="application/json"
        )


async def extract_fields_with_openai(message: str) -> dict:
    """Extract structured fields from user message using OpenAI."""
    
    system_prompt = """You are a data extractor for a mental health assistant. Based on the user's message, extract the following fields in this order and with these exact names: symptoms, duration, triggers, intensity, frequency, impact_on_life, coping_mechanisms. If a field is not clearly mentioned, return null. Output the result as a flat JSON object. Do not guess, infer, or fabricate.

Examples:
User: "I've been feeling overwhelmed for a few weeks. It gets worse at work."
Output: {"symptoms": "overwhelmed", "duration": "a few weeks", "triggers": "work", "intensity": null, "frequency": null, "impact_on_life": null, "coping_mechanisms": null}

User: "Hello, how are you today?"
Output: {"symptoms": null, "duration": null, "triggers": null, "intensity": null, "frequency": null, "impact_on_life": null, "coping_mechanisms": null}"""
    
    client = get_openai_client()
    
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ],
        temperature=0.3,
        max_tokens=500,
        timeout=10
    )
    
    # Parse and return the JSON response
    content = response.choices[0].message.content.strip()
    return json.loads(content)

