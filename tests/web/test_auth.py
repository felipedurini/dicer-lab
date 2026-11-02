import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from services.simulator_api.app import create_app
from services.simulator_api.settings import Settings


ALICE = "10000000-0000-4000-8000-000000000001"
BOB = "20000000-0000-4000-8000-000000000002"


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = Settings.from_env({
            "APP_ENV":"production", "AUTH_MODE":"supabase", "APP_ORIGIN":"https://lab.example.org",
            "SIMULATOR_API_URL":"https://api.example.org", "API_HOST":"0.0.0.0",
            "DATA_DIR":str(Path(self.temp.name)/"data"), "SUPABASE_URL":"https://project.supabase.co",
            "SUPABASE_JWT_ALGORITHMS":"ES256", "ALLOWED_USER_IDS":f"{ALICE},{BOB}",
        })
        self.app = create_app(self.settings, start_worker=False)
        self.client = TestClient(self.app, base_url="https://api.example.org")
        self.private = ec.generate_private_key(ec.SECP256R1())
        public = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(self.private.public_key()))
        public.update({"kid":"active-key", "alg":"ES256", "use":"sig"})
        self.jwks = {"keys":[public]}

    def tearDown(self):
        self.client.close(); self.app.state.job_store.close(); self.temp.cleanup()

    def token(self, subject=ALICE, **overrides):
        now = int(time.time())
        claims = {"sub":subject,"role":"authenticated","aud":"authenticated","iss":"https://project.supabase.co/auth/v1","iat":now,"exp":now+300}
        claims.update(overrides)
        return jwt.encode(claims, self.private, algorithm="ES256", headers={"kid":"active-key"})

    def test_valid_signature_claims_and_allowlisted_user_are_accepted(self):
        with patch("services.simulator_api.auth._jwks", new=AsyncMock(return_value=self.jwks)):
            response = self.client.get("/v1/capabilities", headers={"authorization":f"Bearer {self.token()}"})
        self.assertEqual(response.status_code, 200)

    def test_missing_invalid_and_expired_tokens_are_rejected(self):
        missing = self.client.get("/v1/capabilities")
        self.assertEqual(missing.status_code, 401)
        expired = self.token(exp=int(time.time())-60)
        other = ec.generate_private_key(ec.SECP256R1())
        forged = jwt.encode({"sub":ALICE,"role":"authenticated","aud":"authenticated","iss":"https://project.supabase.co/auth/v1","iat":int(time.time()),"exp":int(time.time())+300}, other, algorithm="ES256", headers={"kid":"active-key"})
        with patch("services.simulator_api.auth._jwks", new=AsyncMock(return_value=self.jwks)):
            rejected = self.client.get("/v1/capabilities", headers={"authorization":f"Bearer {expired}"})
            invalid_signature = self.client.get("/v1/capabilities", headers={"authorization":f"Bearer {forged}"})
        self.assertEqual(rejected.status_code, 401)
        self.assertEqual(invalid_signature.status_code, 401)

    def test_wrong_issuer_and_non_allowlisted_user_are_rejected(self):
        with patch("services.simulator_api.auth._jwks", new=AsyncMock(return_value=self.jwks)):
            wrong_issuer = self.client.get("/v1/capabilities", headers={"authorization":f"Bearer {self.token(iss='https://evil.example') }"})
            unknown = self.client.get("/v1/capabilities", headers={"authorization":f"Bearer {self.token(subject=str(uuid4()))}"})
        self.assertEqual(wrong_issuer.status_code, 401)
        self.assertEqual(unknown.status_code, 401)

    def test_allowlisted_users_cannot_read_each_others_jobs(self):
        self.app.state.job_store.initialize()
        job, _ = self.app.state.job_store.submit(BOB, "test-key", "hash", {"label":"private"})
        with patch("services.simulator_api.auth._jwks", new=AsyncMock(return_value=self.jwks)):
            response = self.client.get(f"/v1/jobs/{job.id}", headers={"authorization":f"Bearer {self.token(ALICE)}"})
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
