import unittest

from nova.http_transport import parse_multipart_form


class MultipartParserTests(unittest.TestCase):
    def test_parses_document_and_mode(self):
        boundary = "nova-test-boundary"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="mode"\r\n\r\n'
            "gemini\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="document"; filename="invoice.pdf"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        ).encode() + b"%PDF-test\r\n" + f"--{boundary}--\r\n".encode()

        files, fields = parse_multipart_form(
            body,
            f"multipart/form-data; boundary={boundary}",
        )

        self.assertEqual(fields["mode"], "gemini")
        self.assertEqual(files["document"][0], "invoice.pdf")
        self.assertEqual(files["document"][1], "application/pdf")
        self.assertEqual(files["document"][2], b"%PDF-test")

    def test_rejects_non_multipart_requests(self):
        with self.assertRaises(ValueError):
            parse_multipart_form(b"{}", "application/json")


if __name__ == "__main__":
    unittest.main()
