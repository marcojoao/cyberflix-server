import base64
import json
from os import environ

import firebase_admin
from firebase_admin import credentials, firestore


class Db:
    def __init__(self, firebase_env_key: str | None = None) -> None:
        app_environment: str = (environ.get("APP_ENVIRONMENT") or "STAGING").upper()
        if firebase_env_key is None:
            firebase_env_key = f"FIREBASE_{app_environment}_KEY"
        firebase_b64 = environ.get(firebase_env_key) or None
        self.json_file = self.__load_firebase_env(firebase_b64)
        self.name = f"CyberflixDB({firebase_env_key})"

        try:
            self.app = firebase_admin.get_app(name=self.name)

        except ValueError as _:
            cred = credentials.Certificate(self.json_file)
            self.app = firebase_admin.initialize_app(cred, name=self.name)

        self.client = firestore.client(app=self.app)
        print(f"Firebase DB initialized with {self.name}")

    def __load_firebase_env(self, base64_string) -> dict:
        if base64_string is None:
            raise ValueError("FIREBASE environment variable is not set")
        base64_bytes = base64_string.encode("ascii")
        sample_string_bytes = base64.b64decode(base64_bytes + b"==", validate=True)
        sample_string = sample_string_bytes.decode("ascii").replace("'", '"')
        json_object = json.loads(sample_string)
        return json_object

    def get(self, collection: str, doc: str) -> dict:
        try:
            doc_ref = self.client.collection(collection).document(doc)
            result = doc_ref.get()
            return result.to_dict()
        except Exception as e:
            print(e)
            return {}

    def set(self, collection: str, doc: str, data: dict) -> bool:
        try:
            doc_ref = self.client.collection(collection).document(doc)
            doc_ref.set(data)
            return True
        except Exception as e:
            print(e)
            return False
