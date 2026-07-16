# Skill / Repo Sync Workflow

The `stock-price` skill is backed by a public GitHub repo. Any code change must be committed and pushed to stay in sync across the skill directory, local clone, and remote repo.

## Workflow

1. **Canonical source of truth**: `~/Codes/stock-price/` (or your local git clone)
2. **Hermes skill directory**: `~/.hermes/skills/data-science/stock-price/scripts/`

### After editing the skill

```bash
# Commit and push from canonical clone
cd ~/Codes/stock-price
git add stock.py test_stock.py README.md
git commit -m "feat: description"
git push origin main

# Sync back to skill directory
cp stock.py test_stock.py ~/.hermes/skills/data-science/stock-price/scripts/
```

### After editing in the skill directory

```bash
# Copy to canonical clone first
cp ~/.hermes/skills/data-science/stock-price/scripts/* ~/Codes/stock-price/
cd ~/Codes/stock-price
git commit -am "fix: description"
git push origin main
```

## Pitfall: editing in skill dir only

If you edit `~/.hermes/skills/.../stock.py` but forget to push, the next session will see stale code in the skill while the repo has newer commits. Always push after any code change.