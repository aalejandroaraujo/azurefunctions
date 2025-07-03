import azure.functions as func
import json
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from shared.common import get_openai_client
except ImportError:
    from openai import OpenAI
    def get_openai_client():
        return OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Azure Function to determine chat mode switch using OpenAI analysis."""
    
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse(json.dumps({"status": "error", "message": "Request body is required."}), status_code=400, mimetype="application/json")
        
        session_id = req_body.get("session_id")
        context = req_body.get("context")
        
        if not session_id:
            return func.HttpResponse(json.dumps({"status": "error", "message": "Missing required 'session_id' field."}), status_code=400, mimetype="application/json")
        
        if not context or not isinstance(context, str):
            return func.HttpResponse(json.dumps({"status": "error", "message": "Missing or invalid 'context' field."}), status_code=400, mimetype="application/json")
        
        client = get_openai_client()
        
        system_prompt = "You are a conversation controller for a mental health assistant. Based on the user's last message, decide whether the assistant should continue asking intake questions, switch to advice-giving, enter reflective discussion, or summarize and close. Only return the most appropriate chat mode: intake, advice, reflection, or summary."
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context}
            ],
            max_tokens=10,
            temperature=0.1
        )
        
        new_mode = response.choices[0].message.content.strip().lower()
        valid_modes = ["intake", "advice", "reflection", "summary"]
        if new_mode not in valid_modes:
            new_mode = "advice"
        
        return func.HttpResponse(json.dumps({"status": "ok", "new_mode": new_mode}), status_code=200, mimetype="application/json")
        
    except ValueError:
        return func.HttpResponse(json.dumps({"status": "error", "message": "Invalid JSON in request body."}), status_code=400, mimetype="application/json")
    except Exception:
        logging.error("Error in switch_chat_mode function")
        return func.HttpResponse(json.dumps({"status": "error", "message": "Internal server error occurred."}), status_code=500, mimetype="application/json")

