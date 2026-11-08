import io
import unittest

from app import create_app
from sqlalchemy import select


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, **kwargs: object) -> None:
        bucket = str(kwargs["Bucket"])
        key = str(kwargs["Key"])
        self.objects[(bucket, key)] = bytes(kwargs["Body"])

    def delete_object(self, **kwargs: object) -> None:
        self.objects.pop((str(kwargs["Bucket"]), str(kwargs["Key"])), None)


class ProfileFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.s3 = FakeS3()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_URL": "sqlite://",
                "S3_BUCKET": "private-test-bucket",
                "S3_CLIENT": self.s3,
            }
        )
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        self.app.extensions["database_engine"].dispose()

    def _create_profile(self) -> str:
        response = self.client.post(
            "/api/profiles",
            json={"name": "Sample User", "bio": "A test bio", "consent": True},
        )
        self.assertEqual(response.status_code, 201)
        return response.json["id"]

    def test_profile_and_s3_document_upload_complete(self) -> None:
        profile_id = self._create_profile()
        response = self.client.post(
            f"/api/profiles/{profile_id}/document",
            data={
                "consent": "yes",
                "document": (io.BytesIO(b"\xff\xd8\xfftest-jpeg"), "card.jpg"),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(self.s3.objects), 1)
        (bucket, key), data = next(iter(self.s3.objects.items()))
        self.assertEqual(bucket, "private-test-bucket")
        self.assertTrue(key.startswith(f"profile-documents/{profile_id}/"))
        self.assertTrue(key.endswith(".jpg"))
        self.assertEqual(data, b"\xff\xd8\xfftest-jpeg")

        from app import Document, Profile

        session = self.app.extensions["database_session_factory"]()
        try:
            profile = session.get(Profile, profile_id)
            document = session.scalar(
                select(Document).where(Document.profile_id == profile_id)
            )
            self.assertEqual(profile.name, "Sample User")
            self.assertEqual(profile.bio, "A test bio")
            self.assertEqual(profile.status, "complete")
            self.assertEqual(document.media_type, "image/jpeg")
            self.assertEqual(document.object_key, key)
        finally:
            session.close()

    def test_profile_stays_awaiting_upload_until_document_is_uploaded(self) -> None:
        profile_id = self._create_profile()
        response = self.client.get(f"/api/profiles/{profile_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["status"], "awaiting_upload")

    def test_invalid_file_content_is_rejected_without_s3_write(self) -> None:
        profile_id = self._create_profile()
        response = self.client.post(
            f"/api/profiles/{profile_id}/document",
            data={
                "consent": "yes",
                "document": (io.BytesIO(b"not an image"), "card.jpg"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"contents do not match", response.data)
        self.assertEqual(self.s3.objects, {})

    def test_profile_requires_consent_and_valid_name(self) -> None:
        missing_consent = self.client.post(
            "/api/profiles", json={"name": "Sample User", "bio": "test"}
        )
        missing_name = self.client.post(
            "/api/profiles", json={"name": " ", "bio": "", "consent": True}
        )
        self.assertEqual(missing_consent.status_code, 400)
        self.assertEqual(missing_name.status_code, 400)

    def test_upload_requires_consent_and_configured_s3_bucket(self) -> None:
        profile_id = self._create_profile()
        missing_consent = self.client.post(
            f"/api/profiles/{profile_id}/document",
            data={"document": (io.BytesIO(b"\xff\xd8\xfftest"), "card.jpg")},
            content_type="multipart/form-data",
        )
        self.assertEqual(missing_consent.status_code, 400)

        self.app.config["S3_BUCKET"] = ""
        missing_bucket = self.client.post(
            f"/api/profiles/{profile_id}/document",
            data={
                "consent": "yes",
                "document": (io.BytesIO(b"\xff\xd8\xfftest"), "card.jpg"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(missing_bucket.status_code, 503)


if __name__ == "__main__":
    unittest.main()
