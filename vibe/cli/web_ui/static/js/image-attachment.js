/**
 * Image Attachment Module
 *
 * Handles clipboard paste, file selection, and validation for image attachments.
 * Supports PNG, JPEG, and WEBP formats with 2MB size limit.
 */

export class ImageAttachmentHandler {
    /**
     * Create an image attachment handler
     * @param {Object} options - Configuration options
     * @param {HTMLElement} previewContainer - Image preview container element
     * @param {HTMLImageElement} previewImg - Preview image element
     * @param {HTMLInputElement} fileInput - File input element
     * @param {Function} onImageAttached - Callback when image is attached
     * @param {Function} onImageRemoved - Callback when image is removed
     * @param {Function} onError - Callback for error messages
     */
    constructor({
        previewContainer,
        previewImg,
        fileInput,
        onImageAttached,
        onImageRemoved,
        onError
    }) {
        this.previewContainer = previewContainer;
        this.previewImg = previewImg;
        this.fileInput = fileInput;
        this.onImageAttached = onImageAttached;
        this.onImageRemoved = onImageRemoved;
        this.onError = onError;

        this.attachedImage = null;
        this.allowedTypes = ['image/png', 'image/jpeg', 'image/webp'];
        this.maxSize = 2 * 1024 * 1024; // 2MB
    }

    /**
     * Handle paste event for image attachment from clipboard
     * @param {ClipboardEvent} event
     * @returns {boolean} - True if image was handled
     */
    handlePaste(event) {
        const items = event.clipboardData?.items;
        if (!items) return false;

        for (const item of items) {
            if (item.type?.startsWith('image/')) {
                event.preventDefault();
                const file = item.getAsFile();
                this.processImage(file);
                return true;
            }
        }
        return false;
    }

    /**
     * Handle file selection from file input
     * @param {Event} event
     */
    handleFileSelect(event) {
        const file = event.target.files?.[0];
        if (file) {
            this.processImage(file);
        }
        // Reset input so same file can be selected again
        event.target.value = '';
    }

    /**
     * Process image: validate and convert to base64
     * @param {File} file
     */
    processImage(file) {
        // Validate format
        if (!this.allowedTypes.includes(file.type)) {
            this.onError('Unsupported image format. Please use PNG, JPEG, or WEBP.');
            return;
        }

        // Validate size
        if (file.size > this.maxSize) {
            this.onError('Image too large. Maximum size is 2MB.');
            return;
        }

        // Convert to base64
        const reader = new FileReader();
        reader.onload = (e) => {
            const base64Data = e.target.result;
            this.attachImage(base64Data, file.type);
        };
        reader.readAsDataURL(file);
    }

    /**
     * Attach image and show preview
     * @param {string} base64Data - Full data URL
     * @param {string} mimeType - Image mime type
     */
    attachImage(base64Data, mimeType) {
        this.attachedImage = {
            data: base64Data.split(',')[1], // Strip data:image/...;base64, prefix
            mime_type: mimeType
        };
        this.showPreview(base64Data);
        this.onImageAttached(this.attachedImage);
    }

    /**
     * Show image preview
     * @param {string} base64Data - Full data URL
     */
    showPreview(base64Data) {
        this.previewImg.src = base64Data;
        this.previewContainer.style.display = 'flex';
    }

    /**
     * Remove attached image and hide preview
     */
    removeImage() {
        if (this.attachedImage) {
            this.attachedImage = null;
            this.previewImg.src = '';
            this.previewContainer.style.display = 'none';
            this.onImageRemoved();
        }
    }

    /**
     * Get attached image data for sending
     * @returns {Object|null} - Image data or null
     */
    getImageData() {
        return this.attachedImage;
    }

    /**
     * Clear attachment after sending
     */
    clear() {
        this.removeImage();
    }
}
