# -*- coding: utf-8 -*-

import unittest
from pathlib import Path


DEPLOY_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = DEPLOY_ROOT.parent


class DeploymentFilesTests(unittest.TestCase):
    def test_dockerfile_uses_deploy_entrypoint_and_not_lab_server(self):
        dockerfile = (DEPLOY_ROOT / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn('CMD ["python", "Deploy/server.py"]', dockerfile)
        self.assertNotIn("Lab/server.py", dockerfile)
        self.assertNotIn("COPY Lab", dockerfile)
        self.assertIn("EXPOSE 8788", dockerfile)

    def test_production_env_example_defaults_to_safe_sync_modes(self):
        env = (DEPLOY_ROOT / ".env.production.example").read_text(encoding="utf-8")

        self.assertIn("MINSIGHT_CONFIG_MODE=production", env)
        self.assertIn("MINSIGHT_FEISHU_SYNC_MODE=dry_run", env)
        self.assertIn("MINSIGHT_FEISHU_BASE_SYNC_MODE=dry_run", env)
        self.assertIn("MINSIGHT_DB_PATH=/var/lib/minsight/minsight_deploy.sqlite", env)

    def test_smoke_check_asserts_benchmark_paths_are_hidden(self):
        smoke = (DEPLOY_ROOT / "scripts" / "smoke_check.py").read_text(encoding="utf-8")

        self.assertIn('"/api/run"', smoke)
        self.assertIn('"/api/runs"', smoke)
        self.assertIn('"/api/scenarios"', smoke)
        self.assertIn("benchmark path should not be exposed", smoke)

    def test_dockerignore_keeps_local_state_out_of_image(self):
        dockerignore = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8")

        for pattern in (".env", "*.sqlite", "**/__pycache__/", "Lab/results/", "docs/"):
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, dockerignore)

    def test_deploy_runtime_uses_own_store_without_lab_store_path(self):
        runtime = (DEPLOY_ROOT / "runtime.py").read_text(encoding="utf-8")

        self.assertIn("from .store import WorkbenchStore", runtime)
        self.assertNotIn("LAB_ROOT", runtime)
        self.assertNotIn("from store import BenchmarkStore", runtime)
        self.assertNotIn("Lab.integrations", runtime)

    def test_core_config_supports_production_env_only_mode(self):
        config = (REPO_ROOT / "Core" / "shared" / "config.py").read_text(encoding="utf-8")

        self.assertIn("MINSIGHT_CONFIG_MODE", config)
        self.assertIn("def env_file_candidates", config)
        self.assertIn("return []", config)

    def test_aliyun_ops_files_install_workbench_service(self):
        service = (DEPLOY_ROOT / "ops" / "minsight.service").read_text(encoding="utf-8")
        nginx = (DEPLOY_ROOT / "ops" / "nginx.minsight.conf").read_text(encoding="utf-8")
        bootstrap = (DEPLOY_ROOT / "scripts" / "bootstrap_aliyun.sh").read_text(encoding="utf-8")

        self.assertIn("EnvironmentFile=/etc/minsight/minsight.env", service)
        self.assertIn("ExecStartPre=/opt/minsight/.venv/bin/python Deploy/scripts/validate_env.py", service)
        self.assertIn("ExecStart=/opt/minsight/.venv/bin/python Deploy/server.py", service)
        self.assertIn("proxy_pass http://127.0.0.1:8788", nginx)
        self.assertIn("systemctl enable --now minsight", bootstrap)

    def test_validate_env_rejects_placeholder_secrets(self):
        validator = (DEPLOY_ROOT / "scripts" / "validate_env.py").read_text(encoding="utf-8")

        self.assertIn("PLACEHOLDER_MARKERS", validator)
        self.assertIn("MINSIGHT_CONFIG_MODE must be production/prod/deploy", validator)
        self.assertIn("still looks like a placeholder", validator)

    def test_export_script_creates_deploy_only_repository(self):
        script = (DEPLOY_ROOT / "scripts" / "export_deploy_repo.ps1").read_text(encoding="utf-8")

        self.assertIn("Core\\shared", script)
        self.assertIn("Core\\v2", script)
        self.assertIn("Core\\prompts\\v2", script)
        self.assertIn("Core\\data\\scenarios", script)
        self.assertIn("Deploy", script)
        self.assertIn("Excluded:", script)
        self.assertIn("Lab/` benchmark", script)
        self.assertIn("git init", script)


if __name__ == "__main__":
    unittest.main()
