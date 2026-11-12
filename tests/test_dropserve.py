import http.cookiejar
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from http.server import ThreadingHTTPServer
from dropserve import create_handler, make_cookie, safe_name, unique_path, valid_cookie


class DropserveTests(unittest.TestCase):
    def test_cookie_signature_and_expiry(self):
        cookie = make_cookie("secret-token", timestamp=1000)
        self.assertTrue(valid_cookie(cookie, "secret-token", now=1100))
        self.assertFalse(valid_cookie(cookie, "wrong-token", now=1100))
        self.assertFalse(valid_cookie(cookie, "secret-token", now=1000 + 12 * 3600 + 1))
        self.assertFalse(valid_cookie("broken", "secret-token", now=1100))

    def test_safe_filename_removes_paths(self):
        self.assertEqual(safe_name("../../hello.txt"), "hello.txt")
        with self.assertRaises(ValueError):
            safe_name("../")

    def test_unique_path_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "report.txt").write_text("original", encoding="utf-8")
            self.assertEqual(unique_path(root, "report.txt").name, "report (1).txt")

    def test_http_login_list_upload_and_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(root, "test-token-123", 1024 * 1024))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = "http://127.0.0.1:%d" % server.server_address[1]
            try:
                opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    opener.open(base + "/api/files")
                self.assertEqual(denied.exception.code, 401)
                data = urllib.parse.urlencode({"token": "test-token-123"}).encode()
                request = urllib.request.Request(base + "/login", data=data, method="POST")
                response = opener.open(request)
                self.assertEqual(response.status, 200)
                upload = urllib.request.Request(base + "/upload?name=hello.txt", data=b"hello world", headers={"Content-Type": "application/octet-stream"}, method="POST")
                result = json.loads(opener.open(upload).read().decode())
                self.assertEqual(result["name"], "hello.txt")
                listing = json.loads(opener.open(base + "/api/files").read().decode())
                self.assertEqual(listing[0]["name"], "hello.txt")
                self.assertEqual(opener.open(base + "/download/hello.txt").read(), b"hello world")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
