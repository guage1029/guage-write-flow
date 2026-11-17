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
    source_files = {str(p.relative_to(ROOT / "skill")): p.read_bytes()
                    for p in (ROOT / "skill").rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.name != ".DS_Store"}
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
           "GUAGE_WRITE_FLOW_WORKSPACE": str(temporary / "ignored-new-variable"),
           "AI_WRITE_FLOW_WORKSPACE": str(temporary / "ignored-legacy-variable")}
    install = ["bash", str(ROOT / "scripts/install.sh"), "--tool", "custom", "--skills-dir", str(skills)]

    # Installation no longer asks for or binds a workspace.
    run(install, cwd=temporary, env=env)
    assert (installed / "SKILL.md").is_file()
    assert not workspace.exists()
    assert not (temporary / "briefs").exists()
    assert not (temporary / "ignored-new-variable").exists()
    assert not (temporary / "ignored-legacy-variable").exists()
    for name in ("README.md", "LICENSE"):
        assert (installed / name).read_bytes() == (ROOT / name).read_bytes()
    assert (installed / "references/style.md").is_file()
    assert not (installed / "references/style-guide.md").exists()
    assert not (installed / "references/workspace-local.md").exists()

    run(install + ["--workspace", str(workspace)], input="y\n", cwd=temporary, env=env)
    assert all((workspace / name).is_dir() for name in ("briefs", "research", "output"))
    assert str(workspace) not in (installed / "references/workspace-config.md").read_text()

    def inventory_workspace(current, *arguments):
        result = run([sys.executable, str(installed / "scripts/prepare_research.py"), "inventory", *arguments], cwd=current, env=env)
        return json.loads(result.stdout)["workspace"]

    assert inventory_workspace(workspace) == str(workspace)
    assert inventory_workspace(temporary) == str(temporary)
    assert inventory_workspace(temporary, "--workspace", str(workspace)) == str(workspace)

    save_command = [sys.executable, str(installed / "scripts/save_article.py"), "--workspace", str(workspace)]
    missing = subprocess.run(save_command, input=ARTICLE, text=True, capture_output=True, cwd=temporary, env=env)
    assert missing.returncode != 0 and not list((workspace / "output").glob("*.md"))
    sys.path.insert(0, str(installed / "scripts"))
    from test_review_style import reviewed_fixture
    from review_style import review_template, validate_review
    draft, review = temporary / "draft.md", temporary / "review.json"
    draft.write_text(ARTICLE, encoding="utf-8")
    record = reviewed_fixture(ARTICLE, ARTICLE)
    assert "style.md" in record["rules_sha256"] and "style-guide.md" not in record["rules_sha256"]
    review.write_text(json.dumps(record), encoding="utf-8")
    run(save_command + ["--draft", str(draft), "--review", str(review)], input=ARTICLE, cwd=temporary, env=env)
    saved = list((workspace / "output").glob("*.md"))
    assert len(saved) == 1 and saved[0].read_text(encoding="utf-8") == ARTICLE
    assert not list(installed.rglob("*.pyc"))

    # Both editable files are actually loaded, and changing them invalidates the review.
    for filename in ("persona.md", "style.md"):
        path = installed / "references" / filename
        original = path.read_text(encoding="utf-8")
        path.write_text(original + "\n本地配置：正式、简练，面向工程师。\n", encoding="utf-8")
        assert any("风格规则" in error for error in validate_review(ARTICLE, ARTICLE, record))
        fresh = review_template(ARTICLE, ARTICLE)
        assert fresh["rules_sha256"][filename] != record["rules_sha256"][filename]
        path.write_text(original, encoding="utf-8")
    assert validate_review(ARTICLE, ARTICLE, record) == []

    personal = installed / "references/style.md"
    personal.write_text(personal.read_text(encoding="utf-8") + "\n私人修改\n", encoding="utf-8")
    previous = personal.read_bytes()
    result = run(install, input="n\n", cwd=temporary, env=env)
    assert "先备份" in result.stdout and personal.read_bytes() == previous
    run(install, input="y\n", cwd=temporary, env=env)
    assert personal.read_bytes() == (ROOT / "skill/references/style.md").read_bytes()
    assert saved[0].read_text(encoding="utf-8") == ARTICLE

    bad_argument = subprocess.run(install + ["--workspace"], cwd=temporary, text=True, capture_output=True, env=env)
    assert bad_argument.returncode != 0 and "需要非空参数值" in bad_argument.stderr
    run(["bash", str(ROOT / "scripts/install.sh"), "--tool", "skip", "--workspace", str(temporary / "init-only")], cwd=temporary, env=env)
    assert (temporary / "init-only/briefs").is_dir()
    after_install = {str(p.relative_to(ROOT / "skill")): p.read_bytes()
                     for p in (ROOT / "skill").rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.name != ".DS_Store"}
    assert source_files == after_install, [name for name in source_files.keys() | after_install.keys()
                                          if source_files.get(name) != after_install.get(name)]

    version = "0.0.11"
    stale_archive = temporary / f"package/guage-write-flow-skill-{version}.zip"
    stale_archive.parent.mkdir()
    with ZipFile(stale_archive, "w") as bundle:
        bundle.writestr("guage-write-flow/output/private-old.md", "合成的旧打包产物，不得混入新包")
    run(["bash", str(ROOT / "scripts/package-skill.sh"), "package", version], cwd=temporary, env=env)
    archive = temporary / f"package/guage-write-flow-skill-{version}.zip"
    with ZipFile(archive) as bundle:
        names = bundle.namelist()
        assert bundle.read("guage-write-flow/LICENSE") == (ROOT / "LICENSE").read_bytes()
        assert bundle.read("guage-write-flow/README.md") == (ROOT / "README.md").read_bytes()
        assert "0.0.11" in bundle.read("guage-write-flow/SKILL.md").decode("utf-8")
        bundle.extractall(temporary / "unpacked")
    assert names and all(name.startswith("guage-write-flow/") for name in names)
    assert "guage-write-flow/scripts/save_article.py" in names
    assert "guage-write-flow/references/style.md" in names
    assert not any("__pycache__" in name or name.endswith(".pyc") or "style-guide.md" in name for name in names)
    assert not any(part in {"briefs", "research", "output", ".git"} for name in names for part in Path(name).parts)
    assert not any("card-post" in name or "check_card_post" in name or "illustration-config" in name for name in names)
    unpacked = temporary / "unpacked/guage-write-flow"
    run([sys.executable, str(ROOT / "quick_validate.py"), str(unpacked)], cwd=temporary, env=env)
    result = run([sys.executable, str(unpacked / "scripts/review_style.py"), "--draft", str(draft), "--final", str(draft)], cwd=workspace, env=env)
    assert "style.md" in json.loads(result.stdout)["rules_sha256"]

print("PASS: isolated install, runtime workspace, editable config binding, overwrite protection, MIT/README archive, and source preservation")
