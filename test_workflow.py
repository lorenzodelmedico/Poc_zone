"""Synthetic behavioral tests; no network, credentials or external dependencies."""
import unittest

from example import assignment
from permission_workflow import (
    Principal, ResolutionError, SharePointRest, SnapshotDirectory,
    all_assignments_policy, process_users, resolve_assignments,
)


class FakeResponse:
    def __init__(self, data, status=200):
        self.data, self.status_code = data, status

    def json(self):
        return self.data


class FakeSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return next(self.responses)


class WorkflowTests(unittest.TestCase):
    def resolve(self, assignments, sp=lambda _: [], **kwargs):
        return resolve_assignments(assignments, scope="test", sharepoint_members=sp, **kwargs)

    def test_nested_directory_and_dedup_preserve_assignment_provenance(self):
        user = Principal(1, "directory:u", r"DOMAIN\one")
        nested = Principal(4, "directory:nested")
        directory = SnapshotDirectory({"group-claim": [nested], nested.key: [user]})
        report = self.resolve([assignment(8, 8, "sp"), assignment(2, 1, user.login)],
                              sp=lambda _: [Principal(4, "directory:root", "group-claim")],
                              directory_members=directory)
        self.assertTrue(report.complete)
        self.assertEqual(len(report.users), 1)
        self.assertEqual([s["assignment"] for s in report.users[0].sources], [1, 2])
        self.assertEqual(len(report.users[0].sources[0]["group_path"]), 3)

    def test_unconfigured_directory_blocks_operations_before_first_callback(self):
        report = self.resolve([assignment(1, 1, "known"), assignment(4, 4, "group")])
        called = []
        with self.assertRaisesRegex(ResolutionError, "incomplete_membership"):
            process_users(report, lambda user: called.append(user.login))
        self.assertEqual(called, [])
        self.assertEqual(report.assignments[1]["status"], "failed")

    def test_empty_group_is_distinct_from_failed_group(self):
        empty = self.resolve([assignment(8, 8, "empty")])
        failed = self.resolve([assignment(4, 4, "missing")])
        self.assertTrue(empty.complete)
        self.assertEqual(empty.assignments[0]["users_found"], 0)
        self.assertFalse(failed.complete)

    def test_cycle_does_not_drop_reachable_users(self):
        group = Principal(4, "group:a", "claim-a")
        user = Principal(1, "u", "user")
        report = self.resolve([assignment(4, 4, "claim-a")],
                              directory_members=SnapshotDirectory({group.login: [group, user]}))
        self.assertTrue(report.complete)
        self.assertEqual(len(report.users), 1)
        self.assertTrue(any(w["code"] == "membership_cycle" for w in report.warnings))

    def test_permission_masks_not_localized_role_names(self):
        report = self.resolve([assignment(1, 1, "allowed", role="<CUSTOM_LOCALIZED_ROLE>"),
                               assignment(2, 1, "excluded", low="0", role="Read")])
        self.assertEqual([u.login for u in report.users], ["allowed"])
        self.assertEqual(report.assignments[1]["status"], "excluded_by_policy")

    def test_missing_permission_masks_are_errors(self):
        record = assignment(1, 1, "user")
        del record["RoleDefinitionBindings"]["results"][0]["BasePermissions"]
        self.assertFalse(self.resolve([record]).complete)
        self.assertTrue(self.resolve([record], include_assignment=all_assignments_policy).complete)

    def test_profile_failure_does_not_delete_user_but_strict_names_block(self):
        def profile(_):
            raise RuntimeError("sensitive details deliberately not copied into report")
        report = self.resolve([assignment(1, 1, r"DOMAIN\compound.person")], profile=profile)
        self.assertTrue(report.complete)
        self.assertEqual(report.users[0].name_status, "lookup_failed")
        self.assertEqual(process_users(report, lambda u: u.login), [r"DOMAIN\compound.person"])
        with self.assertRaisesRegex(ResolutionError, "missing_names"):
            process_users(report, lambda _: None, require_names=True)
        self.assertNotIn("sensitive details", str(report.to_dict()))

    def test_unknown_types_and_missing_logins_are_errors(self):
        for record in (assignment(2, 2, "distribution"), assignment(1, 1, "")):
            self.assertFalse(self.resolve([record]).complete)

    def test_identity_does_not_strip_domains_or_claims(self):
        report = self.resolve([assignment(1, 1, r"A\same"), assignment(2, 1, r"B\same")])
        self.assertEqual(len(report.users), 2)

    def test_cache_is_per_run_not_persistent_membership(self):
        records = [assignment(8, 8, "group")]
        users = [Principal(1, "one", "one")]
        first = self.resolve(records, sp=lambda _: users)
        users[:] = [Principal(1, "two", "two")]
        second = self.resolve(records, sp=lambda _: users)
        self.assertEqual(first.users[0].login, "one")
        self.assertEqual(second.users[0].login, "two")

    def test_depth_limit_marks_report_incomplete(self):
        group = Principal(4, "g", "g")
        report = self.resolve([assignment(8, 8, "sp")], sp=lambda _: [group],
                              directory_members=SnapshotDirectory({"g": [Principal(1, "u", "u")]}),
                              max_depth=0)
        self.assertFalse(report.complete)


class RestTests(unittest.TestCase):
    def test_group_pagination_supports_verbose_and_minimal_shapes(self):
        row = {"Id": 1, "PrincipalType": 1, "LoginName": "one"}
        session = FakeSession([
            FakeResponse({"d": {"results": [row], "__next": "?page=2"}}),
            FakeResponse({"value": [{**row, "Id": 2, "LoginName": "two"}]}),
        ])
        members = SharePointRest(session, "https://example.invalid/site").group_members(
            Principal(8, "sp:g", sp_id=8))
        self.assertEqual([p.login for p in members], ["one", "two"])
        self.assertIsNone(session.calls[1][1]["params"])
        self.assertFalse(session.calls[0][1]["allow_redirects"])

    def test_cross_origin_pagination_is_rejected(self):
        session = FakeSession([FakeResponse({"d": {"results": [], "__next": "https://other.invalid/next"}})])
        with self.assertRaisesRegex(ResolutionError, "cross_origin"):
            SharePointRest(session, "https://example.invalid/site").group_members(Principal(8, "g", sp_id=8))
        self.assertEqual(len(session.calls), 1)

    def test_later_page_error_does_not_return_partial_group(self):
        session = FakeSession([FakeResponse({"d": {"results": [], "__next": "?page=2"}}),
                               FakeResponse({}, status=403)])
        with self.assertRaisesRegex(ResolutionError, "http_403"):
            SharePointRest(session, "https://example.invalid/site").group_members(Principal(8, "g", sp_id=8))

    def test_inheritance_scope_and_apostrophe_escaping(self):
        session = FakeSession([FakeResponse({"d": {"HasUniqueRoleAssignments": False}}),
                               FakeResponse({"d": {"results": []}})])
        SharePointRest(session, "https://example.invalid/site").file_assignments("/site/docs/a'b.docx")
        self.assertIn("a%27%27b.docx", session.calls[0][0])
        self.assertIn("/FirstUniqueAncestorSecurableObject/RoleAssignments", session.calls[1][0])

    def test_profile_uses_full_claim_and_structured_query_parameter(self):
        session = FakeSession([FakeResponse({"d": {"UserProfileProperties": {"results": [
            {"Key": "FirstName", "Value": "Example"}, {"Key": "LastName", "Value": "Person"},
        ]}}})])
        login = r"i:0#.w|DOMAIN\o'example"
        names = SharePointRest(session, "https://example.invalid/site").profile(login)
        self.assertEqual(names["last_name"], "Person")
        self.assertEqual(session.calls[0][1]["params"]["@v"], "'" + login.replace("'", "''") + "'")

    def test_resource_path_navigation_keeps_alias_after_path(self):
        session = FakeSession([FakeResponse({"d": {"HasUniqueRoleAssignments": True}}),
                               FakeResponse({"d": {"results": []}})])
        SharePointRest(session, "https://example.invalid/site", resource_path_api=True).file_assignments(
            "/site/docs/a#100%.docx")
        self.assertIn("/ListItemAllFields/RoleAssignments?", session.calls[1][0])
        self.assertIn("%23100%25", session.calls[1][0])


if __name__ == "__main__":
    unittest.main()
