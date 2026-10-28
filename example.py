"""Offline demonstration and integration entry points. No credentials required."""
from __future__ import annotations

import json

from permission_workflow import (
    Principal, SharePointRest, SnapshotDirectory, process_users, resolve_assignments,
)


def assignment(principal_id, principal_type, login, low="1", role="Read"):
    return {
        "Member": {"Id": principal_id, "PrincipalType": principal_type, "LoginName": login},
        "RoleDefinitionBindings": {"results": [
            {"Name": role, "BasePermissions": {"Low": low, "High": "0"}},
        ]},
    }


def resolve_existing_assignments(sp_client, assignments, directory_members):
    """Entry point when raw expanded assignments are already available."""
    return resolve_assignments(
        assignments,
        scope=sp_client.site_url,
        sharepoint_members=sp_client.group_members,
        directory_members=directory_members,
        profile=sp_client.profile,
    )


def run_with_session(authenticated_session, site_url, file_path, directory_members,
                     operation, *, require_names=False):
    """Actual HTTP integration; authentication remains owned by the application.

    directory_members is a callable taking Principal(kind=4) and returning an
    iterable of Principal(kind=1 or 4). All pages must be fetched by that adapter.
    Transport/file-enumeration errors propagate before any operation can execute.
    """
    sp = SharePointRest(authenticated_session, site_url)
    report = resolve_existing_assignments(sp, sp.file_assignments(file_path), directory_members)
    results = process_users(report, operation, require_names=require_names)
    return report, results


def demo():
    assignments = [
        assignment(1, 1, r"EXAMPLE\person.one"),
        assignment(10, 8, "Example readers"),
        assignment(20, 4, "<DIRECTORY_GROUP_ROOT_CLAIM>"),
        assignment(30, 8, "Example limited access", low="0", role="Limited Access"),
    ]
    one = Principal(1, "directory:user-one", r"EXAMPLE\person.one")
    two = Principal(1, "directory:user-two", r"EXAMPLE\person.two",
                    first_name="Example", last_name="Two")
    three = Principal(1, "directory:user-three", r"EXAMPLE\person.three")
    four = Principal(1, "directory:user-four", r"EXAMPLE\person.four",
                     first_name="Example", last_name="Four")
    team = Principal(4, "directory:team", "<DIRECTORY_GROUP_TEAM_CLAIM>")
    root = Principal(4, "directory:root", "<DIRECTORY_GROUP_ROOT_CLAIM>")
    directory = SnapshotDirectory({
        team.login: [two, three],
        root.login: [two, four, team],
    })

    def sharepoint_members(group):
        assert group.sp_id == 10
        return [one, team]

    def profile(login):
        # Synthetic profile attributes; real use calls SharePointRest.profile.
        return {"first_name": "Example", "last_name": login.rsplit(".", 1)[-1].title()}

    report = resolve_assignments(assignments, scope="example-site",
                                 sharepoint_members=sharepoint_members,
                                 directory_members=directory, profile=profile)
    preview = process_users(report, lambda user: {
        "login": user.login, "first_name": user.first_name, "last_name": user.last_name,
    }, require_names=True)
    print(json.dumps({"report": report.to_dict(), "operation_preview": preview}, indent=2))
    return report


if __name__ == "__main__":
    demo()
