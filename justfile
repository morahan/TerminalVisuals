# TerminalVisuals commands

# Run default spiral
run:
    python -m src.main

# Rainbow mode
rainbow:
    python -m src.main --colors rainbow

# Big rainbow
big:
    python -m src.main --colors rainbow --size 41 --speed 3

# Fast red spiral
fire:
    python -m src.main --colors red --speed 2 --trail 5

# ASCII mode
ascii:
    python -m src.main --ascii

# One-shot (no loop)
once:
    python -m src.main --oneshot

# Claude prompt history
claude-history:
    @tail -100 ~/.claude_global_prompts.log 2>/dev/null || echo "No prompt log found"
