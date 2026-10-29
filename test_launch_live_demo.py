"""Shop credential configuration tests; no network, credentials, or paid calls."""
import pytest

import launch_live_demo as launcher


@pytest.fixture
def config(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, 'ROOT', tmp_path)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    return tmp_path / '.env'


def test_environment_takes_precedence(config, monkeypatch):
    config.write_text('OPENAI_API_KEY=sk-file-fixture\n')
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-env-fixture')
    assert launcher.configured_key() == 'sk-env-fixture'


def test_shop_dotenv_supports_quotes_and_comments(config):
    config.write_text('# local configuration\nOPENAI_API_KEY="sk-file-fixture" # key\n')
    assert launcher.configured_key() == 'sk-file-fixture'


def test_blank_environment_uses_shop_file(config, monkeypatch):
    config.write_text('OPENAI_API_KEY=sk-file-fixture\n')
    monkeypatch.setenv('OPENAI_API_KEY', ' ')
    assert launcher.configured_key() == 'sk-file-fixture'
    assert __import__('os').environ['OPENAI_API_KEY'] == ' '


def test_does_not_search_parent_configuration(config):
    (config.parent.parent / '.env').write_text('OPENAI_API_KEY=sk-parent-fixture\n')
    with pytest.raises(RuntimeError, match='Shop API key is missing'):
        launcher.configured_key()


def test_does_not_interpolate_environment(config, monkeypatch):
    monkeypatch.setenv('OTHER_SECRET', 'sk-other-fixture')
    config.write_text('OPENAI_API_KEY=${OTHER_SECRET}\n')
    with pytest.raises(RuntimeError, match='invalid'):
        launcher.configured_key()


@pytest.mark.parametrize('value', ['', 'not-a-key', 'sk-private fixture'])
def test_invalid_configuration_never_echoes_values(config, monkeypatch, value):
    monkeypatch.setenv('OPENAI_API_KEY', value)
    with pytest.raises(RuntimeError) as error:
        launcher.configured_key()
    if value:
        assert value not in str(error.value)
