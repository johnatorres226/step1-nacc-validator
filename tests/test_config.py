"""
Unit tests for configuration management.
"""

import pytest
from pipeline.config_manager import QCConfig, get_config, load_config_from_env, project_root
from pathlib import Path


@pytest.fixture
def sample_config():
    """Return a sample QCConfig object for testing."""
    return QCConfig(
        redcap_api_token="test_token",
        redcap_api_url="https://test.redcap.com/api/",
        max_workers=2,
        timeout=60,
    )


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for testing."""
    return tmp_path


class TestQCConfig:
    """Test cases for QCConfig class."""

    def test_default_initialization(self):
        """Test default configuration initialization."""
        config = QCConfig()
        assert config.log_level == "INFO"
        assert config.max_workers == 4
        assert config.timeout == 300
        assert config.retry_attempts == 3
        assert config.generate_html_report is True
        assert config.generate_csv_report is True

    def test_environment_variable_loading(self, monkeypatch):
        """Test loading configuration from environment variables."""
        monkeypatch.setenv("REDCAP_API_TOKEN", "env_token")
        monkeypatch.setenv("REDCAP_API_URL", "https://env.redcap.com/api/")

        config = QCConfig()
        assert config.redcap_api_token == "env_token"
        assert config.redcap_api_url == "https://env.redcap.com/api/"

    def test_validation_success(self, sample_config):
        """Test successful configuration validation."""
        errors = sample_config.validate()
        assert not errors

    def test_validation_missing_token(self):
        """Test validation with missing API token."""
        config = QCConfig(redcap_api_url="https://test.com")
        errors = config.validate()
        assert "REDCAP_API_TOKEN is required" in errors

    def test_validation_missing_url(self):
        """Test validation with missing API URL."""
        config = QCConfig(redcap_api_token="test_token")
        errors = config.validate()
        assert "REDCAP_API_URL is required" in errors

    def test_validation_invalid_workers(self, sample_config):
        """Test validation with invalid worker count."""
        sample_config.max_workers = 0
        errors = sample_config.validate()
        assert "max_workers must be at least 1" in errors

    def test_validation_invalid_timeout(self, sample_config):
        """Test validation with invalid timeout."""
        sample_config.timeout = 10
        errors = sample_config.validate()
        assert "timeout must be at least 30 seconds" in errors

    def test_save_and_load_from_file(self, sample_config, temp_dir):
        """Test saving and loading configuration from file."""
        config_file = temp_dir / "test_config.json"

        # Save configuration
        sample_config.to_file(config_file)
        assert config_file.exists()

        # Load configuration
        loaded_config = QCConfig.from_file(config_file)
        assert loaded_config.redcap_api_url == sample_config.redcap_api_url
        assert loaded_config.max_workers == sample_config.max_workers
        assert loaded_config.get_instruments() == sample_config.get_instruments()

    def test_load_from_nonexistent_file(self, temp_dir):
        """Test loading from non-existent file returns default config."""
        config_file = temp_dir / "nonexistent.json"
        config = QCConfig.from_file(config_file)
        assert isinstance(config, QCConfig)
        assert config.log_level == "INFO"  # Default value


class TestConfigFunctions:
    """Test module-level configuration functions."""

    def test_json_rules_path_loading(self, monkeypatch):
        """Test that JSON_RULES_PATH is correctly loaded."""
        # Test case 1: Environment variable is set
        # Use a platform-neutral path for testing
        fake_path = Path("fake") / "path" / "for" / "json"
        monkeypatch.setenv("JSON_RULES_PATH", str(fake_path))
        
        # We need to provide the required env vars to instantiate QCConfig without validation errors
        monkeypatch.setenv("REDCAP_API_TOKEN", "test-token")
        monkeypatch.setenv("REDCAP_API_URL", "http://test.com")

        config = QCConfig()
        
        # The path should be resolved to an absolute path in __post_init__
        assert Path(config.json_rules_path).is_absolute()
        assert config.json_rules_path.endswith(str(fake_path))

        # Test case 2: Environment variable is not set (should use default)
        monkeypatch.delenv("JSON_RULES_PATH", raising=False)
        config_no_env = QCConfig()
        
        expected_default_path = str(project_root / "config" / "json_rules")
        
        assert config_no_env.json_rules_path == expected_default_path

    def test_get_config_returns_singleton(self, monkeypatch):
        """Test that get_config returns the same instance."""
        monkeypatch.setenv("REDCAP_API_TOKEN", "test_token")
        monkeypatch.setenv("REDCAP_API_URL", "https://test.com")
        
        # Force reload to ensure we get a fresh instance with the patched env vars
        config1 = get_config(force_reload=True)
        config2 = get_config()
        assert config1 is config2

    def test_get_config_raises_error_on_invalid_config(self, monkeypatch):
        """Test that get_config raises SystemExit on invalid configuration."""
        # Ensure required variables are not set
        monkeypatch.delenv("REDCAP_API_TOKEN", raising=False)
        monkeypatch.delenv("REDCAP_API_URL", raising=False)
        
        with pytest.raises(SystemExit):
            get_config(force_reload=True)

    def test_load_config_from_env(self, monkeypatch):
        """Test loading configuration from environment variables."""
        monkeypatch.setenv("REDCAP_API_TOKEN", "env_token")
        monkeypatch.setenv("REDCAP_API_URL", "https://env.redcap.com/api/")
        
        config = load_config_from_env()
        assert config.redcap_api_token == "env_token"
        assert config.redcap_api_url == "https://env.redcap.com/api/"
