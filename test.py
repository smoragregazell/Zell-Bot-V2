import os
import requests
import json
import uuid

class APITester:
    def __init__(self, base_url="http://127.0.0.1:5050"):        
        self.base_url = base_url
        self.conversation_id = None
        self.headers = {"Content-Type": "application/json"}
        self.session = requests.Session()
        self.token = None
        self.step_id = 1
        self.user_name = None 

    def set_token(self, token):
        self.token = token.strip()

    def set_user_name(self, user_name):
        self.user_name = str(user_name).strip()

    def send_message(self, message, zToken=None):
        if not zToken and not self.token:
            print("⚠️ Warning: No token provided!")
            return {"error": "Token is required"}

        payload = {
            "conversation_id": self.conversation_id or str(uuid.uuid4()),
            "user_message": message,
            "zToken": zToken or self.token,
            "userName": self.user_name or "anon@zell.mx",
            "step_id": self.step_id
        }
        self.step_id += 1

        try:
            response = self.session.post(
                f"{self.base_url}/classify",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            data = response.json()
            self.conversation_id = data.get("conversation_id", self.conversation_id)
            return data

        except requests.exceptions.HTTPError as e:
            print(f"❌ HTTP {e.response.status_code}: {e.response.text}")
            return {"error": f"HTTP {e.response.status_code}"}
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
            return {"error": f"Request failed: {str(e)}"}

def main():
    tester = APITester()
    DEFAULT_TOKEN = "DEV-TOKEN"
    DEFAULT_USER = "SANTIAGO MORATEST"

    token = input("\nEnter your token (o deja vacío para usar dummy): ").strip() or DEFAULT_TOKEN
    user_name = input("\nEnter your userName: ").strip() or DEFAULT_USER

    tester.set_token(token)
    tester.set_user_name(user_name)



    while True:
        message = input("\nEnter your message (o 'exit' para salir): ")
        if message.lower() == 'exit':
            break

        print("\nSending request...")
        print(f"Using conversation_id: {tester.conversation_id}")
        response = tester.send_message(message)
        print("\nResponse:")
        print(json.dumps(response, indent=2, ensure_ascii=False))

        if response.get("classification") == "Comparar ticket" and response.get("results"):
            analysis = response["results"][0]["analysis"].get("analisis_final", "")
            if analysis:
                print("\n—— Análisis ——\n" + analysis)

if __name__ == "__main__":
    main()