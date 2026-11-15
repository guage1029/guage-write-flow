"""Run with python3 scripts/test_distribution.py; uses isolated temporary paths."""
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parent.parent
ARTICLE = "# 整理记录\n\n## 过程\n\n今天完成了整理。\n"


def run(command, **kwargs):
    result = subprocess.run(command, text=True, capture_output=True, **kwargs)
    assert result.returncode == 0, (command, result.stdout, result.stderr)
    return result


with TemporaryDirectory(prefix="guage-distribution-") as folder:
    temporary = Path(folder).resolve()
    skills = temporary / "skills"
    workspace = temporary / "稿件's workspace"
    installed = skills / "guage-write-flow"
    source_policy = (ROOT / "skill/references/workspace-config.md").read_bytes()
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    for key in ("GUAGE_WRITE_FLOW_WORKSPACE", "AI_WRITE_FLOW_WORKSPACE"):
        env.pop(key, None)
    install = ["bash", str(ROOT / "scripts/install.sh"), "--tool", "custom", "--skills-dir", str(skills)]

    run(install + ["--workspace", str(workspace)], env=env)
    assert (installed / "SKILL.md").is_file()
    assert not (skills / "ai-write-flow").exists()
    assert not (workspace / "images").exists()
    assert not (installed / "references/workspace-local.md").exists()
    assert str(workspace) in (installed / "references/workspace-config.md").read_text()

    def inventory_workspace():
        result = run([sys.executable, str(installed / "scripts/prepare_research.py"), "inventory"], env=env)
        return json.loads(result.stdout)["workspace"]

    assert inventory_workspace() == str(workspace)
    save_command = [sys.executable, str(installed / "scripts/save_article.py")]
    missing_review = subprocess.run(save_command, input=ARTICLE, text=True, capture_output=True, env=env)
    assert missing_review.returncode != 0 and not list((workspace / "output").glob("*.md"))
    sys.path.insert(0, str(installed / "scripts"))
    from test_review_style import reviewed_fixture
    draft = temporary / "draft.md"
    review = temporary / "review.json"
    draft.write_text(ARTICLE, encoding="utf-8")
    review.write_text(json.dumps(reviewed_fixture(ARTICLE, ARTICLE)), encoding="utf-8")
    run(save_command + ["--draft", str(draft), "--review", str(review)], input=ARTICLE, env=env)
    saved = list((workspace / "output").glob("*.md"))
    assert len(saved) == 1 and saved[0].read_text() == ARTICLE
    assert not list(installed.rglob("*.pyc"))

    # Old installations may keep their workspace name after the project rename.
    legacy = temporary / "ai-write-flow"
    env["AI_WRITE_FLOW_WORKSPACE"] = str(legacy)
    run(install, input="y\n", env=env)
    assert inventory_workspace() == str(legacy)
    assert saved[0].read_text() == ARTICLE

    preferred = temporary / "preferred"
    env["GUAGE_WRITE_FLOW_WORKSPACE"] = str(preferred)
    run(install, input="y\n", env=env)
    assert inventory_workspace() == str(preferred)
    assert (ROOT / "skill/references/workspace-config.md").read_bytes() == source_policy

    run(["bash", str(ROOT / "scripts/package-skill.sh"), "package", "0.0.8"], cwd=temporary, env=env)
    archive = temporary / "package/guage-write-flow-skill-0.0.8.zip"
    with ZipFile(archive) as bundle:
        names = bundle.namelist()
    assert names and all(name.startswith("guage-write-flow/") for name in names)
    assert "guage-write-flow/scripts/save_article.py" in names
    assert not any("__pycache__" in name or name.endswith(".pyc") for name in names)
    assert not any("card-post" in name or "check_card_post" in name or "illustration-config" in name for name in names)

print("PASS: renamed install/archive, workspace binding, legacy environment, isolated save, and source preservation")
