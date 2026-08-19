from __future__ import annotations

import os
from getpass import getpass

from fyers_apiv3 import fyersModel


def main() -> None:
    app_id = os.getenv("FYERS_APP_ID")
    secret_id = os.getenv("FYERS_SECRET_ID")
    redirect_uri = os.getenv("FYERS_REDIRECT_URI")

    missing = [name for name, value in {
        "FYERS_APP_ID": app_id,
        "FYERS_SECRET_ID": secret_id,
        "FYERS_REDIRECT_URI": redirect_uri,
    }.items() if not value]
    if missing:
        raise SystemExit("Missing environment variables: " + ", ".join(missing))

    session = fyersModel.SessionModel(
        client_id=app_id,
        secret_key=secret_id,
        redirect_uri=redirect_uri,
        response_type="code",
        grant_type="authorization_code",
        state="slo-cpr",
    )

    print("Open this FYERS login URL in your browser:")
    print(session.generate_authcode())
    print("\nAfter authorization, copy only the auth_code value from the redirect URL.")
    auth_code = getpass("Auth code: ").strip()
    if not auth_code:
        raise SystemExit("Auth code is required")

    session.set_token(auth_code)
    response = session.generate_token()
    if not isinstance(response, dict) or response.get("access_token") is None:
        raise SystemExit(f"FYERS token generation failed: {response}")

    token = response["access_token"]
    print("\nFYERS access token generated successfully.")
    print("Set it only in your local shell:")
    print(f'export FYERS_ACCESS_TOKEN="{token}"')
    print("\nDo not commit the token or paste it into chat/GitHub.")


if __name__ == "__main__":
    main()
