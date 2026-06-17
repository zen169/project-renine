/**
 * ChatWindow — Main chat interface component for Renine.
 *
 * Renders the message history, input field, and send button.
 * Communicates with the Python backend via the renineAPI bridge
 * exposed by preload.ts.
 *
 * Phase 1: Inline rendering via index.html script tags.
 * Future phases will migrate to a proper React/TSX build pipeline.
 *
 * @module ChatWindow
 */

// Type declarations for the renineAPI bridge
declare global {
    interface Window {
        renineAPI?: {
            send: (channel: string, data: unknown) => void;
            on: (channel: string, callback: (...args: any[]) => void) => void;
            invoke: (channel: string, data: unknown) => Promise<unknown>;
        };
    }
}

interface ChatMessage {
    role: 'user' | 'assistant' | 'system';
    content: string;
    timestamp: number;
}

/**
 * ChatWindow manages the message display and user input.
 *
 * Responsibilities:
 * - Renders message bubbles in the message area
 * - Handles text input and submission
 * - Sends messages via IPC to the Python backend
 * - Receives and displays assistant responses
 * - Shows thinking indicator while processing
 */
class ChatWindow {
    private messages: ChatMessage[] = [];
    private messageArea: HTMLElement;
    private inputField: HTMLInputElement;
    private sendButton: HTMLElement;

    constructor() {
        this.messageArea = document.getElementById('message-area')!;
        this.inputField = document.getElementById('message-input') as HTMLInputElement;
        this.sendButton = document.getElementById('send-button')!;

        this.bindEvents();
        this.bindIPC();
    }

    /** Bind DOM event listeners for input and send. */
    private bindEvents(): void {
        this.sendButton.addEventListener('click', () => this.sendMessage());
        this.inputField.addEventListener('keydown', (e: KeyboardEvent) => {
            if (e.key === 'Enter') this.sendMessage();
        });
    }

    /** Bind IPC listeners for backend responses. */
    private bindIPC(): void {
        if (!window.renineAPI) return;

        window.renineAPI.on('renine:receive-response', (data: any) => {
            this.removeThinkingIndicator();
            this.addMessage('assistant', data.content);
        });
    }

    /** Send the current input text to the backend. */
    public sendMessage(): void {
        const text = this.inputField.value.trim();
        if (!text) return;

        this.addMessage('user', text);
        this.inputField.value = '';
        this.showThinkingIndicator();

        // Remove welcome message on first send
        const welcome = this.messageArea.querySelector('.welcome-message');
        if (welcome) welcome.remove();

        if (window.renineAPI) {
            window.renineAPI.send('renine:send-message', { text });
        }
    }

    /** Add a message to the display. */
    public addMessage(role: 'user' | 'assistant' | 'system', content: string): void {
        const message: ChatMessage = { role, content, timestamp: Date.now() };
        this.messages.push(message);

        const bubble = document.createElement('div');
        bubble.className = `message-bubble ${role}`;
        bubble.textContent = content;
        this.messageArea.appendChild(bubble);
        this.messageArea.scrollTop = this.messageArea.scrollHeight;
    }

    /** Show the typing/thinking indicator. */
    private showThinkingIndicator(): void {
        const indicator = document.createElement('div');
        indicator.className = 'thinking-indicator';
        indicator.id = 'thinking';
        indicator.innerHTML = '<span></span><span></span><span></span>';
        this.messageArea.appendChild(indicator);
        this.messageArea.scrollTop = this.messageArea.scrollHeight;
    }

    /** Remove the thinking indicator. */
    private removeThinkingIndicator(): void {
        const indicator = document.getElementById('thinking');
        if (indicator) indicator.remove();
    }
}

export { ChatWindow, ChatMessage };
