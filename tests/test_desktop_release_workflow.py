from pathlib import Path


ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "desktop-release.yml"


def test_tagged_desktop_release_builds_and_publishes_verified_assets():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert 'tags: ["v*"]' in workflow
    assert "matrix:" in workflow
    assert "os: [ubuntu-latest, windows-latest, macos-latest]" in workflow
    assert "python scripts/smoke_desktop.py" in workflow
    assert "geologia-desktop-${{ runner.os }}-${{ runner.arch }}" in workflow
    assert "sha256sum release-assets/* > release-assets/SHA256SUMS" in workflow
    assert 'gh release create "$GITHUB_REF_NAME" release-assets/*' in workflow
    assert "--generate-notes --verify-tag" in workflow


def test_release_write_permission_is_scoped_to_publish_job():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "permissions:\n  contents: read" in workflow
    publish = workflow.index("  publish:")
    assert "permissions:\n      contents: write" in workflow[publish:]
