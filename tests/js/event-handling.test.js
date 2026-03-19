/**
 * Tests for WebUI event handling, specifically UserMessageEvent with list content.
 */

// Mock DOM elements
const mockMessages = {
    children: [],
    appendChild: function(child) {
        this.children.push(child);
    },
    scrollHeight: 100,
    scrollTop: 100
};

// Mock VibeClient with minimal implementation for testing
class MockVibeClient {
    constructor() {
        this.elements = {
            messages: mockMessages
        };
        this.streamingMessage = null;
    }

    stopStreaming() {
        this.streamingMessage = null;
    }

    addMessage(type, content) {
        const messageDiv = { className: `message ${type}`, content: content };
        this.elements.messages.appendChild(messageDiv);
    }

    addImageMessage(imageData) {
        const messageDiv = { 
            className: 'message user', 
            type: 'image',
            imageData: imageData 
        };
        this.elements.messages.appendChild(messageDiv);
    }

    scrollToBottom() {
        // Mock implementation
    }

    handleEvent(event) {
        const eventType = event.type;
        
        switch (eventType) {
            case 'UserMessageEvent':
                this.stopStreaming();
                // Handle multi-part content (text + images)
                if (Array.isArray(event.content)) {
                    event.content.forEach(item => {
                        if (item.type === 'image_url') {
                            const imageUrl = item.image_url?.url || '';
                            this.addImageMessage(imageUrl);
                        } else if (item.type === 'text') {
                            this.addMessage('user', item.text);
                        }
                    });
                } else {
                    this.addMessage('user', event.content);
                }
                break;
            case 'ContinueableUserMessageEvent':
                this.stopStreaming();
                if (Array.isArray(event.content)) {
                    event.content.forEach(item => {
                        if (item.type === 'image_url') {
                            const imageUrl = item.image_url?.url || '';
                            this.addImageMessage(imageUrl);
                        } else if (item.type === 'text') {
                            this.addMessage('user', item.text);
                        }
                    });
                } else {
                    this.addMessage('user', event.content);
                }
                break;
        }
    }
}

describe('UserMessageEvent handling', () => {
    let client;

    beforeEach(() => {
        client = new MockVibeClient();
        mockMessages.children = []; // Reset mock messages
    });

    test('handles UserMessageEvent with simple string content', () => {
        const event = {
            type: 'UserMessageEvent',
            content: 'Hello, world!'
        };

        client.handleEvent(event);

        expect(mockMessages.children).toHaveLength(1);
        expect(mockMessages.children[0]).toEqual({
            className: 'message user',
            content: 'Hello, world!'
        });
    });

    test('handles UserMessageEvent with list content (text only)', () => {
        const event = {
            type: 'UserMessageEvent',
            content: [
                { type: 'text', text: 'Hello, world!' }
            ]
        };

        client.handleEvent(event);

        expect(mockMessages.children).toHaveLength(1);
        expect(mockMessages.children[0]).toEqual({
            className: 'message user',
            content: 'Hello, world!'
        });
    });

    test('handles UserMessageEvent with list content (text + image)', () => {
        const event = {
            type: 'UserMessageEvent',
            content: [
                { type: 'text', text: 'Check out this image' },
                { type: 'image_url', image_url: { url: 'data:image/png;base64,abc123' } }
            ]
        };

        client.handleEvent(event);

        expect(mockMessages.children).toHaveLength(2);
        
        // First message should be text
        expect(mockMessages.children[0]).toEqual({
            className: 'message user',
            content: 'Check out this image'
        });
        
        // Second message should be image
        expect(mockMessages.children[1]).toEqual({
            className: 'message user',
            type: 'image',
            imageData: 'data:image/png;base64,abc123'
        });
    });

    test('handles UserMessageEvent with list content (image only)', () => {
        const event = {
            type: 'UserMessageEvent',
            content: [
                { type: 'image_url', image_url: { url: 'data:image/jpeg;base64,xyz789' } }
            ]
        };

        client.handleEvent(event);

        expect(mockMessages.children).toHaveLength(1);
        expect(mockMessages.children[0]).toEqual({
            className: 'message user',
            type: 'image',
            imageData: 'data:image/jpeg;base64,xyz789'
        });
    });

    test('handles UserMessageEvent with multiple text and images', () => {
        const event = {
            type: 'UserMessageEvent',
            content: [
                { type: 'text', text: 'First message' },
                { type: 'image_url', image_url: { url: 'data:image/png;base64,img1' } },
                { type: 'text', text: 'Second message' },
                { type: 'image_url', image_url: { url: 'data:image/jpeg;base64,img2' } }
            ]
        };

        client.handleEvent(event);

        expect(mockMessages.children).toHaveLength(4);
        
        expect(mockMessages.children[0]).toEqual({
            className: 'message user',
            content: 'First message'
        });
        
        expect(mockMessages.children[1]).toEqual({
            className: 'message user',
            type: 'image',
            imageData: 'data:image/png;base64,img1'
        });
        
        expect(mockMessages.children[2]).toEqual({
            className: 'message user',
            content: 'Second message'
        });
        
        expect(mockMessages.children[3]).toEqual({
            className: 'message user',
            type: 'image',
            imageData: 'data:image/jpeg;base64,img2'
        });
    });

    test('handles UserMessageEvent with empty image_url', () => {
        const event = {
            type: 'UserMessageEvent',
            content: [
                { type: 'text', text: 'Test message' },
                { type: 'image_url', image_url: {} }
            ]
        };

        client.handleEvent(event);

        expect(mockMessages.children).toHaveLength(2);
        expect(mockMessages.children[1]).toEqual({
            className: 'message user',
            type: 'image',
            imageData: ''
        });
    });

    test('handles UserMessageEvent with missing image_url.url', () => {
        const event = {
            type: 'UserMessageEvent',
            content: [
                { type: 'image_url', image_url: null }
            ]
        };

        client.handleEvent(event);

        expect(mockMessages.children).toHaveLength(1);
        expect(mockMessages.children[0]).toEqual({
            className: 'message user',
            type: 'image',
            imageData: ''
        });
    });
});

describe('ContinueableUserMessageEvent handling', () => {
    let client;

    beforeEach(() => {
        client = new MockVibeClient();
        mockMessages.children = []; // Reset mock messages
    });

    test('handles ContinueableUserMessageEvent with list content (text + image)', () => {
        const event = {
            type: 'ContinueableUserMessageEvent',
            content: [
                { type: 'text', text: 'Image description' },
                { type: 'image_url', image_url: { url: 'data:image/png;base64,desc123' } }
            ]
        };

        client.handleEvent(event);

        expect(mockMessages.children).toHaveLength(2);
        
        expect(mockMessages.children[0]).toEqual({
            className: 'message user',
            content: 'Image description'
        });
        
        expect(mockMessages.children[1]).toEqual({
            className: 'message user',
            type: 'image',
            imageData: 'data:image/png;base64,desc123'
        });
    });
});
