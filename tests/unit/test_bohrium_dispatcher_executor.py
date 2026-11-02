"""DispatcherExecutor construction against the dflow build on the submitter."""

import configparser
import inspect
from unittest.mock import MagicMock

from et_dflow.infrastructure.workflows.baseline_workflow import (
    _bohrium_job_name,
    _construct_dispatcher_executor,
    _dispatcher_executor_arguments,
    _inject_job_group_patch,
    _resources_with_scass,
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


def test_dispatcher_arguments_include_job_group_and_name(tmp_path):
    arguments = _dispatcher_executor_arguments(
        docker_image="registry.example/astra:test",
        scass_type="c16_m62_1 * NVIDIA T4",
        project_id=3407188,
        access_key="unit-test-key",
        private_key_file=str(tmp_path / "placeholder.key"),
        job_group_id=990100,
        job_name="baseline-benchmark-sm70-astra_fbp",
    )
    remote = arguments["machine_dict"]["remote_profile"]
    assert remote["job_group_id"] == 990100
    assert remote["bohr_job_group_id"] == 990100
    assert remote["job_name"] == "baseline-benchmark-sm70-astra_fbp"
    assert remote["machine_type"] == "c16_m62_1 * NVIDIA T4"


def test_inject_job_group_patch_wraps_machine_load():
    script = "machine = Machine.load_from_dict(machine_dict)\nprint(machine)\n"
    patched = _inject_job_group_patch(script)
    assert "_et_patch_job_group" in patched
    assert "machine = _et_patch_job_group(machine)" in patched
    assert patched.index("_et_patch_job_group") < patched.index("Machine.load_from_dict")


def test_render_writes_config_and_job_group_patch(tmp_path, monkeypatch):
    class _IgnorePreScript(_SubmitterDispatcherExecutor):
        def render(self, template):
            # The installed dflow render does not insert pre_script.
            return type(
                "Rendered",
                (),
                {"script": "machine = Machine.load_from_dict({})\n"},
            )()

    arguments = _dispatcher_executor_arguments(
        docker_image="registry.example/astra:test",
        scass_type="c16_m62_1 * NVIDIA T4",
        project_id=3407188,
        access_key="unit-test-key",
        private_key_file=str(tmp_path / "placeholder.key"),
        job_group_id=881001,
        job_name="baseline-benchmark-sm70-astra",
    )
    executor = _construct_dispatcher_executor(
        _IgnorePreScript,
        arguments,
        access_key="unit-test-key",
        project_id=3407188,
    )
    rendered = executor.render(None)
    assert rendered.script.index("_et_cfg = ") < rendered.script.index(
        "Machine.load_from_dict"
    )
    assert "_et_patch_job_group" in rendered.script
    assert "machine = _et_patch_job_group(machine)" in rendered.script
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


def test_resources_with_scass_fills_default():
    config = {
        "dflow": {
            "force_scass_for_all_algorithms": True,
            "default_scass_type": "c16_m32_cpu",
        }
    }
    filled = _resources_with_scass({"cpu": 4, "memory": "16Gi"}, config)
    assert filled["scass_type"] == "c16_m32_cpu"
    # Explicit scass wins.
    kept = _resources_with_scass(
        {"scass_type": "c8_m32_cpu", "cpu": 4},
        config,
    )
    assert kept["scass_type"] == "c8_m32_cpu"


def test_resources_with_scass_respects_force_false():
    config = {"dflow": {"force_scass_for_all_algorithms": False}}
    out = _resources_with_scass({"cpu": 4}, config)
    assert "scass_type" not in out


def test_bohrium_job_name_readable():
    name = _bohrium_job_name("baseline-benchmark", "sm70", "astra_fbp")
    assert name == "baseline-benchmark-sm70-astra_fbp"


def test_ensure_bohrium_job_group_once_and_shared_id(tmp_path, monkeypatch):
    from et_dflow.infrastructure.workflows import baseline_workflow as bw

    created = []

    def _fake_create(group_name, config):
        created.append(group_name)
        return 990100

    monkeypatch.setattr(bw, "_create_bohrium_job_group", _fake_create)
    monkeypatch.setattr(
        bw,
        "_bohrium_access_key",
        lambda: "unit-test-key",
    )

    config = {
        "workflow": {
            "name": "baseline-benchmark",
            "output_dir": str(tmp_path / "results"),
            "execution_mode": "hybrid",
        },
        "dflow": {
            "bohrium_project_id": "3407188",
            "bohrium_job_group": True,
            "force_scass_for_all_algorithms": True,
            "default_scass_type": "c16_m32_cpu",
        },
        "algorithms": {
            "wbp": {
                "enabled": True,
                "docker_image": "registry.example/wbp:test",
                "resources": {"cpu": 4, "memory": "16Gi"},
            },
            "astra_fbp": {
                "enabled": True,
                "docker_image": "registry.example/astra:test",
                "resources": {
                    "cpu": 8,
                    "scass_type": "c16_m62_1 * NVIDIA T4",
                },
            },
        },
        "datasets": {},
        "evaluation": {},
    }
    # Avoid real configure_dflow side effects where possible.
    monkeypatch.setattr(bw, "configure_dflow", lambda **kwargs: None)

    wf_obj = bw.BaselineBenchmarkWorkflow(config)
    algorithms_items = wf_obj._enabled_algorithms()
    wf_obj._ensure_bohrium_job_group("baseline-benchmark", algorithms_items)
    assert created == [f"baseline-benchmark-{wf_obj._run_output_dir.name}"]
    assert wf_obj._bohrium_job_group_id == 990100
    meta = (wf_obj._run_output_dir / "bohrium_job_group.json").read_text(encoding="utf-8")
    assert "990100" in meta

    # Second ensure recreates for a new build; still one call per ensure.
    wf_obj._ensure_bohrium_job_group("baseline-benchmark", algorithms_items)
    assert len(created) == 2

    # Machine executors for both algorithms receive the same group id.
    monkeypatch.setattr(
        bw,
        "_bohrium_machine_executor",
        lambda docker_image, resources, project_id, job_group_id=None, job_name=None: MagicMock(
            docker_image=docker_image,
            resources=resources,
            job_group_id=job_group_id,
            job_name=job_name,
        ),
    )
    wf_obj._bohrium_job_group_id = 990100
    ex1 = wf_obj._machine_executor(
        "registry.example/wbp:test",
        {"scass_type": "c8_m32_cpu"},
        job_name="baseline-benchmark-sm70-wbp",
    )
    ex2 = wf_obj._machine_executor(
        "registry.example/astra:test",
        {"scass_type": "c16_m62_1 * NVIDIA T4"},
        job_name="baseline-benchmark-sm70-astra_fbp",
    )
    assert ex1.job_group_id == 990100
    assert ex2.job_group_id == 990100
    assert ex1.job_name == "baseline-benchmark-sm70-wbp"
    assert ex2.job_name == "baseline-benchmark-sm70-astra_fbp"
