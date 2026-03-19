/**
 * Tests for ImageAttachmentHandler module
 * 
 * Tests clipboard paste, file selection, validation, and image attachment logic.
 */

import { ImageAttachmentHandler } from '../../vibe/cli/web_ui/static/js/image-attachment.js';

describe('ImageAttachmentHandler', () => {
    let handler;
    let mockPreviewContainer;
    let mockPreviewImg;
    let mockFileInput;
    let onImageAttachedSpy;
    let onImageRemovedSpy;
    let onErrorSpy;

    beforeEach(() => {
        // Mock DOM elements
        mockPreviewContainer = {
            style: { display: 'none' },
            classList: { add: jest.fn(), remove: jest.fn() }
        };
        
        mockPreviewImg = {
            src: '',
            onload: null
        };
        
        mockFileInput = {
            value: '',
            click: jest.fn(),
            files: []
        };
        
        // Mock callbacks
        onImageAttachedSpy = jest.fn();
        onImageRemovedSpy = jest.fn();
        onErrorSpy = jest.fn();
        
        // Create handler instance
        handler = new ImageAttachmentHandler({
            previewContainer: mockPreviewContainer,
            previewImg: mockPreviewImg,
            fileInput: mockFileInput,
            onImageAttached: onImageAttachedSpy,
            onImageRemoved: onImageRemovedSpy,
            onError: onErrorSpy
        });
        
        // Mock FileReader for base64 conversion
        global.FileReader = class {
            constructor() {
                this.onload = null;
                this.onerror = null;
            }
            readAsDataURL(file) {
                // Simulate async reading with data URL
                setTimeout(() => {
                    if (this.onload) {
                        this.onload({
                            target: {
                                result: `data:${file.type};base64,${file.mockBase64 || 'mockBase64Data'}`
                            }
                        });
                    }
                }, 0);
            }
        };
    });

    describe('Constructor', () => {
        test('should initialize with null attachedImage', () => {
            expect(handler.attachedImage).toBeNull();
        });

        test('should set allowedTypes to PNG, JPEG, WEBP', () => {
            expect(handler.allowedTypes).toEqual(['image/png', 'image/jpeg', 'image/webp']);
        });

        test('should set maxSize to 2MB', () => {
            expect(handler.maxSize).toBe(2 * 1024 * 1024);
        });
    });

    describe('handlePaste', () => {
        test('should return false when no clipboard items', () => {
            const result = handler.handlePaste({ clipboardData: { items: null } });
            expect(result).toBe(false);
        });

        test('should return false when no image items', () => {
            const mockItem = { type: 'text/plain' };
            const result = handler.handlePaste({ 
                clipboardData: { items: [mockItem] } 
            });
            expect(result).toBe(false);
        });

        test('should handle image paste and call processImage', () => {
            const mockFile = {
                type: 'image/png',
                size: 1024,
                mockBase64: 'testImageData'
            };
            
            const mockItem = {
                type: 'image/png',
                getAsFile: () => mockFile
            };
            
            const mockEvent = {
                clipboardData: { items: [mockItem] },
                preventDefault: jest.fn()
            };
            
            // Run microtasks to complete FileReader
            handler.handlePaste(mockEvent);
            return new Promise((resolve) => {
                setTimeout(() => {
                    expect(mockEvent.preventDefault).toHaveBeenCalled();
                    expect(handler.attachedImage).toEqual({
                        data: 'testImageData',
                        mime_type: 'image/png'
                    });
                    expect(onImageAttachedSpy).toHaveBeenCalledWith(handler.attachedImage);
                    resolve();
                }, 10);
            });
        });
    });

    describe('handleFileSelect', () => {
        test('should process selected file', () => {
            const mockFile = {
                type: 'image/jpeg',
                size: 1024,
                mockBase64: 'fileImageData'
            };
            
            mockFileInput.files = [mockFile];
            
            handler.handleFileSelect({ target: mockFileInput });
            
            return new Promise((resolve) => {
                setTimeout(() => {
                    expect(handler.attachedImage).toEqual({
                        data: 'fileImageData',
                        mime_type: 'image/jpeg'
                    });
                    expect(mockFileInput.value).toBe(''); // Reset after selection
                    resolve();
                }, 10);
            });
        });

        test('should reset file input value after selection', () => {
            const mockFile = {
                type: 'image/png',
                size: 1024,
                mockBase64: 'test'
            };
            
            mockFileInput.files = [mockFile];
            mockFileInput.value = '/path/to/file.png';
            
            handler.handleFileSelect({ target: mockFileInput });
            
            return new Promise((resolve) => {
                setTimeout(() => {
                    expect(mockFileInput.value).toBe('');
                    resolve();
                }, 10);
            });
        });
    });

    describe('processImage', () => {
        test('should reject unsupported format', () => {
            const mockFile = {
                type: 'image/gif',
                size: 1024
            };
            
            handler.processImage(mockFile);
            
            expect(onErrorSpy).toHaveBeenCalledWith(
                'Unsupported image format. Please use PNG, JPEG, or WEBP.'
            );
            expect(handler.attachedImage).toBeNull();
        });

        test('should reject image larger than 2MB', () => {
            const mockFile = {
                type: 'image/png',
                size: 2 * 1024 * 1024 + 1 // 2MB + 1 byte
            };
            
            handler.processImage(mockFile);
            
            expect(onErrorSpy).toHaveBeenCalledWith(
                'Image too large. Maximum size is 2MB.'
            );
            expect(handler.attachedImage).toBeNull();
        });

        test('should accept image exactly at 2MB limit', (done) => {
            const mockFile = {
                type: 'image/webp',
                size: 2 * 1024 * 1024, // Exactly 2MB
                mockBase64: 'atLimitData'
            };
            
            handler.processImage(mockFile);
            
            setTimeout(() => {
                expect(handler.attachedImage).not.toBeNull();
                expect(handler.attachedImage.mime_type).toBe('image/webp');
                expect(onErrorSpy).not.toHaveBeenCalled();
                done();
            }, 10);
        });

        test('should convert valid image to base64 and attach', (done) => {
            const mockFile = {
                type: 'image/png',
                size: 1024,
                mockBase64: 'validImageData'
            };
            
            handler.processImage(mockFile);
            
            setTimeout(() => {
                expect(handler.attachedImage).toEqual({
                    data: 'validImageData',
                    mime_type: 'image/png'
                });
                expect(mockPreviewContainer.style.display).toBe('flex');
                expect(onImageAttachedSpy).toHaveBeenCalled();
                done();
            }, 10);
        });
    });

    describe('removeImage', () => {
        test('should clear attached image and hide preview', (done) => {
            // First attach an image
            const mockFile = {
                type: 'image/png',
                size: 1024,
                mockBase64: 'testData'
            };
            
            handler.processImage(mockFile);
            
            setTimeout(() => {
                expect(handler.attachedImage).not.toBeNull();
                
                // Now remove it
                handler.removeImage();
                
                expect(handler.attachedImage).toBeNull();
                expect(mockPreviewImg.src).toBe('');
                expect(mockPreviewContainer.style.display).toBe('none');
                expect(onImageRemovedSpy).toHaveBeenCalled();
                done();
            }, 10);
        });

        test('should handle remove when no image attached', () => {
            expect(handler.attachedImage).toBeNull();
            handler.removeImage(); // Should not throw
            expect(onImageRemovedSpy).not.toHaveBeenCalled();
        });
    });

    describe('getImageData', () => {
        test('should return null when no image attached', () => {
            expect(handler.getImageData()).toBeNull();
        });

        test('should return image data when attached', (done) => {
            const mockFile = {
                type: 'image/jpeg',
                size: 1024,
                mockBase64: 'imageData'
            };
            
            handler.processImage(mockFile);
            
            setTimeout(() => {
                expect(handler.getImageData()).toEqual({
                    data: 'imageData',
                    mime_type: 'image/jpeg'
                });
                done();
            }, 10);
        });
    });

    describe('clear', () => {
        test('should clear attached image', (done) => {
            const mockFile = {
                type: 'image/png',
                size: 1024,
                mockBase64: 'testData'
            };
            
            handler.processImage(mockFile);
            
            setTimeout(() => {
                expect(handler.attachedImage).not.toBeNull();
                
                handler.clear();
                
                expect(handler.attachedImage).toBeNull();
                expect(onImageRemovedSpy).toHaveBeenCalled();
                done();
            }, 10);
        });
    });

    describe('showPreview', () => {
        test('should set image src and show container', () => {
            const testDataUrl = 'data:image/png;base64,testData';
            
            handler.showPreview(testDataUrl);
            
            expect(mockPreviewImg.src).toBe(testDataUrl);
            expect(mockPreviewContainer.style.display).toBe('flex');
        });
    });
});
