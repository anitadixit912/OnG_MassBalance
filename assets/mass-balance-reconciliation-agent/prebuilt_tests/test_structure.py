import pytest

@pytest.mark.structure
class TestRequiredFiles:
    def test_agent_directory_exists(self, agent_path):
        assert agent_path.exists() and agent_path.is_dir()

    def test_app_directory_exists(self, agent_app_path):
        assert agent_app_path.exists() and agent_app_path.is_dir()

    def test_requirements_txt_exists(self, agent_path):
        req = agent_path / "requirements.txt"
        assert req.exists() and req.stat().st_size > 0

    def test_dockerfile_exists(self, agent_path):
        assert (agent_path / "Dockerfile").exists()

    def test_skills_dir_exists(self, agent_app_path):
        skills = agent_app_path / "skills"
        assert skills.exists() and skills.is_dir()

    def test_all_skill_dirs_present(self, agent_app_path):
        skills = agent_app_path / "skills"
        expected = [
            "data-validation",
            "mass-balance-calculation",
            "variance-classification",
            "root-cause-investigation",
            "approval-governance",
            "exception-report",
        ]
        for name in expected:
            assert (skills / name / "SKILL.md").exists(), f"Missing skill: {name}/SKILL.md"
