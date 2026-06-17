/**
 * App — Root application component for Renine UI.
 *
 * Initializes the ChatWindow and VoiceIndicator components.
 * In Phase 1, this runs as vanilla TypeScript loaded via index.html.
 * Future phases will migrate to a React component tree.
 *
 * @module App
 */

import { ChatWindow } from './components/ChatWindow';
import { VoiceIndicator } from './components/VoiceIndicator';

/**
 * RenineApp is the root orchestrator for the UI.
 */
class RenineApp {
    private chatWindow: ChatWindow | null = null;
    private voiceIndicator: VoiceIndicator | null = null;

    /** Initialize all UI components after DOM is ready. */
    public init(): void {
        this.chatWindow = new ChatWindow();
        this.voiceIndicator = new VoiceIndicator();
        console.log('[Renine UI] App initialized — Phase 1');
    }
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const app = new RenineApp();
    app.init();
});

export { RenineApp };
