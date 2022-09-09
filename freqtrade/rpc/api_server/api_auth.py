import logging
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Union

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.http import HTTPBasic, HTTPBasicCredentials

from freqtrade.rpc.api_server.api_schemas import AccessAndRefreshToken, AccessToken
from freqtrade.rpc.api_server.deps import get_api_config


logger = logging.getLogger(__name__)

ALGORITHM = "HS256"

router_login = APIRouter()


def verify_auth(api_config, username: str, password: str):
    """Verify username/password"""
    return (secrets.compare_digest(username, api_config.get('username')) and
            secrets.compare_digest(password, api_config.get('password')))


httpbasic = HTTPBasic(auto_error=False)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


def get_user_from_token(token, secret_key: str, token_type: str = "access",
                        raise_on_error: bool = True) -> Union[bool, str]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        username: str = payload.get("identity", {}).get('u')
        if username is None:
            if raise_on_error:
                raise credentials_exception
            else:
                return False
        if payload.get("type") != token_type:
            if raise_on_error:
                raise credentials_exception
            else:
                return False

    except jwt.PyJWTError:
        if raise_on_error:
            raise credentials_exception
        else:
            return False
    return username


# This should be reimplemented to better realign with the existing tools provided
# by FastAPI regarding API Tokens
# https://github.com/tiangolo/fastapi/blob/master/fastapi/security/api_key.py
async def get_ws_token(
    ws: WebSocket,
    ws_token: Union[str, None] = Query(..., alias="token"),
    api_config: Dict[str, Any] = Depends(get_api_config)
):
    secret_ws_token = api_config.get('ws_token', 'secret_ws_t0ken.')
    secret_jwt_key = api_config.get('jwt_secret_key', 'super-secret')

    if secrets.compare_digest(secret_ws_token, ws_token):
        # Just return the token if it matches
        return ws_token
    elif user := get_user_from_token(ws_token, secret_jwt_key, raise_on_error=False):
        # If the token is a jwt, and it's valid return the user
        return user
    else:
        logger.info("Denying websocket request")
        # If it doesn't match, close the websocket connection
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)


def create_token(data: dict, secret_key: str, token_type: str = "access") -> str:
    to_encode = data.copy()
    if token_type == "access":
        expire = datetime.utcnow() + timedelta(minutes=15)
    elif token_type == "refresh":
        expire = datetime.utcnow() + timedelta(days=30)
    else:
        raise ValueError()
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": token_type,
    })
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def http_basic_or_jwt_token(form_data: HTTPBasicCredentials = Depends(httpbasic),
                            token: str = Depends(oauth2_scheme),
                            api_config=Depends(get_api_config)):
    if token:
        return get_user_from_token(token, api_config.get('jwt_secret_key', 'super-secret'))
    elif form_data and verify_auth(api_config, form_data.username, form_data.password):
        return form_data.username

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized",
    )


@router_login.post('/token/login', response_model=AccessAndRefreshToken)
def token_login(form_data: HTTPBasicCredentials = Depends(HTTPBasic()),
                api_config=Depends(get_api_config)):

    if verify_auth(api_config, form_data.username, form_data.password):
        token_data = {'identity': {'u': form_data.username}}
        access_token = create_token(token_data, api_config.get('jwt_secret_key', 'super-secret'))
        refresh_token = create_token(token_data, api_config.get('jwt_secret_key', 'super-secret'),
                                     token_type="refresh")
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )


@router_login.post('/token/refresh', response_model=AccessToken)
def token_refresh(token: str = Depends(oauth2_scheme), api_config=Depends(get_api_config)):
    # Refresh token
    u = get_user_from_token(token, api_config.get(
        'jwt_secret_key', 'super-secret'), 'refresh')
    token_data = {'identity': {'u': u}}
    access_token = create_token(token_data, api_config.get('jwt_secret_key', 'super-secret'),
                                token_type="access")
    return {'access_token': access_token}
