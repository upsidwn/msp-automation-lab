# Opt-in, per-tool privilege escalation: prompt right before the one
# operation that actually needs it, explain why, elevate only that call.
# Not blanket sudo at startup. This is the first feature in the project
# that needs this (see design-notes.md for the decision), built here as
# a small reusable helper rather than one-off sudo calls scattered
# around, since more privileged features are expected to need this same
# shape later.
#
# The actual password prompt is left entirely to `sudo` itself, this
# module never sees or handles a password. `sudo -v` runs first with the
# terminal fully inherited (no output capture) so its interactive prompt
# works normally, then the real command runs with output captured, by
# which point sudo's credential cache means it won't need to prompt
# again.

import subprocess


def confirm_and_run_with_sudo(cmd, reason):
    """Asks whether to run cmd with sudo, explaining what it's for. On
    yes, validates sudo access first (letting the OS handle the password
    prompt), then runs the actual command and returns its stdout. Returns
    None if the user declines or sudo access can't be validated, raises
    subprocess.CalledProcessError if the elevated command itself fails.
    """
    answer = input(f"This needs administrator privileges to {reason}. Run with sudo (y/n)? ").strip().lower()
    if answer != "y":
        return None

    validated = subprocess.run(["sudo", "-v"], check=False)
    if validated.returncode != 0:
        print("Could not get sudo access, skipping this step.")
        return None

    result = subprocess.run(["sudo"] + cmd, capture_output=True, text=True, check=True)
    return result.stdout
