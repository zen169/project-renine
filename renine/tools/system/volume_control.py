"""Volume control tool for Renine.

Controls system volume and mute states using inline C# loaded via PowerShell
invoked with subprocess.run(shell=False).
"""
from __future__ import annotations

import subprocess
from typing import Any

from renine.core.logging_config import get_logger
from renine.tools.permissions import PermissionLevel
from renine.tools.registry import BaseTool, ToolResult, register_tool

logger = get_logger(__name__)

# C# definition for Windows Audio Endpoint Volume control via COM.
_CSHARP_AUDIO_CODE = """
using System;
using System.Runtime.InteropServices;

[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioEndpointVolume {
    int f(); int g(); int h(); int i();
    int SetMasterVolumeLevelScalar(float fLevel, Guid pguidEventContext);
    int j();
    int GetMasterVolumeLevelScalar(out float pfLevel);
    int k(); int l(); int m(); int n();
    int SetMute(bool bMute, Guid pguidEventContext);
    int GetMute(out bool pbMute);
}

[Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDevice {
    int Activate(ref Guid id, int clsCtx, int activationParams, out IAudioEndpointVolume aev);
}

[Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDeviceEnumerator {
    int f();
    int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice endpoint);
}

[ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
class MMDeviceEnumeratorComObject { }

public class AudioController {
    private static IAudioEndpointVolume GetVolumeInterface() {
        var enumerator = new MMDeviceEnumeratorComObject() as IMMDeviceEnumerator;
        IMMDevice dev = null;
        enumerator.GetDefaultAudioEndpoint(0, 1, out dev);
        IAudioEndpointVolume epv = null;
        Guid epvid = typeof(IAudioEndpointVolume).GUID;
        dev.Activate(ref epvid, 23, 0, out epv);
        return epv;
    }
    public static void SetVolume(float level) {
        GetVolumeInterface().SetMasterVolumeLevelScalar(level / 100f, Guid.Empty);
    }
    public static float GetVolume() {
        float level = 0f;
        GetVolumeInterface().GetMasterVolumeLevelScalar(out level);
        return level * 100f;
    }
    public static void SetMute(bool mute) {
        GetVolumeInterface().SetMute(mute, Guid.Empty);
    }
    public static bool GetMute() {
        bool mute = false;
        GetVolumeInterface().GetMute(out mute);
        return mute;
    }
}
"""


def _run_ps_volume_command(cmd_text: str) -> str:
    """Compile C# helper and run the given command text in PowerShell.

    Args:
        cmd_text: PowerShell command to run.

    Returns:
        Stripped stdout string from command.
    """
    ps_script = f"""
$csharpCode = @'
{_CSHARP_AUDIO_CODE}
'@
Add-Type -TypeDefinition $csharpCode -ReferencedAssemblies "System.Runtime.InteropServices"
{cmd_text}
"""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script],
        capture_output=True,
        text=True,
        shell=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"PowerShell command failed: {result.stderr.strip()}")
    return result.stdout.strip()


@register_tool(
    name="volume_control",
    description="Control the Windows master system volume and mute status",
    permission_level=PermissionLevel.STANDARD,
    requires_confirmation=False,
)
class VolumeControlTool(BaseTool):
    """Tool to control Windows system volume."""

    def execute(self, action: str, level: int | None = None, **kwargs: Any) -> ToolResult:
        """Execute the volume control command.

        Args:
            action: Action to perform ('get', 'set', 'mute', 'unmute', 'is_muted').
            level: The target volume percentage (0 to 100), required if action is 'set'.
            **kwargs: Extra arguments.

        Returns:
            ToolResult containing success status and returned data.
        """
        try:
            action = action.lower().strip()
            if action == "get":
                out = _run_ps_volume_command("[AudioController]::GetVolume()")
                val = round(float(out))
                return ToolResult(success=True, data={"volume": val})

            if action == "set":
                if level is None:
                    return ToolResult(
                        success=False,
                        error="Level parameter is required when action is 'set'.",
                    )
                if not (0 <= level <= 100):
                    return ToolResult(
                        success=False,
                        error=f"Volume level must be between 0 and 100, got: {level}.",
                    )
                _run_ps_volume_command(f"[AudioController]::SetVolume({level})")
                return ToolResult(success=True, data={"volume": level, "status": "updated"})

            if action == "mute":
                _run_ps_volume_command("[AudioController]::SetMute($true)")
                return ToolResult(success=True, data={"muted": True})

            if action == "unmute":
                _run_ps_volume_command("[AudioController]::SetMute($false)")
                return ToolResult(success=True, data={"muted": False})

            if action == "is_muted":
                out = _run_ps_volume_command("[AudioController]::GetMute()")
                muted = out.lower() == "true"
                return ToolResult(success=True, data={"muted": muted})

            return ToolResult(
                success=False,
                error=f"Unknown volume action: {action}. Supported: get, set, mute, unmute, is_muted",
            )

        except Exception as e:
            logger.exception("volume_control_failed", action=action, level=level)
            return ToolResult(success=False, error=str(e))
