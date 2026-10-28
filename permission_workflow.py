"""Generic SharePoint assignment -> group -> user -> profile workflow.

Python 3.10+. Network authentication is injected; the core uses only the stdlib.
This enumerates membership under an explicit grant policy, not effective access.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Iterable
from urllib.parse import quote, urljoin, urlsplit


class ResolutionError(RuntimeError):
    """A diagnostic code without response bodies, credentials or request URLs."""


@dataclass(frozen=True)
class Principal:
    kind: int
    key: str  # Scoped SharePoint ID or directory identifier; not a person's name.
    login: str = ""
    display_name: str | None = None
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    sp_id: int | None = None

    @classmethod
    def from_sharepoint(cls, member: dict, scope: str) -> Principal:
        try:
            kind = int(member["PrincipalType"])
            principal_id = int(member["Id"])
        except (KeyError, TypeError, ValueError):
            raise ResolutionError("invalid_sharepoint_principal") from None
        return cls(kind, f"sp:{scope}:{principal_id}", member.get("LoginName") or "",
                   member.get("Title"), member.get("Email"), sp_id=principal_id)


def collection(value: Any) -> list:
    """Parse an already complete inline collection; refuse deferred/truncated data."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict) and isinstance(value.get("results"), list):
        if value.get("__next") or value.get("@odata.nextLink"):
            raise ResolutionError("inline_collection_requires_pagination")
        return value["results"]
    raise ResolutionError("missing_or_invalid_collection")


def view_items_policy(assignment: dict) -> bool:
    """Candidate view grant: union of role masks contains ViewListItems (bit 0).

    Explicitly NOT a complete permission check for downloading/reading every file
    version. Missing masks are errors, not exclusions. Role names are not used.
    """
    roles = collection(assignment.get("RoleDefinitionBindings"))
    mask = 0
    for role in roles:
        try:
            permissions = role["BasePermissions"]
            low, high = int(permissions["Low"]), int(permissions["High"])
        except (KeyError, TypeError, ValueError):
            raise ResolutionError("missing_base_permissions") from None
        mask |= ((high & 0xFFFFFFFF) << 32) | (low & 0xFFFFFFFF)
    return bool(mask & 1)


def all_assignments_policy(assignment: dict) -> bool:
    """Diagnostic inventory of every assignment, including Limited Access."""
    return True


class SharePointRest:
    """Adapter for an existing authenticated requests-compatible session.

    TLS/proxy/certificate configuration belongs to the injected session. Session
    redirects are disabled; SSO redirects must be handled before this adapter.
    The instance must be bound to the web containing the file.
    """

    def __init__(self, session: Any, site_url: str, *, timeout: int = 30,
                 max_pages: int = 1000, resource_path_api: bool = False):
        parsed = urlsplit(site_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError("site_url must be an HTTPS web URL without query/fragment")
        if parsed.username or parsed.password:
            raise ValueError("credentials do not belong in site_url")
        self.session, self.site_url = session, site_url.rstrip("/")
        self.timeout, self.max_pages = timeout, max_pages
        self.resource_path_api = resource_path_api
        self.origin = self._origin(self.site_url)

    @staticmethod
    def _origin(url: str) -> tuple:
        parsed = urlsplit(url)
        return parsed.scheme, parsed.hostname, parsed.port or 443

    def _url(self, path: str) -> str:
        return self.site_url + "/_api/" + path.lstrip("/")

    def _get(self, url: str, params: dict | None = None) -> dict:
        parsed = urlsplit(url)
        if self._origin(url) != self.origin or parsed.username or parsed.password:
            raise ResolutionError("cross_origin_request_rejected")
        try:
            response = self.session.get(
                url, params=params, headers={"Accept": "application/json;odata=verbose"},
                timeout=self.timeout, allow_redirects=False,
            )
            if response.status_code != 200:
                raise ResolutionError(f"sharepoint_http_{response.status_code}")
            data = response.json()
        except ResolutionError:
            raise
        except Exception:
            raise ResolutionError("sharepoint_transport_or_json_error") from None
        if not isinstance(data, dict) or "error" in data or "odata.error" in data:
            raise ResolutionError("sharepoint_error_payload")
        return data

    def _object(self, url: str, params: dict | None = None) -> dict:
        data = self._get(url, params)
        obj = data.get("d", data)
        if not isinstance(obj, dict):
            raise ResolutionError("invalid_object_payload")
        return obj

    def _list(self, url: str, params: dict | None = None) -> list[dict]:
        result, seen = [], set()
        for _ in range(self.max_pages):
            if url in seen:
                raise ResolutionError("pagination_cycle")
            seen.add(url)
            data = self._get(url, params)
            obj = data.get("d", data)
            if not isinstance(obj, dict):
                raise ResolutionError("invalid_collection_payload")
            rows = obj.get("results", obj.get("value"))
            if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
                raise ResolutionError("invalid_collection_payload")
            result.extend(rows)
            next_link = obj.get("__next") or obj.get("@odata.nextLink") or obj.get("odata.nextLink")
            if not next_link:
                return result
            if not isinstance(next_link, str):
                raise ResolutionError("invalid_next_link")
            url, params = urljoin(url, next_link), None
        raise ResolutionError("pagination_limit")

    def file_assignments(self, server_relative_url: str) -> list[dict]:
        if not server_relative_url.startswith("/"):
            raise ValueError("a server-relative path beginning with '/' is required")
        params = {"$select": "Id,HasUniqueRoleAssignments"}
        if self.resource_path_api:
            item = self._url("web/GetFileByServerRelativePath(decodedUrl=@p)/ListItemAllFields")
            params["@p"] = "'" + server_relative_url.replace("'", "''") + "'"
            # Retain the parameter in later navigation requests, including next links.
            # Encode once here so no separate query parameter can be lost.
            from urllib.parse import urlencode
            item += "?" + urlencode({"@p": params.pop("@p")})
        else:
            if "#" in server_relative_url or "%" in server_relative_url:
                raise ResolutionError("ambiguous_legacy_path_use_resource_path_api")
            literal = quote(server_relative_url.replace("'", "''"), safe="/")
            item = self._url(f"web/GetFileByServerRelativeUrl('{literal}')/ListItemAllFields")
        info = self._object(item, params)
        unique = info.get("HasUniqueRoleAssignments")
        if not isinstance(unique, bool):
            raise ResolutionError("missing_inheritance_flag")
        # Navigation belongs before an alias query string.
        item_path, separator, item_query = item.partition("?")
        scope = item_path if unique else item_path + "/FirstUniqueAncestorSecurableObject"
        assignment_url = scope + "/RoleAssignments" + (separator + item_query if separator else "")
        # Keep navigation properties expanded, and explicitly request permission masks.
        assignments = self._list(assignment_url, {
            "$expand": "Member,RoleDefinitionBindings",
            "$select": "PrincipalId,Member/Id,Member/PrincipalType,Member/LoginName,"
                       "Member/Title,Member/Email,RoleDefinitionBindings/Id,"
                       "RoleDefinitionBindings/Name,RoleDefinitionBindings/BasePermissions",
        })
        for assignment in assignments:
            bindings = assignment.get("RoleDefinitionBindings")
            if isinstance(bindings, dict) and bindings.get("__next"):
                assignment["RoleDefinitionBindings"] = self._list(
                    urljoin(assignment_url, bindings["__next"]))
        return assignments

    def group_members(self, principal: Principal) -> list[Principal]:
        if principal.kind != 8 or principal.sp_id is None:
            raise ResolutionError("sharepoint_group_id_required")
        rows = self._list(self._url(f"web/sitegroups({principal.sp_id})/users"), {
            "$select": "Id,LoginName,Title,Email,PrincipalType",
        })
        return [Principal.from_sharepoint(row, self.site_url) for row in rows]

    def profile(self, login: str) -> dict[str, str | None]:
        if not login:
            raise ResolutionError("profile_login_missing")
        obj = self._object(self._url("SP.UserProfiles.PeopleManager/GetPropertiesFor(accountName=@v)"),
                           {"@v": "'" + login.replace("'", "''") + "'"})
        values = {row["Key"]: row.get("Value")
                  for row in collection(obj.get("UserProfileProperties"))}
        return {"first_name": values.get("FirstName") or None,
                "last_name": values.get("LastName") or None}


@dataclass
class User:
    identity: str
    login: str
    display_name: str | None = None
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    sources: list[dict] = field(default_factory=list)
    name_status: str = "not_requested"


@dataclass
class Report:
    assignments: list[dict] = field(default_factory=list)
    users: list[User] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        """Complete traversal of the supplied assignments under the chosen policy."""
        return not self.errors

    def to_dict(self) -> dict:
        return {"complete": self.complete, **asdict(self)}


Members = Callable[[Principal], Iterable[Principal]]
Profile = Callable[[str], dict[str, str | None]]


def no_directory(principal: Principal) -> list[Principal]:
    raise ResolutionError("directory_adapter_not_configured")


def resolve_assignments(
    assignments: Iterable[dict], *, scope: str, sharepoint_members: Members,
    directory_members: Members = no_directory, profile: Profile | None = None,
    include_assignment: Callable[[dict], bool] = view_items_policy,
    identity_key: Callable[[Principal], str] | None = None,
    max_depth: int = 32, max_visits: int = 100000,
) -> Report:
    """Resolve complete raw assignments. Each invocation starts a fresh cache.

    directory_members maps a type-4 principal's full login/key to directory
    membership. It returns normalized Principal records (kind 1/4), including
    names when available, and raises on failed/ambiguous/incomplete lookups.
    It must not interpret a SharePoint integer ID as a directory identifier.
    """
    report = Report()
    users: dict[str, User] = {}
    cache: dict[tuple, list[Principal]] = {}
    visits = 0
    identity_key = identity_key or (lambda principal: principal.login.casefold())

    def walk(principal: Principal, index: int, path: tuple[str, ...], active: frozenset):
        nonlocal visits
        visits += 1
        if visits > max_visits:
            raise ResolutionError("traversal_visit_limit")
        if len(path) > max_depth:
            raise ResolutionError("traversal_depth_limit")
        if principal.kind == 1:
            if not principal.login:
                raise ResolutionError("user_login_missing")
            key = identity_key(principal)
            if not key:
                raise ResolutionError("user_identity_missing")
            user = users.setdefault(key, User(key, principal.login))
            for name in ("display_name", "email", "first_name", "last_name"):
                incoming = getattr(principal, name)
                if incoming and not getattr(user, name):
                    setattr(user, name, incoming)
                elif incoming and getattr(user, name) != incoming:
                    report.warnings.append({"assignment": index, "code": "attribute_conflict", "field": name})
            source = {"assignment": index, "group_path": list(path)}
            if source not in user.sources:
                user.sources.append(source)
            return
        if principal.kind not in (4, 8):
            raise ResolutionError(f"unsupported_principal_type_{principal.kind}")
        group_key = (principal.kind, principal.key)
        if not principal.key:
            raise ResolutionError("group_identity_missing")
        if group_key in active:
            report.warnings.append({"assignment": index, "code": "membership_cycle", "path": list(path)})
            return  # All other edges remain traversable; no users are lost.
        if group_key not in cache:
            loader = sharepoint_members if principal.kind == 8 else directory_members
            members = list(loader(principal))  # Materialize completely before caching.
            if not all(isinstance(member, Principal) for member in members):
                raise ResolutionError("adapter_returned_invalid_members")
            cache[group_key] = members
        for member in cache[group_key]:
            try:
                walk(member, index, path + (principal.key,), active | {group_key})
            except Exception as error:
                record_error(index, path + (principal.key,), error)

    def record_error(index: int, path: tuple, error: Exception):
        # Raw exception messages can contain internal URLs or credentials.
        code = str(error) if isinstance(error, ResolutionError) else type(error).__name__
        report.errors.append({"assignment": index, "group_path": list(path), "code": code})

    for index, assignment in enumerate(assignments, 1):
        diagnostic = {"assignment": index, "status": "pending", "users_found": 0}
        report.assignments.append(diagnostic)
        before_errors = len(report.errors)
        try:
            principal = Principal.from_sharepoint(assignment["Member"], scope)
            diagnostic.update(principal_key=principal.key, principal_type=principal.kind,
                              roles=[role.get("Name") for role in collection(assignment.get("RoleDefinitionBindings"))])
            if not include_assignment(assignment):
                diagnostic["status"] = "excluded_by_policy"
                continue
            walk(principal, index, (), frozenset())
        except Exception as error:
            record_error(index, (), error)
        diagnostic["users_found"] = sum(
            any(source["assignment"] == index for source in user.sources)
            for user in users.values())
        diagnostic["status"] = "failed" if len(report.errors) > before_errors else "resolved"

    for user in users.values():
        if user.first_name and user.last_name:
            user.name_status = "available"
        elif profile is not None:
            try:
                names = profile(user.login)
                user.first_name = user.first_name or names.get("first_name")
                user.last_name = user.last_name or names.get("last_name")
                user.name_status = "available" if user.first_name and user.last_name else "missing"
            except Exception as error:
                user.name_status = "lookup_failed"
                report.warnings.append({"code": "profile_lookup_failed", "identity": user.identity,
                                        "error_type": type(error).__name__})
    report.users = list(users.values())
    return report


def process_users(report: Report, operation: Callable[[User], Any], *, require_names: bool = False) -> list:
    """Preflight the whole report before invoking any callback.

    Callback side effects are not transactional or automatically retried.
    """
    if not report.complete:
        raise ResolutionError("incomplete_membership_operation_blocked")
    if require_names and any(not user.first_name or not user.last_name for user in report.users):
        raise ResolutionError("missing_names_operation_blocked")
    return [operation(user) for user in report.users]


class SnapshotDirectory:
    """Working offline adapter for an explicitly supplied membership snapshot.

    Group dictionary keys are full login claims (for SharePoint roots) or stable
    directory keys (for nested groups). Snapshot freshness/completeness must be
    established by its producer; absence of a key is an error, never an empty group.
    """

    def __init__(self, groups: dict[str, list[Principal]]):
        self.groups = groups

    def __call__(self, principal: Principal) -> list[Principal]:
        if principal.login in self.groups:
            return self.groups[principal.login]
        if principal.key in self.groups:
            return self.groups[principal.key]
        raise ResolutionError("directory_group_unresolved")
