import pytest
@pytest.mark.structure
class TestRequiredFiles:
    def test_agent_directory_exists(self, agent_path): assert agent_path.exists() and agent_path.is_dir()
    def test_app_directory_exists(self, agent_app_path): assert agent_app_path.exists() and agent_app_path.is_dir()
    def test_requirements_txt_exists(self, agent_path):
        req = agent_path / "requirements.txt"; assert req.exists() and req.stat().st_size > 0
