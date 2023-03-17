from .exceptions import rblx_opencloudException, InvalidKey, RateLimited, ServiceUnavailable, InsufficientScope
from urllib import parse
import requests, datetime, jwt
from typing import Optional, Union, TYPE_CHECKING
from .user import User
from .experience import Experience

__all__ = (
    "OAuth2App",
    "AccessToken"
)

class PartialAccessToken():
    def __init__(self, client, access_token) -> None:
        self.client: OAuth2App = client
        self.token: str = access_token

    def fetch_userinfo(self) -> User:
        response = requests.get("https://apis.roblox.com/oauth/v1/userinfo", headers={
            "authorization": f"Bearer {self.token}"
        })

        if response.ok: return User(response.json())
        elif response.status_code == 401:
            if response.json()["error"] == "insufficient_scope":
                raise InsufficientScope(response.json()["scope"], f"The access token does not have the required scope:'{response.json()['scope']}'")
        elif response.status_code >= 500: raise ServiceUnavailable("The service is unavailable or has encountered an error.")
        else: raise rblx_opencloudException(f"Unexpected HTTP {response.status_code}")

    
    def fetch_experiences(self) -> list[Experience]:
        response = requests.post("https://apis.roblox.com/oauth/v1/token/resources", data={
            "token": self.token,
            "client_id": self.client.id,
            "client_secret": self.client._OAuth2App__secret
        })

        if response.status_code == 401:
            if response.json()["error"] == "insufficient_scope":
                raise InsufficientScope(response.json()["scope"], f"The access token does not have the required scope:'{response.json()['scope']}'")
        elif response.status_code >= 500: raise ServiceUnavailable("The service is unavailable or has encountered an error.")
        elif not response.ok: raise rblx_opencloudException(f"Unexpected HTTP {response.status_code}")
        
        experiences = []
        for resource in response.json()["resource_infos"]:
            owner = resource["owner"]
            for experience_id in resource["resources"]["universe"]["ids"]:
                experience = Experience(experience_id, self.token)
                experience._Experience__key_type = "BEARER"
                if owner["type"] == "User":
                    experience.owner = User({"id": owner["id"]})
                experiences.append(experience)
        return experiences
    
    def revoke(self):
        self.client.revoke_token(self.token)

class AccessToken(PartialAccessToken):
    def __init__(self, client, payload) -> None:
        super().__init__(client, payload["access_token"])
        self.refresh_token: str = payload["refresh_token"]
        self.scope: list[str] = payload["scope"].split(" ")
        self.expires_at: datetime = datetime.datetime.now() + datetime.timedelta(payload["expires_in"])

    def revoke_refresh_token(self):
        self.client.revoke_token(self.refresh_token)


class OAuth2App():
    def __init__(self, id: int, secret: str, redirect_uri):
        self.id: int = id
        self.redirect_uri: int = redirect_uri
        self.__secret: str = secret

    def generate_uri(self, scope: Union[str, list[str]], state: Optional[str]=None, generate_code=True) -> str:
        params = {
            "client_id": self.id,
            "scope": " ".join(scope) if type(scope) == list else scope,
            "state": state,
            "redirect_uri": self.redirect_uri,
            "response_type": "code" if generate_code else "none"
        }
        return f"https://apis.roblox.com/oauth/v1/authorize?{parse.urlencode({key: value for key, value in params.items() if value is not None})}"

    def from_access_token_string(self, access_token: str) -> PartialAccessToken:
        return PartialAccessToken(self, access_token)

    def exchange_code(self, code: str) -> AccessToken:
        response = requests.post("https://apis.roblox.com/oauth/v1/token", data={
            "client_id": self.id,
            "client_secret": self.__secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
            "code": code
        })
        if response.ok: return AccessToken(self, response.json())
        elif response.status_code == 400: raise InvalidKey("The code, client id, client secret, or redirect uri is invalid.")
        elif response.status_code >= 500: raise ServiceUnavailable("The service is unavailable or has encountered an error.")
        else: raise rblx_opencloudException(f"Unexpected HTTP {response.status_code}")

    def refresh_token(self, refresh_token: str) -> AccessToken:
        response = requests.post("https://apis.roblox.com/oauth/v1/token", data={
            "client_id": self.id,
            "client_secret": self.__secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        })
        if response.ok: return AccessToken(self, response.json())
        elif response.status_code == 400: raise InvalidKey("The code, client id, client secret, or redirect uri is invalid.")
        elif response.status_code >= 500: raise ServiceUnavailable("The service is unavailable or has encountered an error.")
        else: raise rblx_opencloudException(f"Unexpected HTTP {response.status_code}")
    
    def revoke_token(self, token: str):
        response = requests.post("https://apis.roblox.com/oauth/v1/token/revoke", data={
            "token": token,
            "client_id": self.id,
            "client_secret": self.__secret
        })
        if response.ok: return AccessToken(self, response.json())
        elif response.status_code == 400: raise InvalidKey("The code, client id, client secret, or redirect uri is invalid.")
        elif response.status_code >= 500: raise ServiceUnavailable("The service is unavailable or has encountered an error.")
        else: raise rblx_opencloudException(f"Unexpected HTTP {response.status_code}")