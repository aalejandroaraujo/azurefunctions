import json
import logging
import datetime
import azure.functions as func
from shared.common import get_openai_client, nocodb_upsert

app = func.FunctionApp()

# --- Existing sample function ---
@app.route(route="HttpExample", auth_level=func.AuthLevel.ANONYMOUS)
def HttpExample(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')
    name = req.params.get('name')
    if not name:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            name = req_body.get('name')
    if name:
        return func.HttpResponse(f"Hello, {name}. This HTTP triggered function executed successfully.")
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )

# --- 1. extract_fields_from_input ---
@app.function_name(name="extract_fields_from_input")
@app.route(route="extract_fields_from_input", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
async def extract_fields(req: func.HttpRequest) -> func.HttpResponse:
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
    logging.info(f"Processing field extraction for session: {session_id}")
    fields = await extract_fields_with_openai(message)
    return func.HttpResponse(
        json.dumps({"status": "ok", "fields": fields}),
        status_code=200,
        mimetype="application/json"
    )

async def extract_fields_with_openai(message: str) -> dict:
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
    content = response.choices[0].message.content.strip()
    return json.loads(content)

# --- 2. evaluate_intake_progress ---
@app.function_name(name="evaluate_intake_progress")
@app.route(route="evaluate_intake_progress", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
async def evaluate_intake_progress(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('evaluate_intake_progress function processed a request.')
    try:
        try:
            req_body = req.get_json()
        except ValueError:
            return func.HttpResponse(
                json.dumps({"status": "error", "message": "Invalid JSON in request body."}),
                status_code=400,
                mimetype="application/json"
            )
        if not req_body:
            return func.HttpResponse(
                json.dumps({"status": "error", "message": "Request body is required."}),
                status_code=400,
                mimetype="application/json"
            )
        if "session_id" not in req_body:
            return func.HttpResponse(
                json.dumps({"status": "error", "message": "Missing required field: 'session_id'."}),
                status_code=400,
                mimetype="application/json"
            )
        if "fields" not in req_body or not isinstance(req_body["fields"], dict):
            return func.HttpResponse(
                json.dumps({"status": "error", "message": "Invalid input: 'fields' must be an object."}),
                status_code=400,
                mimetype="application/json"
            )
        fields = req_body["fields"]
        field_weights = {"symptoms":3,"duration":2,"triggers":2,"intensity":1,"frequency":1,"impact_on_life":2,"coping_mechanisms":1}
        score = 0
        for field_name, weight in field_weights.items():
            value = fields.get(field_name)
            if value is not None and isinstance(value, str) and value.strip() != "":
                score += weight
        enough_data = score >= 6
        return func.HttpResponse(
            json.dumps({"status": "ok", "score": score, "enough_data": enough_data}),
            status_code=200,
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"Unexpected error in evaluate_intake_progress: {str(e)}")
        return func.HttpResponse(
            json.dumps({"status": "error", "message": "Internal server error occurred."}),
            status_code=500,
            mimetype="application/json"
        )

# --- 3. risk_escalation_check ---
@app.function_name(name="risk_escalation_check")
@app.route(route="risk_escalation_check", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
async def risk_escalation_check(req: func.HttpRequest) -> func.HttpResponse:
    try:
        try:
            req_body = req.get_json()
        except ValueError:
            return func.HttpResponse(
                json.dumps({"status": "error", "message": "Invalid JSON in request body."}),
                status_code=400,
                mimetype="application/json"
            )
        if not req_body or "message" not in req_body:
            return func.HttpResponse(
                json.dumps({"status": "error", "message": "Missing required field: message."}),
                status_code=400,
                mimetype="application/json"
            )
        message = req_body.get("message", "").strip()
        session_id = req_body.get("session_id", "")
        if not message:
            return func.HttpResponse(
                json.dumps({"status": "error", "message": "Message cannot be empty."}),
                status_code=400,
                mimetype="application/json"
            )
        client = get_openai_client()
        mod_resp = await client.moderations.create(input=message)
        results = mod_resp.results[0]
        categories = results.categories
        flagged = results.flagged
        flag = None
        if flagged:
            if getattr(categories, 'self_harm', False) or getattr(categories, 'self_harm_intent', False):
                flag = "self-harm"
            elif getattr(categories, 'violence', False) or getattr(categories, 'harassment_threatening', False):
                flag = "violence"
        logging.info(f"Risk check completed for session: {session_id}, flag: {flag}")
        return func.HttpResponse(
            json.dumps({"status": "ok", "flag": flag}),
            status_code=200,
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"Unexpected error in risk_escalation_check: {str(e)}")
        return func.HttpResponse(
            json.dumps({"status": "error", "message": "Internal server error."}),
            status_code=500,
            mimetype="application/json"
        )

# --- 4. switch_chat_mode ---
@app.function_name(name="switch_chat_mode")
@app.route(route="switch_chat_mode", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
async def switch_chat_mode(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing switch_chat_mode request')
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse(json.dumps({"status": "error", "message": "Request body is required."}), status_code=400, mimetype="application/json")
        session_id = req_body.get("session_id")
        context = req_body.get("context")
        logging.info(f"Processing chat mode switch for session: {session_id}")
        if not session_id:
            return func.HttpResponse(json.dumps({"status": "error", "message": "Missing required 'session_id' field."}), status_code=400, mimetype="application/json")
        if not context or not isinstance(context, str):
            return func.HttpResponse(json.dumps({"status": "error", "message": "Missing or invalid 'context' field."}), status_code=400, mimetype="application/json")
        if len(context.strip()) == 0:
            return func.HttpResponse(json.dumps({"status": "error", "message": "Context cannot be empty."}), status_code=400, mimetype="application/json")
        if len(context) > 4000:  # Reasonable limit for context
            context = context[:4000]
        client = get_openai_client()
        logging.info(f"Client type: {type(client)}")
        system_prompt = (
            "You are a conversation controller for a mental health assistant. "
            "Based on the user's last message, decide whether the assistant should continue asking intake questions, switch to advice-giving, enter reflective discussion, or summarize and close. "
            "Only return the most appropriate chat mode: intake, advice, reflection, or summary."
        )
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context}
            ],
            max_tokens=10,
            temperature=0.1,
            timeout=10
        )
        logging.info(f"Response type: {type(response)}")
        new_mode = response.choices[0].message.content
        if not new_mode:
            new_mode = "advice"  # Default fallback
        else:
            new_mode = new_mode.strip().lower()
        if new_mode not in ["intake", "advice", "reflection", "summary"]:
            new_mode = "advice"
        logging.info(f"Chat mode determined for session {session_id}: {new_mode}")
        return func.HttpResponse(json.dumps({"status": "ok", "new_mode": new_mode}), status_code=200, mimetype="application/json")
    except ValueError:
        return func.HttpResponse(json.dumps({"status": "error", "message": "Invalid JSON in request body."}), status_code=400, mimetype="application/json")
    except Exception as e:
        logging.error(f"Error in switch_chat_mode: {str(e)}")
        return func.HttpResponse(json.dumps({"status": "error", "message": "Internal server error occurred."}), status_code=500, mimetype="application/json")

# --- 5. save_session_summary ---
@app.function_name(name="save_session_summary")
@app.route(route="save_session_summary", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
async def save_session_summary(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing save_session_summary request')
    try:
        try:
            req_body = req.get_json()
        except ValueError:
            return func.HttpResponse(
                json.dumps({"status": "error", "message": "Invalid JSON in request body"}),
                status_code=400,
                mimetype="application/json"
            )
        if not req_body:
            return func.HttpResponse(
                json.dumps({"status": "error", "message": "Request body is required"}),
                status_code=400,
                mimetype="application/json"
            )
        session_id = req_body.get("session_id")
        summary = req_body.get("summary")
        if not session_id or not isinstance(session_id, str) or not session_id.strip():
            return func.HttpResponse(
                json.dumps({"status": "error", "message": "Missing 'session_id' field or NocoDB request failed."}),
                status_code=400,
                mimetype="application/json"
            )
        if not summary or not isinstance(summary, str) or not summary.strip():
            return func.HttpResponse(
                json.dumps({"status": "error", "message": "Missing 'summary' field or NocoDB request failed."}),
                status_code=400,
                mimetype="application/json"
            )
        if len(summary) > 2000:
            summary = summary[:2000]
            logging.info('Summary truncated to 2000 characters')
        await nocodb_upsert(session_id.strip(), summary.strip())
        logging.info('Successfully saved summary')
        return func.HttpResponse(
            json.dumps({"status": "ok"}),
            status_code=200,
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"Unexpected error in save_session_summary: {str(e)}")
        return func.HttpResponse(
            json.dumps({"status": "error", "message": "Internal server error occurred."}),
            status_code=500,
            mimetype="application/json"
        )
