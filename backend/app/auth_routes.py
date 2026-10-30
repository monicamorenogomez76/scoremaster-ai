"""HTTP routes for accounts: email/password and, only when configured, Google (OIDC with PKCE)."""
from __future__ import annotations

import base64
import hashlib
import os
import logging
import secrets
from datetime import timedelta
from typing import Optional
from urllib.parse import urlencode

import httpx
from authlib.jose import JsonWebKey, jwt
from authlib.jose.errors import JoseError
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field, field_validator

from backend.application.accounts import AccountRepository, User
from backend.application.auth import (
    RESET_MINUTES, SESSION_DAYS, AuthService, InvalidCredentials, InvalidRegistration, InvalidResetLink, LoginLimiter,
    SignedIn, TooManyAttempts,
)
from backend.application.mail import Mailer
from backend.app.dependencies import SESSION_COOKIE, authenticated_user, get_account_repository, get_mailer, is_admin
from backend.app.i18n import language, translate

router = APIRouter(prefix="/auth")
LIMITER = LoginLimiter()
RESET_LIMITER = LoginLimiter(3, timedelta(hours=1))
RESET_SENT = ("Si hay una cuenta con ese email, te hemos enviado un enlace para elegir una contraseña nueva. "
              f"Caduca en {RESET_MINUTES} minutos.")
OAUTH_COOKIE = "scoremaster_oauth"
GOOGLE_AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_KEYS = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ["https://accounts.google.com", "accounts.google.com"]


class RegisterBody(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)
    display_name: str = Field("", max_length=100)


class ProfileBody(BaseModel):
    display_name: str

    @field_validator("display_name")
    @classmethod
    def visible_name(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= 100:
            raise ValueError("El nombre debe tener entre 1 y 100 caracteres.")
        return value


class ForgotBody(BaseModel):
    email: str = Field(max_length=254)


class ResetBody(BaseModel):
    token: str = Field(max_length=100)
    password: str = Field(max_length=256)


class LoginBody(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)


def cookie_secure() -> bool:
    """Secure cookies in production (HTTPS); SESSION_COOKIE_SECURE overrides it for local tests."""
    explicit = os.environ.get("SESSION_COOKIE_SECURE")
    if explicit is not None:
        return explicit == "1"
    return os.environ.get("APP_ENV") == "production"


def google_enabled() -> bool:
    return bool(os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET"))


def _service(accounts: AccountRepository = Depends(get_account_repository)) -> AuthService:
    return AuthService(accounts, limiter=LIMITER, reset_limiter=RESET_LIMITER)


def _ip(request: Request) -> str:
    return request.client.host if request.client else ""


def _user(user: User, display_name: Optional[str] = None) -> dict:
    return {"email": user.email, "display_name": user.display_name if display_name is None else display_name,
            "is_admin": is_admin(user)}


def _public(signed_in: SignedIn) -> dict:
    return {"user": _user(signed_in.user), "csrf_token": signed_in.csrf_token}


def _with_session(response: Response, signed_in: SignedIn) -> Response:
    response.set_cookie(SESSION_COOKIE, signed_in.token, max_age=SESSION_DAYS * 24 * 3600, path="/",
                        httponly=True, samesite="lax", secure=cookie_secure())
    return response


@router.post("/register", status_code=201)
def register(body: RegisterBody, request: Request, service: AuthService = Depends(_service)):
    try:
        signed_in = service.register(body.email, body.password, body.display_name, _ip(request))
    except InvalidRegistration as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return _with_session(JSONResponse(_public(signed_in), status_code=201), signed_in)


@router.post("/login")
def login(body: LoginBody, request: Request, service: AuthService = Depends(_service)):
    try:
        signed_in = service.login(body.email, body.password, _ip(request))
    except TooManyAttempts as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from None
    except InvalidCredentials as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from None
    return _with_session(JSONResponse(_public(signed_in)), signed_in)


@router.post("/logout", status_code=204, dependencies=[Depends(authenticated_user)])
def logout(request: Request, service: AuthService = Depends(_service)):
    service.logout(request.cookies.get(SESSION_COOKIE, ""))
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="lax", secure=cookie_secure())
    return response


@router.get("/me")
def me(request: Request, service: AuthService = Depends(_service)):
    current = service.current(request.cookies.get(SESSION_COOKIE, ""))
    if current is None:
        raise HTTPException(status_code=401, detail="Inicia sesión para continuar.")
    user, session = current
    return {"user": _user(user), "csrf_token": session.csrf_token}


@router.patch("/me")
def update_me(body: ProfileBody, user: User = Depends(authenticated_user),
              accounts: AccountRepository = Depends(get_account_repository)):
    """The name shown in the app (Configuración); the email cannot be changed here."""
    accounts.rename_user(user.id, body.display_name)
    return {"user": _user(user, body.display_name)}


@router.get("/config")
def config(mailer: Optional[Mailer] = Depends(get_mailer)):
    return {"google_enabled": google_enabled(), "demo_email": os.environ.get("DEMO_USER_EMAIL") or None,
            "password_reset_enabled": mailer is not None}


# The recovery email in the language of the interface it was asked from.
RESET_EMAIL = {
    "es": ("ScoreMaster: elige una contraseña nueva",
           "Hola, {name}:\n\nPara elegir una contraseña nueva en ScoreMaster abre este enlace:\n\n{link}\n\n"
           "Caduca en {minutes} minutos y solo sirve una vez. Si no lo has pedido tú, ignora este correo: tu contraseña no cambia.\n"),
    "en": ("ScoreMaster: choose a new password",
           "Hello {name},\n\nTo choose a new password in ScoreMaster open this link:\n\n{link}\n\n"
           "It expires in {minutes} minutes and works only once. If you did not ask for it, ignore this email: your password "
           "does not change.\n"),
}


def _send_reset(service: AuthService, mailer: Mailer, email: str, base_url: str, ip: str, lang: str = "es") -> None:
    """After the answer, so its timing does not tell whether the account exists. The demo account, whose password
    is public and whose mailbox does not exist, never gets a link."""
    if (email or "").strip().lower() == (os.environ.get("DEMO_USER_EMAIL") or "").lower():
        return
    requested = service.request_password_reset(email, ip)
    if requested is None:
        return
    user, token = requested
    # The token goes in the fragment: the browser never sends it to a server, so no log or Referer keeps it.
    link = f"{base_url.rstrip('/')}/#reset={token}"
    subject, text = RESET_EMAIL[lang]
    try:
        mailer.send(user.email, subject, text.format(name=user.display_name, link=link, minutes=RESET_MINUTES))
    except Exception:
        logging.getLogger("uvicorn.error").warning("No se pudo enviar el correo de recuperación.", exc_info=True)


@router.post("/password/forgot", status_code=202)
def forgot_password(body: ForgotBody, request: Request, tasks: BackgroundTasks,
                    service: AuthService = Depends(_service), mailer: Optional[Mailer] = Depends(get_mailer)):
    if mailer is None:
        raise HTTPException(status_code=404, detail="La recuperación de la contraseña no está disponible.")
    # APP_BASE_URL in production: a link built from the Host header could point to another site.
    base_url = os.environ.get("APP_BASE_URL") or str(request.base_url)
    lang = language(request.headers.get("accept-language"))
    tasks.add_task(_send_reset, service, mailer, body.email, base_url, _ip(request), lang)
    return {"detail": translate(RESET_SENT, lang)}


@router.post("/password/reset")
def reset_password(body: ResetBody, request: Request, service: AuthService = Depends(_service)):
    try:
        signed_in = service.reset_password(body.token, body.password, _ip(request))
    except (InvalidResetLink, InvalidRegistration) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return _with_session(JSONResponse(_public(signed_in)), signed_in)


def _redirect_uri(request: Request) -> str:
    return os.environ.get("GOOGLE_REDIRECT_URI") or str(request.url_for("google_callback"))


@router.get("/google/start")
def google_start(request: Request):
    if not google_enabled():
        raise HTTPException(status_code=404, detail="Google no está configurado.")
    state, verifier = secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    query = urlencode({"client_id": os.environ["GOOGLE_CLIENT_ID"], "redirect_uri": _redirect_uri(request),
                       "response_type": "code", "scope": "openid email profile", "state": state,
                       "code_challenge": challenge, "code_challenge_method": "S256", "prompt": "select_account"})
    response = RedirectResponse(GOOGLE_AUTHORIZE + "?" + query, status_code=302)
    response.set_cookie(OAUTH_COOKIE, state + "." + verifier, max_age=600, path="/auth/google",
                        httponly=True, samesite="lax", secure=cookie_secure())
    return response


def exchange_google_code(code: str, verifier: str, redirect_uri: str) -> dict:
    """Trade the code for an ID token and verify its signature, issuer and audience."""
    client_id = os.environ["GOOGLE_CLIENT_ID"]
    token = httpx.post(GOOGLE_TOKEN, data={
        "code": code, "client_id": client_id, "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
        "redirect_uri": redirect_uri, "grant_type": "authorization_code", "code_verifier": verifier}, timeout=10)
    token.raise_for_status()
    keys = JsonWebKey.import_key_set(httpx.get(GOOGLE_KEYS, timeout=10).json())
    claims = jwt.decode(token.json()["id_token"], keys, claims_options={
        "iss": {"essential": True, "values": GOOGLE_ISSUERS}, "aud": {"essential": True, "value": client_id}})
    claims.validate()
    return dict(claims)


@router.get("/google/callback", name="google_callback")
def google_callback(request: Request, code: str = "", state: str = "", service: AuthService = Depends(_service)):
    if not google_enabled():
        raise HTTPException(status_code=404, detail="Google no está configurado.")
    stored_state, _, verifier = request.cookies.get(OAUTH_COOKIE, "").partition(".")
    if not code or not stored_state or not secrets.compare_digest(stored_state, state):
        raise HTTPException(status_code=400, detail="La respuesta de Google no es válida. Vuelve a intentarlo.")
    try:
        claims = exchange_google_code(code, verifier, _redirect_uri(request))
        signed_in = service.google(claims["sub"], claims.get("email", ""), bool(claims.get("email_verified")),
                                   claims.get("name", ""), _ip(request))
    except (InvalidCredentials, JoseError, KeyError, httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="No se pudo entrar con Google.") from exc
    response = _with_session(RedirectResponse("/", status_code=302), signed_in)
    response.delete_cookie(OAUTH_COOKIE, path="/auth/google")
    return response
