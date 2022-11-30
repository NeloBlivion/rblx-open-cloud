from .exceptions import *
import requests, json, datetime
from typing import Union, Iterable
import base64, hashlib

__all__ = (
    "EntryInfo",
    "EntryVersion",
    "ListedEntry",
    "DataStore",
    "SortedEntry"
    "OrderedDataStore"
)

class EntryInfo():
    def __init__(self, version, created, updated, users, metadata) -> None:
        self.version = version
        self.created = datetime.datetime.fromisoformat((created.split("Z")[0]+"0"*6)[0:26])
        self.updated = datetime.datetime.fromisoformat((updated.split("Z")[0]+"0"*6)[0:26])
        self.users = users
        self.metadata = metadata
    
    def __repr__(self) -> str:
        return f"rblxopencloud.EntryInfo(\"{self.version}\", users={self.users}, metadata={self.metadata})"

class EntryVersion():
    def __init__(self, version, deleted, content_length, created, key_created, datastore, key, scope) -> None:
        self.version = version
        self.deleted = deleted
        self.content_length = content_length
        self.created = datetime.datetime.fromisoformat((created.split("Z")[0]+"0"*6)[0:26])
        print(key_created)
        self.key_created = datetime.datetime.fromisoformat((key_created.split("Z")[0]+"0"*6)[0:26])
        self.__datastore = datastore
        self.__key = key
        self.__scope = scope
    
    def __eq__(self, object) -> bool:
        if not isinstance(object, EntryVersion):
            return NotImplemented
        return self.__key == object.__key and self.__scope == object.__scope and self.version == object.version
    
    def get_value(self) -> tuple[Union[str, dict, list, int, float], EntryInfo]:
        """Gets the value of this version. Shortcut for `DataStore.get_version`"""
        if self.__datastore.scope:
            return self.__datastore.get_version(self.__key, self.version)
        else:
            return self.__datastore.get_version(f"{self.__scope}/{self.__key}", self.version)

    def __repr__(self) -> str:
        return f"rblxopencloud.EntryVersion(\"{self.version}\", content_length={self.content_length})"

class ListedEntry():
    def __init__(self, key, scope) -> None:
        self.key = key
        self.scope = scope
    
    def __eq__(self, object) -> bool:
        if not isinstance(object, ListedEntry):
            return NotImplemented
        return self.key == object.key and self.scope == object.scope
    
    def __repr__(self) -> str:
        return f"rblxopencloud.ListedEntry(\"{self.key}\", scope=\"{self.scope}\")"

class DataStore():
    def __init__(self, name, universe, api_key, created, scope):
        self.name = name
        self.__api_key = api_key
        self.scope = scope
        self.universe = universe
        if created: self.created = datetime.datetime.fromisoformat((created.split("Z")[0]+"0"*6)[0:26])
        else: self.created = None
    
    def __repr__(self) -> str:
        return f"rblxopencloud.DataStore(\"{self.name}\", scope=\"{self.scope}\", universe={repr(self.universe)})"
    
    def __str__(self) -> str:
        return self.name

    def list_keys(self, prefix: str="", limit: Union[None, int]=None) -> Iterable[ListedEntry]:
        """Returns an `Iterable` of keys in the database and scope, optionally matching a prefix. Will return keys from all scopes if `DataStore.scope` is `None`. The example below would list all versions, along with their value.
                
        ```py
            for key in datastore.list_keys():
                print(key.key, key.scope)
        ```

        You can simply convert it to a list by putting it in the list function:

        ```py
            list(datastore.list_versions())
        ```"""
        nextcursor = ""
        yields = 0
        while limit == None or yields < limit:
            response = requests.get(f"https://apis.roblox.com/datastores/v1/universes/{self.universe.id}/standard-datastores/datastore/entries",
                headers={"x-api-key": self.__api_key}, params={
                "datastoreName": self.name,
                "scope": self.scope,
                "AllScopes": not self.scope,
                "prefix": prefix,
                "cursor": nextcursor if nextcursor else None
            })
            if response.status_code == 401 or response.status_code == 403: raise InvalidKey("Your key may have expired, or may not have permission to access this resource.")
            elif response.status_code == 404: raise NotFound("The datastore you're trying to access does not exist.")
            elif response.status_code == 429: raise RateLimited("You're being rate limited.")
            elif response.status_code >= 500: raise ServiceUnavailable("The service is unavailable or has encountered an error.")
            elif not response.ok: raise rblx_opencloudException(f"Unexpected HTTP {response.status_code}")
            
            data = response.json()
            for key in data["keys"]:
                yields += 1
                yield ListedEntry(key["key"], key["scope"])
                if limit == None or yields >= limit: break
            nextcursor = data.get("nextPageCursor")
            if not nextcursor: break
    
    def get(self, key: str) -> tuple[Union[str, dict, list, int, float], EntryInfo]:
        """Gets the value of a key. If `DataStore.scope` is `None` then `key` must be formatted like `scope/key`."""
        try:
            if not self.scope: scope, key = key.split("/", maxsplit=1)
        except(ValueError):
            raise ValueError("a scope and key seperated by a forward slash is required for DataStore without a scope.")
        response = requests.get(f"https://apis.roblox.com/datastores/v1/universes/{self.universe.id}/standard-datastores/datastore/entries/entry",
            headers={"x-api-key": self.__api_key}, params={
                "datastoreName": self.name,
                "scope": self.scope if self.scope else scope,
                "entryKey": key
            })

        if response.status_code == 200:
            try: metadata = json.loads(response.headers["roblox-entry-attributes"])
            except(KeyError): metadata = {}
            try: userids = json.loads(response.headers["roblox-entry-userids"])
            except(KeyError): userids = []
            
            return json.loads(response.text), EntryInfo(response.headers["roblox-entry-version"], response.headers["roblox-entry-created-time"],
    response.headers["roblox-entry-version-created-time"], userids, metadata)
        elif response.status_code == 204: return None
        elif response.status_code == 401: raise InvalidKey("Your key may have expired, or may not have permission to access this resource.")
        elif response.status_code == 404: raise NotFound(f"The key {key} does not exist.")
        elif response.status_code == 429: raise RateLimited("You're being rate limited.")
        elif response.status_code >= 500: raise ServiceUnavailable("The service is unavailable or has encountered an error.")
        else: raise rblx_opencloudException(f"Unexpected HTTP {response.status_code}")

    def set(self, key: str, value: Union[str, dict, list, int, float], users:list=None, metadata:dict={}, exclusive_create:bool=False, previous_version:Union[None, str]=None) -> EntryVersion:
        """Sets the value of a key. If `DataStore.scope` is `None` then `key` must be formatted like `scope/key`."""
        if previous_version and exclusive_create: raise ValueError("previous_version and exclusive_create can not both be set")
        try:
            if not self.scope: scope, key = key.split("/", maxsplit=1)
        except(ValueError):
            raise ValueError("a scope and key seperated by a forward slash is required for DataStore without a scope.")
        if users == None: users = []
        data = json.dumps(value)

        response = requests.post(f"https://apis.roblox.com/datastores/v1/universes/{self.universe.id}/standard-datastores/datastore/entries/entry",
            headers={"x-api-key": self.__api_key, "roblox-entry-userids": json.dumps(users), "roblox-entry-attributes": json.dumps(metadata),
            "content-md5": base64.b64encode(hashlib.md5(data.encode()).digest())}, data=data, params={
                "datastoreName": self.name,
                "scope": self.scope if self.scope else scope,
                "entryKey": key,
                "exclusiveCreate": exclusive_create,
                "matchVersion": previous_version
            })
        
        if response.status_code == 200:
            data = json.loads(response.text)
            return EntryVersion(data["version"], data["deleted"], data["contentLength"], data["createdTime"], data["objectCreatedTime"], self, key, self.scope if self.scope else scope)
        elif response.status_code == 401: raise InvalidKey("Your key may have expired, or may not have permission to access this resource.")
        elif response.status_code == 429: raise RateLimited("You're being rate limited.")
        elif response.status_code >= 500: raise ServiceUnavailable("The service is unavailable or has encountered an error.")
        elif response.status_code == 412:
            try: metadata = json.loads(response.headers["roblox-entry-attributes"])
            except(KeyError): metadata = {}
            try: userids = json.loads(response.headers["roblox-entry-userids"])
            except(KeyError): userids = []

            if exclusive_create:
                error = "An entry already exists with the provided key and scope"
            elif previous_version:
                error = f"The current version is not '{previous_version}'"
            else:
                error = "A Precondition Failed"

            raise PreconditionFailed(json.loads(response.text), EntryInfo(response.headers["roblox-entry-version"], response.headers["roblox-entry-created-time"],
    response.headers["roblox-entry-version-created-time"], userids, metadata), error)
        else: raise rblx_opencloudException(f"Unexpected HTTP {response.status_code}")

    def increment(self, key: str, increment: Union[int, float], users:list=None, metadata:dict={}) -> tuple[Union[str, dict, list, int, float], EntryInfo]:
        """Increments the value of a key. If `DataStore.scope` is `None` then `key` must be formatted like `scope/key`."""
        try:
            if not self.scope: scope, key = key.split("/", maxsplit=1)
        except(ValueError):
            raise ValueError("a scope and key seperated by a forward slash is required for DataStore without a scope.")
        if users == None: users = []

        response = requests.post(f"https://apis.roblox.com/datastores/v1/universes/{self.universe.id}/standard-datastores/datastore/entries/entry/increment",
            headers={"x-api-key": self.__api_key, "roblox-entry-userids": json.dumps(users), "roblox-entry-attributes": json.dumps(metadata)}, params={
                "datastoreName": self.name,
                "scope": self.scope if self.scope else scope,
                "entryKey": key,
                "incrementBy": increment
            })

        if response.status_code == 200:
            try: metadata = json.loads(response.headers["roblox-entry-attributes"])
            except(KeyError): metadata = {}
            try: userids = json.loads(response.headers["roblox-entry-userids"])
            except(KeyError): userids = []
            
            return json.loads(response.text), EntryInfo(response.headers["roblox-entry-version"], response.headers["roblox-entry-created-time"],
    response.headers["roblox-entry-version-created-time"], userids, metadata)
        elif response.status_code == 401: raise InvalidKey("Your key may have expired, or may not have permission to access this resource.")
        elif response.status_code == 429: raise RateLimited("You're being rate limited.")
        elif response.status_code >= 500: raise ServiceUnavailable("The service is unavailable or has encountered an error.")
        else: raise rblx_opencloudException(f"Unexpected HTTP {response.status_code}")
    
    def remove(self, key: str) -> None:
        """Removes a key. If `DataStore.scope` is `None` then `key` must be formatted like `scope/key`."""
        try:
            if not self.scope: scope, key = key.split("/", maxsplit=1)
        except(ValueError):
            raise ValueError("a scope and key seperated by a forward slash is required for DataStore without a scope.")
        response = requests.delete(f"https://apis.roblox.com/datastores/v1/universes/{self.universe.id}/standard-datastores/datastore/entries/entry",
            headers={"x-api-key": self.__api_key}, params={
                "datastoreName": self.name,
                "scope": self.scope if self.scope else scope,
                "entryKey": key
            })

        if response.status_code == 204: return None
        elif response.status_code == 401: raise InvalidKey("Your key may have expired, or may not have permission to access this resource.")
        elif response.status_code == 404: raise NotFound(f"The key {key} does not exist.")
        elif response.status_code == 429: raise RateLimited("You're being rate limited.")
        elif response.status_code >= 500: raise ServiceUnavailable("The service is unavailable or has encountered an error.")
        else: raise rblx_opencloudException(f"Unexpected HTTP {response.status_code}")
    
    def list_versions(self, key: str, after: datetime.datetime=None, before: datetime.datetime=None, limit: Union[None, int]=None, descending: bool=True) -> Iterable[EntryVersion]:
        """Returns an Iterable of previous versions of a key. If `DataStore.scope` is `None` then `key` must be formatted like `scope/key`. The example below would list all versions, along with their value.
                
        ```py
            for version in datastore.list_versions("key-name"):
                print(version, version.get_value())
        ```

        You can simply convert it to a list by putting it in the list function:

        ```py
            list(datastore.list_versions("key-name"))
        ```"""
        try:
            if not self.scope: scope, key = key.split("/", maxsplit=1)
        except(ValueError):
            raise ValueError("a scope and key seperated by a forward slash is required for DataStore without a scope.")
        nextcursor = ""
        yields = 0
        while limit == None or yields < limit:
            response = requests.get(f"https://apis.roblox.com/datastores/v1/universes/{self.universe.id}/standard-datastores/datastore/entries/entry/versions",
                headers={"x-api-key": self.__api_key}, params={
                    "datastoreName": self.name,
                    "scope": self.scope if self.scope else scope,
                    "entryKey": key,
                    "sortOrder": "Descending" if descending else "Ascending",
                    "cursor": nextcursor if nextcursor else None,
                    "startTime": after.isoformat() if after else None,
                    "endTime": before.isoformat() if before else None
                })
            
            if response.status_code == 401: raise InvalidKey("Your key may have expired, or may not have permission to access this resource.")
            elif response.status_code == 404: raise NotFound("The datastore you're trying to access does not exist.")
            elif response.status_code == 429: raise RateLimited("You're being rate limited.")
            elif response.status_code >= 500: raise ServiceUnavailable("The service is unavailable or has encountered an error.")
            elif not response.ok: raise rblx_opencloudException(f"Unexpected HTTP {response.status_code}")

            data = response.json()
            for version in data["versions"]:
                yields += 1
                yield EntryVersion(version["version"], version["deleted"], version["contentLength"], version["createdTime"], version["objectCreatedTime"], self, key, self.scope if self.scope else scope)
                if limit == None or yields >= limit: break
            nextcursor = data.get("nextPageCursor")
            if not nextcursor: break

    def get_version(self, key: str, version: str) -> tuple[Union[str, dict, list, int, float], EntryInfo]:
        """Gets the value of a key version. If `DataStore.scope` is `None` then `key` must be formatted like `scope/key`."""
        try:
            if not self.scope: scope, key = key.split("/", maxsplit=1)
        except(ValueError):
            raise ValueError("a scope and key seperated by a forward slash is required for DataStore without a scope.") 
        response = requests.get(f"https://apis.roblox.com/datastores/v1/universes/{self.universe.id}/standard-datastores/datastore/entries/entry/versions/version",
            headers={"x-api-key": self.__api_key}, params={
                "datastoreName": self.name,
                "scope": self.scope if self.scope else scope,
                "entryKey": key,
                "versionId": version
            })

        if response.status_code == 200:
            try: metadata = json.loads(response.headers["roblox-entry-attributes"])
            except(KeyError): metadata = {}
            try: userids = json.loads(response.headers["roblox-entry-userids"])
            except(KeyError): userids = []
            
            return json.loads(response.text), EntryInfo(response.headers["roblox-entry-version"], response.headers["roblox-entry-created-time"],
                response.headers["roblox-entry-version-created-time"], userids, metadata)
        elif response.status_code == 204: return None
        elif response.status_code == 401: raise InvalidKey("Your key may have expired, or may not have permission to access this resource.")
        elif response.status_code == 404: raise NotFound(f"The key {key} does not exist.")
        elif response.status_code == 429: raise RateLimited("You're being rate limited.")
        elif response.status_code >= 500: raise ServiceUnavailable("The service is unavailable or has encountered an error.")
        else: raise rblx_opencloudException(f"Unexpected HTTP {response.status_code}")

class SortedEntry():
    def __init__(self, key: str, value: int, scope: str="global") -> None:
        self.key: str = key
        self.scope: str = scope
        self.value: int = value
    
    def __eq__(self, object) -> bool:
        if not isinstance(object, SortedEntry):
            return NotImplemented
        return self.key == object.key and self.scope == object.scope and self.value == object.value
    
    def __repr__(self) -> str:
        return f"rblxopencloud.SortedEntry(\"{self.key}\", value=\"{self.value}\")"

class OrderedDataStore():
    def __init__(self, name, universe, api_key, scope):
        self.name = name
        self.__api_key = api_key
        self.scope = scope
        self.universe = universe
    
    def __repr__(self) -> str:
        return f"rblxopencloud.OrderedDataStore(\"{self.name}\", scope=\"{self.scope}\", universe={repr(self.universe)})"
    
    def __str__(self) -> str:
        return self.name
    
    def sort_keys(self, descending: bool=True, limit: Union[None, int]=None) -> Iterable[SortedEntry]:
        if not self.scope:
            raise ValueError("")
        nextcursor = ""
        yields = 0
        while limit == None or yields < limit:
            response = requests.get(f"https://apis.roblox.com/datastores/v2/universes/{self.universe.id}/orderedDatastores/{base64.b64encode(self.name.encode()).decode()}/scopes/{base64.b64encode(self.scope.encode()).decode()}/entries",
                headers={"x-api-key": self.__api_key}, params={
                "max_page_size": limit if limit and limit < 100 else 100,
                "order_by": "desc" if descending else None,
                "page_token": nextcursor if nextcursor else None
            })
            if response.status_code == 401 or response.status_code == 403: raise InvalidKey("Your key may have expired, or may not have permission to access this resource.")
            elif response.status_code == 404: raise NotFound("The datastore you're trying to access does not exist.")
            elif response.status_code == 429: raise RateLimited("You're being rate limited.")
            elif response.status_code >= 500: raise ServiceUnavailable("The service is unavailable or has encountered an error.")
            elif not response.ok: raise rblx_opencloudException(f"Unexpected HTTP {response.status_code}")
            
            data = response.json()
            for key in data["entries"]:
                yields += 1
                yield SortedEntry(key["target"], key["value"], self.scope)
                if limit != None and yields >= limit: break
            nextcursor = data.get("lastEvaluatedKey")
            if not nextcursor: break
    
    def get(self, key: str) -> int:
        try:
            if not self.scope: scope, key = key.split("/", maxsplit=1)
        except(ValueError):
            raise ValueError("a scope and key seperated by a forward slash is required for OrderedDataStore without a scope.")
        scope = base64.b64encode(self.scope.encode() if self.scope else scope.encode()).decode()
        response = requests.get(f"https://apis.roblox.com/datastores/v2/universes/{self.universe.id}/orderedDatastores/{base64.b64encode(self.name.encode()).decode()}/scopes/{scope}/entries/{base64.b64encode(key.encode()).decode()}",
            headers={"x-api-key": self.__api_key})
        
        if response.status_code == 200: return int(response.json()["value"])
        elif response.status_code == 401: raise InvalidKey("Your key may have expired, or may not have permission to access this resource.")
        elif response.status_code == 404: raise NotFound(f"The key {key} does not exist.")
        elif response.status_code == 429: raise RateLimited("You're being rate limited.")
        elif response.status_code >= 500: raise ServiceUnavailable("The service is unavailable or has encountered an error.")
        else: raise rblx_opencloudException(f"Unexpected HTTP {response.status_code}")

    def create(self, key: str, value: int) -> int:
        try:
            if not self.scope: scope, key = key.split("/", maxsplit=1)
        except(ValueError):
            raise ValueError("a scope and key seperated by a forward slash is required for OrderedDataStore without a scope.")
        
        scope = base64.b64encode(self.scope.encode() if self.scope else scope.encode()).decode()
        response = requests.post(f"https://apis.roblox.com/datastores/v2/universes/{self.universe.id}/orderedDatastores/{base64.b64encode(self.name.encode()).decode()}/scopes/{scope}/entries/{base64.b64encode(key.encode()).decode()}",
            headers={"x-api-key": self.__api_key}, data=str(value))
        
        if response.status_code == 200: return int(response.json()["value"])
        elif response.status_code == 401: raise InvalidKey("Your key may have expired, or may not have permission to access this resource.")
        elif response.status_code == 404: raise NotFound(f"The key {key} does not exist.")
        elif response.status_code == 429: raise RateLimited("You're being rate limited.")
        elif response.status_code >= 500: raise ServiceUnavailable("The service is unavailable or has encountered an error.")
        else: raise rblx_opencloudException(f"Unexpected HTTP {response.status_code}")
        
    def update(self, key: str, value: int, previous_value: Union[int, None]=None) -> int:

        try:
            if not self.scope: scope, key = key.split("/", maxsplit=1)
        except(ValueError):
            raise ValueError("a scope and key seperated by a forward slash is required for OrderedDataStore without a scope.")
        
        scope = base64.b64encode(self.scope.encode() if self.scope else scope.encode()).decode()
        response = requests.patch(f"https://apis.roblox.com/datastores/v2/universes/{self.universe.id}/orderedDatastores/{base64.b64encode(self.name.encode()).decode()}/scopes/{scope}/entries/{base64.b64encode(key.encode()).decode()}",
            headers={"x-api-key": self.__api_key}, params={
                "eTag": str(previous_value),
                "allow_missing": not previous_value
            }, data=str(value))
        
        if response.status_code == 200: return int(response.json()["value"])
        elif response.status_code == 401: raise InvalidKey("Your key may have expired, or may not have permission to access this resource.")
        elif response.status_code == 404: raise NotFound(f"The key {key} does not exist.")
        elif response.status_code == 429: raise RateLimited("You're being rate limited.")
        elif response.status_code >= 500: raise ServiceUnavailable("The service is unavailable or has encountered an error.")
        else: raise rblx_opencloudException(f"Unexpected HTTP {response.status_code}")
  
    def remove(self, key: str) -> None:
        try:
            if not self.scope: scope, key = key.split("/", maxsplit=1)
        except(ValueError):
            raise ValueError("a scope and key seperated by a forward slash is required for OrderedDataStore without a scope.")
        
        scope = base64.b64encode(self.scope.encode() if self.scope else scope.encode()).decode()
        response = requests.delete(f"https://apis.roblox.com/datastores/v2/universes/{self.universe.id}/orderedDatastores/{base64.b64encode(self.name.encode()).decode()}/scopes/{scope}/entries/{base64.b64encode(key.encode()).decode()}",
            headers={"x-api-key": self.__api_key})
        
        if response.status_code == 204: return None
        elif response.status_code == 401: raise InvalidKey("Your key may have expired, or may not have permission to access this resource.")
        elif response.status_code == 404: raise NotFound(f"The key {key} does not exist.")
        elif response.status_code == 429: raise RateLimited("You're being rate limited.")
        elif response.status_code >= 500: raise ServiceUnavailable("The service is unavailable or has encountered an error.")
        else: raise rblx_opencloudException(f"Unexpected HTTP {response.status_code}")

"https://apis.roblox.com/datastores/v2/universes/:universe/orderedDatastores/:datastore/scopes/:scope/entries/:entry"