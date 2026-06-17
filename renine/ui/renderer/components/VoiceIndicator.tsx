/**
 * VoiceIndicator — Visual feedback for voice activity.
 *
 * Displays the current voice state:
 * - Hidden when idle
 * - Animated wave bars when listening
 * - Pulsing when processing
 *
 * @module VoiceIndicator
 */

type VoiceState = 'idle' | 'listening' | 'processing' | 'speaking';

/**
 * VoiceIndicator manages the visual feedback for the voice pipeline.
 */
class VoiceIndicator {
    private container: HTMLElement;
    private label: HTMLElement;
    private state: VoiceState = 'idle';

    constructor() {
        this.container = document.getElementById('voice-indicator')!;
        this.label = this.container.querySelector('.voice-label')!;
        this.bindIPC();
    }

    /** Bind IPC listeners for voice state changes. */
    private bindIPC(): void {
        if (!window.renineAPI) return;

        window.renineAPI.on('renine:voice-state', (data: { state: VoiceState }) => {
            this.setState(data.state);
        });
    }

    /** Update the voice indicator state. */
    public setState(state: VoiceState): void {
        this.state = state;

        switch (state) {
            case 'idle':
                this.container.classList.add('hidden');
                break;
            case 'listening':
                this.container.classList.remove('hidden');
                this.label.textContent = 'Listening...';
                break;
            case 'processing':
                this.container.classList.remove('hidden');
                this.label.textContent = 'Processing...';
                break;
            case 'speaking':
                this.container.classList.remove('hidden');
                this.label.textContent = 'Speaking...';
                break;
        }
    }

    /** Get the current voice state. */
    public getState(): VoiceState {
        return this.state;
    }
}

export { VoiceIndicator, VoiceState };
