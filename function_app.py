import azure.functions as func
import json
import logging
from datetime import datetime
from shared.storage import save_session_summary

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.route(route="orchestrate_mental_health_functions", methods=["POST"])
def orchestrate_mental_health_functions(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("[orchestrate] Invocation started")
    try:
        # --- Parse input body ---
        try:
            req_body = req.get_json()
        except ValueError:
            logging.warning("[orchestrate] Invalid JSON payload")
            return func.HttpResponse(
                json.dumps({"error": "Invalid JSON"}),
                status_code=400,
                headers={"Content-Type": "application/json"}
            )

        message = req_body.get('message', '')
        session_id = req_body.get('session_id', '')

        logging.info(f"[orchestrate] session={session_id} message={message!r}")

        # --- Placeholder de lógica de enrutamiento/orquestación ---
        assistant_response = f"Processed your message: {message}"
        routing_decision = "default_assistant"
        # ==========================================================

        # --- Construir payload de respuesta completo ---
        response_payload = {
            "status": "success",
            "test": "Function executed successfully",
            "message": f"Received: {message}",
            "assistant_response": assistant_response,
            "session_id": session_id,
            "routing": {
                "next_assistant": routing_decision
            }
        }

        # --- Intentar grabar el resumen de sesión (stub) ---
        timestamp = datetime.utcnow().isoformat()
        try:
            save_session_summary(
                session_id=session_id,
                user_message=message,
                assistant_reply=assistant_response,
                routing_decision=routing_decision,
                timestamp=timestamp
            )
        except Exception as save_err:
            logging.error(f"[save_session_summary] failed: {save_err}")

        # --- Responder OK ---
        return func.HttpResponse(
            json.dumps(response_payload),
            status_code=200,
            headers={"Content-Type": "application/json"}
        )

    except Exception as e:
        logging.exception("[orchestrate] Unhandled exception")
        return func.HttpResponse(
            json.dumps({"error": "Internal server error"}),
            status_code=500,
            headers={"Content-Type": "application/json"}
        )
