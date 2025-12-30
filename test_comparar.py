import requests
import json
import uuid

while True:
    ticket_number = input("\nEnter the ticket number to compare (o 'exit' para salir): ")
    if ticket_number.strip().lower() == "exit":
        break

    payload = {
        "ticket_number": ticket_number,
        "user_question": f"¿Cuáles tickets se parecen al ticket {ticket_number}?"
    }

    conversation_id = str(uuid.uuid4())
    try:
        print("\nSending request to /comparar_ticket...")
        response = requests.post(
            f"http://127.0.0.1:5050/comparar_ticket?conversation_id={conversation_id}",
            json=payload
        )
        print("\nResponse:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"\n❌ Request failed: {e}")
