import ast
import json
from pathlib import Path
import unittest

from app_config import settings


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"


class ConfigurationSmokeTests(unittest.TestCase):
    def test_paths_and_security_configuration(self):
        self.assertEqual(settings.base_dir, ROOT)
        self.assertTrue(settings.static_dir.is_dir())
        self.assertGreater(settings.llm_timeout_seconds, 0)
        self.assertGreaterEqual(settings.llm_max_retries, 0)
        self.assertTrue(settings.secret_key)
        self.assertTrue(settings.gemini_vision_model)
        self.assertGreater(settings.gemini_vision_timeout_seconds, 0)

    def test_cors_origins_are_normalized(self):
        self.assertEqual(len(settings.cors_origins), len(set(settings.cors_origins)))
        self.assertIn("https://openpharmacy.online", settings.cors_origins)


class FrontendContractTests(unittest.TestCase):
    def test_portals_load_core_before_application(self):
        for filename in ("index.html", "pharmacist.html", "admin.html"):
            html = (STATIC / filename).read_text(encoding="utf-8")
            with self.subTest(filename=filename):
                self.assertLess(html.index("js/ui-core.js"), html.index("js/app.js"))
                self.assertIn("css/brand-system.css", html)

    def test_markdown_renderer_has_allowlist_and_safe_links(self):
        source = (STATIC / "js" / "ui-core.js").read_text(encoding="utf-8")
        self.assertIn("allowedTags", source)
        self.assertIn("noopener noreferrer", source)
        self.assertIn("/^https?:\\/\\//i", source)
        self.assertNotIn("eval(", source)

    def test_manifest_uses_canonical_start_route(self):
        manifest = json.loads((STATIC / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "BisaRx Clinical AI")
        self.assertEqual(manifest["start_url"], "/")

    def test_admin_portal_uses_access_code_only_form(self):
        html = (STATIC / "admin.html").read_text(encoding="utf-8")
        app_source = (STATIC / "js" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn('id="login-username"', html)
        self.assertIn('id="login-pass"', html)
        self.assertIn('name="access_code"', html)
        self.assertIn("usernameInput?.dataset.loginMode", app_source)

    def test_scroll_ownership_contract(self):
        css = (STATIC / "css" / "brand-system.css").read_text(encoding="utf-8")
        self.assertIn(".panel.on:not(#panel-chat)", css)
        self.assertIn("overscroll-behavior-y: contain", css)
        self.assertIn("#panel-chat .messages-container", css)
        self.assertIn("overflow-y: auto", css)

    def test_body_map_captures_location_sensation_and_severity(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        source = (STATIC / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="bodymap-sensations"', html)
        self.assertIn('id="bodymap-severity"', html)
        self.assertIn("selectedBodyZones", source)
        self.assertIn("initializeBodyMapAccessibility", source)


class RouteContractTests(unittest.TestCase):
    def test_critical_routes_remain_declared(self):
        tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
        routes = set()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                    continue
                if decorator.func.attr not in {"get", "post", "put", "patch", "delete", "websocket"}:
                    continue
                if decorator.args and isinstance(decorator.args[0], ast.Constant):
                    routes.add(decorator.args[0].value)

        expected = {
            "/api/health",
            "/api/auth/login",
            "/api/chat",
            "/api/pharmacist/dashboard",
            "/api/admin/dashboard",
            "/api/cases/{case_id}/order",
            "/",
            "/pharmacist",
            "/admin",
        }
        self.assertTrue(expected.issubset(routes), expected - routes)


if __name__ == "__main__":
    unittest.main()
