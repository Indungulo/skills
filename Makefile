# Copyright (c) 2026 EUMETSAT
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

DEFAULT_BRANCH ?= main
REMOTE ?= origin
MANIFEST := .claude-plugin/plugin.json

.DEFAULT_GOAL := help

.PHONY: help setup version check lint release-check check-version check-release-branch check-clean check-tag tag tag-push release

help:
	@printf '%s\n' \
		'EUMETSAT Agent Skills helpers' \
		'' \
		'Targets:' \
		'  make setup                    Configure this clone: sign every commit and tag (SSH key), add Signed-off-by via a hook' \
		'  make version                  Print the plugin version from $(MANIFEST)' \
		'  make check                    Validate the skills (skills-bench and claude plugin validate, when installed)' \
		'  make lint                     Ruff over the helper scripts' \
		'  make release-check VERSION=X  Validate local release preconditions (VERSION is bare, the tag is vX)' \
		'  make tag VERSION=X            Create signed annotated tag vX' \
		'  make tag-push VERSION=X       Push existing tag vX' \
		'  make release VERSION=X        Create and push tag vX from $(DEFAULT_BRANCH)'

setup:
	@git config commit.gpgsign true
	@git config tag.gpgsign true
	@git config core.hooksPath .githooks
	@echo "commit.gpgsign and tag.gpgsign set, .githooks installed: every commit is signed with $$(git config user.signingkey) and signed-off"

version:
	@python3 -c 'import json, pathlib; print(json.loads(pathlib.Path("$(MANIFEST)").read_text())["version"])'

check:
	@if command -v skills-bench >/dev/null 2>&1; then skills-bench validate . --strict; else echo "skills-bench not installed: skipped (see docs/validation.md)"; fi
	@if command -v claude >/dev/null 2>&1; then claude plugin validate .; else echo "claude not installed: plugin validation skipped"; fi

lint:
	@uv run --with ruff ruff check skills/firecube/scripts

release-check: check-version check-release-branch check-clean check-tag

check-version:
	@if [ -z "$(VERSION)" ]; then \
		echo "ERROR: VERSION is required, for example VERSION=0.1.1" >&2; \
		exit 1; \
	fi
	@case "$(VERSION)" in \
		v*) echo "ERROR: VERSION must be the bare version, not v-prefixed: $(VERSION) (the tag becomes v$(VERSION))" >&2; exit 1;; \
	esac
	@manifest_version=$$($(MAKE) -s version); \
	if [ "$$manifest_version" != "$(VERSION)" ]; then \
		echo "ERROR: VERSION=$(VERSION) does not match $(MANIFEST) version $$manifest_version" >&2; \
		exit 1; \
	fi
	@if ! grep -q "^## \[$(VERSION)\]" CHANGELOG.md; then \
		echo "ERROR: CHANGELOG.md has no '## [$(VERSION)]' section" >&2; \
		exit 1; \
	fi
	@for skill in skills/*/SKILL.md; do \
		if ! grep -q '^  version: "$(VERSION)"' "$$skill"; then \
			echo "ERROR: $$skill metadata.version is not $(VERSION)" >&2; \
			exit 1; \
		fi; \
	done

check-release-branch:
	@branch=$$(git branch --show-current); \
	if [ "$$branch" != "$(DEFAULT_BRANCH)" ]; then \
		echo "ERROR: releases are tagged from $(DEFAULT_BRANCH), current branch is $$branch" >&2; \
		exit 1; \
	fi
	@git fetch --quiet "$(REMOTE)" "+refs/heads/$(DEFAULT_BRANCH):refs/remotes/$(REMOTE)/$(DEFAULT_BRANCH)"
	@local_head=$$(git rev-parse HEAD); \
	remote_head=$$(git rev-parse "$(REMOTE)/$(DEFAULT_BRANCH)"); \
	if [ "$$local_head" != "$$remote_head" ]; then \
		echo "ERROR: local $(DEFAULT_BRANCH) is not equal to $(REMOTE)/$(DEFAULT_BRANCH)" >&2; \
		echo "Run: git pull --ff-only $(REMOTE) $(DEFAULT_BRANCH)" >&2; \
		exit 1; \
	fi

check-clean:
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "ERROR: working tree must be clean before tagging a release" >&2; \
		git status --short >&2; \
		exit 1; \
	fi

check-tag:
	@if git rev-parse -q --verify "refs/tags/v$(VERSION)" >/dev/null; then \
		echo "ERROR: local tag v$(VERSION) already exists" >&2; \
		exit 1; \
	fi
	@status=0; \
	git ls-remote --exit-code --tags "$(REMOTE)" "refs/tags/v$(VERSION)" >/dev/null 2>&1 || status=$$?; \
	if [ "$$status" -eq 0 ]; then \
		echo "ERROR: remote tag v$(VERSION) already exists on $(REMOTE)" >&2; \
		exit 1; \
	fi; \
	if [ "$$status" -ne 2 ]; then \
		echo "ERROR: could not query remote tags from $(REMOTE)" >&2; \
		exit "$$status"; \
	fi

tag: release-check
	@git tag -s "v$(VERSION)" -m "Release v$(VERSION)"
	@echo "Created signed tag v$(VERSION)"

tag-push: check-version check-release-branch
	@git push "$(REMOTE)" "refs/tags/v$(VERSION)"

release: tag tag-push
