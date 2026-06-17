/**
 * Renine — Secure IPC Preload Bridge
 *
 * Exposes only explicitly whitelisted IPC channels to the renderer
 * via contextBridge.exposeInMainWorld. No arbitrary access to Node
 * APIs or shell commands from the renderer process.
 */

import { contextBridge, ipcRenderer } from 'electron';

/** Whitelisted IPC channels for renderer → main communication */
const SEND_CHANNELS = [
    'renine:send-message',
    'renine:voice-toggle',
    'renine:request-status',
] as const;

/** Whitelisted IPC channels for main → renderer communication */
const RECEIVE_CHANNELS = [
    'renine:receive-response',
    'renine:voice-state',
    'renine:status-update',
    'renine:error',
] as const;

type SendChannel = (typeof SEND_CHANNELS)[number];
type ReceiveChannel = (typeof RECEIVE_CHANNELS)[number];

contextBridge.exposeInMainWorld('renineAPI', {
    /**
     * Send a message from renderer to main process.
     * Only whitelisted channels are allowed.
     */
    send: (channel: SendChannel, data: unknown): void => {
        if (SEND_CHANNELS.includes(channel)) {
            ipcRenderer.send(channel, data);
        }
    },

    /**
     * Register a listener for messages from main process.
     * Only whitelisted channels are allowed.
     */
    on: (channel: ReceiveChannel, callback: (...args: unknown[]) => void): void => {
        if (RECEIVE_CHANNELS.includes(channel)) {
            ipcRenderer.on(channel, (_event, ...args) => callback(...args));
        }
    },

    /**
     * Send a message and wait for a response (invoke pattern).
     */
    invoke: async (channel: SendChannel, data: unknown): Promise<unknown> => {
        if (SEND_CHANNELS.includes(channel)) {
            return ipcRenderer.invoke(channel, data);
        }
        throw new Error(`Channel "${channel}" is not whitelisted.`);
    },
});
