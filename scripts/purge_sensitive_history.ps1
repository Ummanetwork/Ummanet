#requires -version 5.1
<#
.SYNOPSIS
  Rewrites git history to remove known leaked artifacts/secrets.

.DESCRIPTION
  This script is destructive for commit hashes (history rewrite).
  Run it only when you are ready to force-push rewritten branches/tags.
#>

param(
    [switch]$Run,
    [string]$LeakedFireworksKey
)

$ErrorActionPreference = "Stop"

if (-not $Run) {
    Write-Host "Dry mode. No changes applied."
    Write-Host "To execute history rewrite, run:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File scripts/purge_sensitive_history.ps1 -Run -LeakedFireworksKey '<old_key>'"
    exit 0
}

git rev-parse --is-inside-work-tree | Out-Null

if ((git status --porcelain).Length -gt 0) {
    throw "Working tree is not clean. Commit/stash changes before rewriting history."
}

Write-Host "Removing bot/.env copy from all refs..."
git filter-branch --force `
  --index-filter "git rm --cached --ignore-unmatch -- 'bot/.env copy'" `
  --prune-empty `
  --tag-name-filter cat `
  -- --all

if ($LeakedFireworksKey) {
    if ($LeakedFireworksKey -notmatch "^[A-Za-z0-9_:-]+$") {
        throw "LeakedFireworksKey contains unsupported characters."
    }
    Write-Host "Redacting provided Fireworks key in history..."
    git filter-branch --force `
      --tree-filter "if [ -f reports/gpt_5.md ]; then sed -i 's/$LeakedFireworksKey/fw_REDACTED/g' reports/gpt_5.md; fi" `
      --tag-name-filter cat `
      -- --all
} else {
    Write-Host "Skipping Fireworks key redaction step: -LeakedFireworksKey not provided."
}

Write-Host "Cleanup refs/original and gc..."
git for-each-ref --format="delete %(refname)" refs/original | git update-ref --stdin
git reflog expire --expire=now --all
git gc --prune=now --aggressive

Write-Host "Done. Next step: force-push all rewritten branches and tags."
