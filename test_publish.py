import io
import unittest
from publish import immutable_put, candidate_prefix


class Conflict(Exception):
    response = {"Error": {"Code": "PreconditionFailed"}}


class ExistingObject:
    def put_object(self, **kwargs):
        assert kwargs["IfNoneMatch"] == "*"
        raise Conflict()

    def get_object(self, **kwargs):
        return {"Body": io.BytesIO(b"original")}


class PublicationTests(unittest.TestCase):
    def test_identical_upload_can_be_retried(self):
        immutable_put(ExistingObject(), "bucket", "key", b"original", "application/zip")

    def test_version_cannot_be_replaced(self):
        with self.assertRaisesRegex(ValueError, "Refusing to replace"):
            immutable_put(ExistingObject(), "bucket", "key", b"changed", "application/zip")

    def test_version_and_build_identify_candidate(self):
        self.assertEqual(candidate_prefix({"id": "grindset", "version": "1.0", "build": "2"}),
                         "grindset/versions/1.0-2")

    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError):
            candidate_prefix({"id": "../stable", "version": "1", "build": "2"})
