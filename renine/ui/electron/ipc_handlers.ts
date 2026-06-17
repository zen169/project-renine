/**
 * Renine — IPC Event Handlers
 *
 * Handles IPC messages from the renderer process and bridges
 * them to the Python backend (via subprocess pipe in Phase 1).
 */

import { ipcMain, BrowserWindow } from 'electron';

/**
 * Register all IPC handlers for the main process.
 * Called once during app initialization.
 */
export function registerIpcHandlers(): void {
    ipcMain.on('renine:send-message', (_event, data: { text: string }) => {
        // Phase 1: Log the message. Python backend integration in future phases.
        console.log('[IPC] Message received:', data.text);

        // Echo back for now — will be replaced with Python bridge
        const windows = BrowserWindow.getAllWindows();
        if (windows.length > 0) {
            windows[0].webContents.send('renine:receive-response', {
                content: `[Phase 1 Echo] ${data.text}`,
                source: 'main_brain',
                timestamp: Date.now(),
            });
        }
    });

    ipcMain.on('renine:voice-toggle', (_event, data: { enabled: boolean }) => {
        console.log('[IPC] Voice toggle:', data.enabled);

        const windows = BrowserWindow.getAllWindows();
        if (windows.length > 0) {
            windows[0].webContents.send('renine:voice-state', {
                state: data.enabled ? 'listening' : 'idle',
            });
        }
    });

    ipcMain.handle('renine:request-status', async () => {
        return {
            status: 'online',
            phase: 1,
            version: '0.1.0',
        };
    });
}
