"""DispatcherExecutor construction against the dflow build on the submitter."""

import configparser
import inspect

from et_dflow.infrastructure.workflows.baseline_workflow import (
    _construct_dispatcher_executor,
    _dispatcher_executor_arguments,
)


class _SubmitterDispatcherExecutor:
    """Matches the installed dflow: no ``envs`` parameter."""

    def __init__(self, private_key_file=None, pre_script="", machine_dict=None):
        self.private_key_file = private_key_file
        self.pre_script = pre_script
        self.machine_dict = machine_dict


def test_old_dispatcher_executor_rejects_envs():
    with_envs = inspect.signature(_SubmitterDispatcherExecutor)
    assert "envs" not in with_envs.parameters
    try:
        _SubmitterDispatcherExecutor(envs={"BOHRIUM_ACCESS_KEY": "secret"})
    except TypeError as exc:
        assert "envs" in str(exc)
    else:
        raise AssertionError("expected TypeError for envs")


def test_render_writes_config_even_when_pre_script_is_ignored(tmp_path, monkeypatch):
    class _IgnorePreScript(_SubmitterDispatcherExecutor):
        def render(self, template):
            # The installed dflow render does not insert pre_script.
            return type("Rendered", (), {"script": "machine = Machine.load_from_dict({})\n"})()

    arguments = _dispatcher_executor_arguments(
        docker_image="registry.example/astra:test",
        scass_type="c16_m62_1 * NVIDIA T4",
        project_id=3407188,
        access_key="unit-test-key",
        private_key_file=str(tmp_path / "placeholder.key"),
    )
    executor = _construct_dispatcher_executor(
        _IgnorePreScript,
        arguments,
        access_key="unit-test-key",
        project_id=3407188,
    )
    rendered = executor.render(None)
    assert rendered.script.index("_et_cfg = ") < rendered.script.index("Machine.load_from_dict")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    exec(rendered.script.split("machine = ", 1)[0], {})
    parser = configparser.ConfigParser()
    parser.read(tmp_path / ".bohriumconfig", encoding="utf-8")
    assert parser.get("Credentials", "accessKey") == "unit-test-key"
    assert parser.get("Credentials", "baseUrl") == "https://openapi.dp.tech"
    cloud_dir = tmp_path / ".dpdispatcher" / "dp_cloud_server"
    assert cloud_dir.is_dir()
    (cloud_dir / "submission.json").write_text("{}", encoding="utf-8")
