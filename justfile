# TerminalVisuals commands

# Run (default waves, use arrows to switch)
run:
    freio

# Start in galaxy mode
galaxy:
    freio --mode galaxy

# Start in spiral (droid) mode
spiral:
    freio --mode spiral

# Big and fast
big:
    freio --size 41 --speed 8

# ASCII mode
ascii:
    freio --ascii

# One-shot (no loop)
once:
    freio --oneshot

# Claude prompt history
claude-history:
    @tail -100 ~/.claude_global_prompts.log 2>/dev/null || echo "No prompt log found"
