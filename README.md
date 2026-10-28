# Generic SharePoint permission membership workflow

This reference implementation resolves raw role assignments into individual user
accounts, optionally retrieves separate first/last-name attributes, and invokes
an application callback once per deduplicated account. Python 3.10+ is required.
The core, demo and tests use only the Python standard library.

## Files and first run

| File | Purpose |
| --- | --- |
| `permission_workflow.py` | REST adapter, recursive resolver, policies, report and operation guard |
| `example.py` | Offline demo and integration functions |
| `test_workflow.py` | Synthetic tests; no internal environment required |
| `sample_output.json` | Output from the offline demo, using invented data |

From the extracted directory:

```bash
python example.py
python -m unittest -v
```

The demo starts with four synthetic assignments: an individual user, a SharePoint
group, a directory group and a Limited Access assignment. It produces four
unique users. The last assignment is excluded by the sample grant policy.
The numbers illustrate behavior and make no claim about an actual environment.

## Integration with existing raw assignments

The workflow accepts the original expanded assignment dictionaries, not the
diagnostic summaries and not the final login list. Required fields are
`Member.Id`, `Member.PrincipalType`, `Member.LoginName` for individual users, and
`RoleDefinitionBindings`. The default policy additionally requires each role's
`BasePermissions.Low` and `BasePermissions.High`.

```python
from permission_workflow import SharePointRest, resolve_assignments, process_users

# authenticated_session is the application's existing requests-compatible
# session, with its approved authentication, TLS certificates and proxy settings.
sp = SharePointRest(authenticated_session, "https://example.invalid/sites/example")

# Existing raw enumeration can be retained instead of calling file_assignments.
assignments = existing_sp_client.get_file_role_assignments(server_relative_url)

report = resolve_assignments(
    assignments,
    scope=sp.site_url,
    sharepoint_members=sp.group_members,
    directory_members=directory_members,  # Callable contract below.
    profile=sp.profile,                  # Omit to disable profile enrichment.
)

# A side-effect-free example. An application-specific operation can replace it.
results = process_users(
    report,
    lambda user: {
        "login": user.login,
        "first_name": user.first_name,
        "last_name": user.last_name,
    },
    require_names=False,
)
```

The example refers to application-owned variables; it is an integration excerpt,
not a standalone credential setup script. Authentication is deliberately injected.
No username/password convention, cloud token flow or additional package install
is assumed.

## Alternative: retrieve the file assignments with the included adapter

```python
assignments = sp.file_assignments("/sites/example/Documents/example.docx")
```

This explicitly retrieves the inheritance flag. For inherited permissions, it
reads assignments through `FirstUniqueAncestorSecurableObject`, rather than
combining every parent's ACL. Collection pagination is followed, including
verbose-JSON nested role-binding continuation links. The REST request explicitly
requests the principal type and base permission masks.

The configured web must contain the target file. Endpoint availability and
inheritance navigation need validation against the deployed SharePoint version.
The existing enumeration function remains usable if a deployment needs another
scope-discovery mechanism. Failure of file enumeration propagates and prevents
the processing stage from starting.

Legacy URL APIs are ambiguous for filenames containing literal `%` or `#`; the
default path rejects these characters. When the deployment supports ResourcePath:

```python
sp = SharePointRest(authenticated_session, site_url, resource_path_api=True)
assignments = sp.file_assignments(decoded_server_relative_path)
```

The ResourcePath input must be decoded, not an already percent-encoded URL.
ResourcePath availability is not assumed for every on-premise deployment.

## Directory adapter contract

`directory_members(principal)` is the only environment-specific membership
boundary. It is called for type-4 principals, whether found directly on the file
ACL or inside a SharePoint group. It must:

1. Map the complete SharePoint claim/login or a normalized directory key to a
   unique directory group. A SharePoint integer principal ID is not an AD group ID.
2. Fetch **all direct members**, including every page or ranged response.
3. Return individual users as `Principal(kind=1, ...)` and nested security groups
   as `Principal(kind=4, ...)`. The workflow handles nested-group recursion.
4. Use stable directory keys for groups so repeated references and cycles are
   recognized. Return complete provider-qualified user logins for processing and
   profile lookup; avoid guessing names from account strings.
5. Raise `ResolutionError("stable_error_code")` on absent, ambiguous, forbidden or
   incomplete results. Return `[]` only for a successfully enumerated empty group.
6. Define handling of non-user objects, foreign principals, primary-group
   membership and provider-specific broad claims. Unsupported identity classes
   must not silently disappear. Any authorization-grade completeness claim
   depends on this contract being met by the directory implementation.

Example normalized return values:

```python
from permission_workflow import Principal

def directory_members(principal):
    # A local approved backend owns claim mapping, authentication, page/range
    # completion and object classification. These methods are application APIs.
    directory_group = approved_backend.resolve_group(principal.login or principal.key)
    records = approved_backend.list_all_direct_members(directory_group)
    return [
        Principal(
            kind=record.principal_type,  # 1 for user, 4 for nested security group.
            key=record.stable_directory_key,
            login=record.full_login,
            display_name=record.display_name,
            email=record.email,
            first_name=record.given_name,
            last_name=record.surname,
        )
        for record in records
    ]
```

`approved_backend` is an explicit integration boundary, not a supplied LDAP
client. No live LDAP/AD connector is included because group-claim mapping,
directory routing, authentication and completeness rules are deployment-specific.
The default `no_directory` callback fails explicitly. `SnapshotDirectory` is a
working alternative for a supplied complete offline membership map; the demo
uses it. Snapshot freshness and membership coverage remain the producer's
responsibility. No cloud directory service is required.

## Policy, identity and names

The default `view_items_policy` checks the union of an assignment's role masks
for `ViewListItems`. It identifies candidate view grants without relying on
localized or custom role names. It is **not** a complete effective-access check
for file download, draft visibility, every version, or administrative policy.
Another grant policy can be passed through `include_assignment`.

For diagnostic enumeration of every role assignment, regardless of its rights:

```python
from permission_workflow import all_assignments_policy
# resolve_assignments(..., include_assignment=all_assignments_policy)
```

That mode includes Limited Access and must not be labeled a list of file readers.
Assignments excluded by a policy still appear in the report.

The default identity key is the **entire login, casefolded**. Domains and claims
are retained. Different claim encodings for the same person are intentionally
not merged automatically. A supplied `identity_key(principal)` callback can map
both SharePoint users and directory users to a common authoritative identifier.
The callback must avoid merging unrelated accounts or key collisions.

Directory-provided first/last names take precedence. If either is missing and a
profile callback is configured, `PeopleManager.GetPropertiesFor` is called once
per deduplicated user. It reads `FirstName` and `LastName` from
`UserProfileProperties`. Missing/inaccessible profile properties remain `None`;
there is no splitting of dots, email addresses or display names to invent names.
Profile-service availability and readable profile properties depend on deployment.

The `name_status` field distinguishes available attributes, missing properties,
lookup failure and enrichment not requested. Names are attributes, not unique
identifiers. `require_names=True` blocks processing before the first operation
if any user's first or last name is missing.

## Diagnostics and processing behavior

`report.to_dict()` contains:

| Field | Meaning |
| --- | --- |
| `assignments` | One diagnostic row per supplied assignment, including exclusions |
| `users` | Deduplicated accounts and their source assignments/group paths |
| `errors` | Unresolved principals, unavailable membership, invalid data or limits |
| `warnings` | Cycles, profile failures or inconsistent optional attributes |
| `complete` | No expansion errors under the selected assignment policy |

`complete` means traversal completed for the supplied assignments. It does not
certify that the source ACL inventory includes every possible administrative,
web-application policy, sharing-link, anonymous or token-based access route.
Expanding directory membership also does not prove a particular user can currently
open a file. Authorization-sensitive operations still need the source system's
effective permission checks and freshness appropriate to the application.

Cycles are reported and their recursive edge is skipped; remaining edges continue
to be explored. Depth/visit limits make the result incomplete if exceeded. A
failed group's known siblings can remain visible for diagnosis, but
`process_users` rejects the entire incomplete report before invoking any callback.
An empty successfully resolved group is distinct from a failed group.

Membership caching lasts only for one resolution run. Operations are invoked once
per deduplicated account. Callbacks are not transactional: a callback that fails
after earlier callbacks have completed cannot roll those side effects back.
An application requiring retries should implement idempotency and its own
checkpoint policy.

The adapter uses the injected session's TLS verification, disables HTTP redirects,
rejects cross-origin next links and does not log response bodies or credentials.
Real report values contain account information and belong in the local approved
environment. Any shared diagnostic sample must replace identities and internal
addresses with synthetic placeholders.

## Validation

17 synthetic tests passed. The demo produced four deduplicated users with names,
all source assignments preserved, one policy exclusion, and no expansion errors.
Tests cover nested groups, deduplication, cycle handling, domain preservation,
custom role names, missing permission masks, profile failure, operation guards,
pagination, a failed later page, inheritance navigation and OData quote handling.
No live SharePoint or directory authentication/integration was exercised.

## Primary documentation and contribution estimates

These weights describe the documented API/design basis; they are editorial
estimates, not measured code attribution or probabilities. Recursion, error
aggregation and operation guards are implementation choices tested synthetically.

| Source | Contribution | Basis |
| --- | --- | --- |
| [Microsoft PrincipalType](https://learn.microsoft.com/en-us/previous-versions/office/sharepoint-csom/ee541430(v=office.15)) | 15% | Routing users, SharePoint groups and directory security groups |
| [Microsoft SharePoint group users](https://learn.microsoft.com/en-us/previous-versions/office/sharepoint-visio/jj246607(v=office.15)) | 20% | Group-membership REST endpoint |
| [Microsoft FirstUniqueAncestorSecurableObject](https://learn.microsoft.com/en-us/previous-versions/office/sharepoint-csom/jj171634(v=office.15)) | 15% | Applicable inherited permission scope |
| [Microsoft PermissionKind](https://learn.microsoft.com/en-us/dotnet/api/microsoft.sharepoint.client.permissionkind?view=sharepoint-csom) | 15% | ViewListItems permission position |
| [Microsoft user profile APIs](https://learn.microsoft.com/en-us/sharepoint/dev/general-development/work-with-user-profiles-in-sharepoint) | 15% | PeopleManager profile lookup |
| [Microsoft profile response example](https://learn.microsoft.com/en-us/sharepoint/dev/general-development/following-people-and-content-rest-api-reference-for-sharepoint) | 10% | FirstName/LastName property shape |
| [Microsoft ResourcePath](https://learn.microsoft.com/en-us/sharepoint/dev/solution-guidance/supporting-and-in-file-and-folder-with-the-resourcepath-api) | 10% | Decoded-path API and legacy ambiguity |
