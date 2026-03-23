import logging
import os
import signal
import subprocess

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 600
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_DIR = os.path.join(PROJECT_ROOT, "workspace")


def invoke_skill(
    channel_id: str,
    message_ts: str,
) -> bool:
    """Invoke the prompt template via claude CLI.

    Returns True if the invocation succeeded, False otherwise.
    """
    local_template = os.path.join(PROJECT_ROOT, "prompt_template.local.md")
    template_path = local_template if os.path.exists(local_template) else os.path.join(PROJECT_ROOT, "prompt_template.md")
    with open(template_path) as f:
        template = f.read()
    prompt = template.replace("{{channel_id}}", channel_id).replace("{{message_ts}}", message_ts)
    cmd = [
        "claude",
        "-p",
        prompt,
        "--model", "claude-sonnet-4-6",
        "--dangerously-skip-permissions",
    ]

    env = {**os.environ, "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "0"}

    logger.info(
        "Invoking skill: channel=%s ts=%s", channel_id, message_ts
    )

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=WORKSPACE_DIR,
            env=env,
            start_new_session=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            # Kill entire process group to clean up child processes
            import os as _os

            try:
                _os.killpg(proc.pid, signal.SIGTERM)
            except OSError:
                proc.kill()
            # Capture any partial output before reaping
            try:
                stdout, stderr = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
            logger.error(
                "Skill timed out after %ds for %s:\npartial stdout: %s\npartial stderr: %s",
                TIMEOUT_SECONDS,
                message_ts,
                stdout[-2000:] if stdout else "(no stdout)",
                stderr[-2000:] if stderr else "(no stderr)",
            )
            return False

        if proc.returncode == 0:
            logger.info("Skill completed successfully for %s", message_ts)
            if stdout:
                logger.info("Skill output:\n%s", stdout)
            return True
        else:
            logger.error(
                "Skill failed (rc=%d) for %s:\nstdout: %s\nstderr: %s",
                proc.returncode,
                message_ts,
                stdout[:1000] if stdout else "(no stdout)",
                stderr[:1000] if stderr else "(no stderr)",
            )
            return False
    except FileNotFoundError:
        logger.error("claude CLI not found. Is it installed and in PATH?")
        return False
