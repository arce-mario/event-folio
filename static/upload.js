/**
 * EventFolio - Upload JavaScript
 * Handles file selection, preview, and upload with progress
 */

// Configuration
const CONFIG = {
    maxFiles: 20,
    maxSizeMB: 10,
    allowedExtensions: ['.jpg', '.jpeg', '.png', '.heic', '.heif'],
    uploadEndpoint: '/upload'
};

// State
let selectedFiles = [];

// DOM Elements
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const previewSection = document.getElementById('previewSection');
const previewGrid = document.getElementById('previewGrid');
const fileCount = document.getElementById('fileCount');
const clearBtn = document.getElementById('clearBtn');
const uploadForm = document.getElementById('uploadForm');
const uploadBtn = document.getElementById('uploadBtn');
const progressSection = document.getElementById('progressSection');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const resultsSection = document.getElementById('resultsSection');
const resultsHeader = document.getElementById('resultsHeader');
const resultsList = document.getElementById('resultsList');
const newUploadBtn = document.getElementById('newUploadBtn');
const uploaderNameInput = document.getElementById('uploaderName');
const eventName = document.getElementById('eventName');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    updateFromUrlParams();
});

function setupEventListeners() {
    // Drag and drop
    dropZone.addEventListener('dragover', handleDragOver);
    dropZone.addEventListener('dragleave', handleDragLeave);
    dropZone.addEventListener('drop', handleDrop);
    
    // File input change
    fileInput.addEventListener('change', handleFileSelect);
    
    // Clear button
    clearBtn.addEventListener('click', clearFiles);
    
    // Form submit
    uploadForm.addEventListener('submit', handleSubmit);
    
    // New upload button
    newUploadBtn.addEventListener('click', resetUpload);
    
    // Uploader name input validation
    if (uploaderNameInput) {
        uploaderNameInput.addEventListener('input', updateUploadButton);
    }
}

function updateFromUrlParams() {
    const params = new URLSearchParams(window.location.search);
    const maxFiles = params.get('max_files');
    const maxSize = params.get('max_size');
    
    if (maxFiles) CONFIG.maxFiles = parseInt(maxFiles);
    if (maxSize) CONFIG.maxSizeMB = parseInt(maxSize);
}

// Drag and Drop Handlers
function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.add('dragover');
}

function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.remove('dragover');
}

function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.remove('dragover');
    
    const files = Array.from(e.dataTransfer.files);
    addFiles(files);
}

// File Selection
function handleFileSelect(e) {
    const files = Array.from(e.target.files);
    addFiles(files);
    // Reset input to allow selecting same files again
    e.target.value = '';
}

function addFiles(files) {
    const validFiles = files.filter(file => validateFile(file));
    
    // Check total count
    const totalCount = selectedFiles.length + validFiles.length;
    if (totalCount > CONFIG.maxFiles) {
        alert(`Máximo ${CONFIG.maxFiles} archivos permitidos. Tienes ${selectedFiles.length} seleccionados.`);
        return;
    }
    
    selectedFiles = [...selectedFiles, ...validFiles];
    updatePreview();
    updateUploadButton();
}

function validateFile(file) {
    // Check extension
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!CONFIG.allowedExtensions.includes(ext)) {
        console.warn(`Archivo rechazado (extensión): ${file.name}`);
        return false;
    }
    
    // Check size
    const sizeMB = file.size / (1024 * 1024);
    if (sizeMB > CONFIG.maxSizeMB) {
        alert(`"${file.name}" excede el límite de ${CONFIG.maxSizeMB} MB`);
        return false;
    }
    
    return true;
}

function removeFile(index) {
    selectedFiles.splice(index, 1);
    updatePreview();
    updateUploadButton();
}

function clearFiles() {
    selectedFiles = [];
    updatePreview();
    updateUploadButton();
}

// Preview
function updatePreview() {
    if (selectedFiles.length === 0) {
        previewSection.style.display = 'none';
        return;
    }
    
    previewSection.style.display = 'block';
    fileCount.textContent = selectedFiles.length;
    
    previewGrid.innerHTML = '';
    
    selectedFiles.forEach((file, index) => {
        const item = createPreviewItem(file, index);
        previewGrid.appendChild(item);
    });
}

function createPreviewItem(file, index) {
    const item = document.createElement('div');
    item.className = 'preview-item';
    
    // Create image preview
    const img = document.createElement('img');
    img.alt = file.name;
    
    // Use FileReader for preview
    const reader = new FileReader();
    reader.onload = (e) => {
        img.src = e.target.result;
    };
    reader.readAsDataURL(file);
    
    // Remove button
    const removeBtn = document.createElement('button');
    removeBtn.className = 'remove-btn';
    removeBtn.innerHTML = '×';
    removeBtn.onclick = (e) => {
        e.stopPropagation();
        removeFile(index);
    };
    
    // File size
    const sizeDiv = document.createElement('div');
    sizeDiv.className = 'file-size';
    sizeDiv.textContent = formatFileSize(file.size);
    
    item.appendChild(img);
    item.appendChild(removeBtn);
    item.appendChild(sizeDiv);
    
    return item;
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// Upload Button State
function updateUploadButton() {
    const hasFiles = selectedFiles.length > 0;
    const hasName = uploaderNameInput && uploaderNameInput.value.trim().length > 0;
    uploadBtn.disabled = !hasFiles || !hasName;
}


// Form Submit
async function handleSubmit(e) {
    e.preventDefault();
    
    if (selectedFiles.length === 0) return;
    
    const token = document.getElementById('token').value;
    if (!token) {
        alert('Error: Token de autenticación no encontrado');
        return;
    }
    
    // Get uploader name
    const uploaderName = uploaderNameInput ? uploaderNameInput.value.trim() : 'Anónimo';
    if (!uploaderName) {
        alert('Por favor ingresa tu nombre');
        return;
    }
    
    // Get event ID from hidden field
    const eventId = document.getElementById('eventId').value || 'default';
    
    // Prepare form data
    const formData = new FormData();
    formData.append('event_id', eventId);
    formData.append('uploader_name', uploaderName);
    
    selectedFiles.forEach(file => {
        formData.append('files', file);
    });
    
    // Show progress
    showProgress();
    
    try {
        const response = await uploadWithProgress(formData, token);
        showResults(response);
    } catch (error) {
        showError(error.message);
    }
}

async function uploadWithProgress(formData, token) {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        
        // Progress handler - Upload progress (sending data to server)
        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                // Only show up to 90% during upload, reserve 10% for server processing
                const percent = Math.round((e.loaded / e.total) * 90);
                updateProgress(percent, 'upload');
            }
        });
        
        // When upload completes, show "processing" state
        xhr.upload.addEventListener('load', () => {
            updateProgress(90, 'processing');
        });
        
        // Load handler - Server response received
        xhr.addEventListener('load', () => {
            updateProgress(100, 'complete');
            if (xhr.status >= 200 && xhr.status < 300) {
                try {
                    const response = JSON.parse(xhr.responseText);
                    resolve(response);
                } catch {
                    reject(new Error('Error al procesar respuesta del servidor'));
                }
            } else {
                try {
                    const error = JSON.parse(xhr.responseText);
                    reject(new Error(error.detail || `Error ${xhr.status}`));
                } catch {
                    reject(new Error(`Error ${xhr.status}: ${xhr.statusText}`));
                }
            }
        });
        
        // Error handler
        xhr.addEventListener('error', () => {
            reject(new Error('Error de conexión'));
        });
        
        // Timeout handler
        xhr.addEventListener('timeout', () => {
            reject(new Error('Tiempo de espera agotado'));
        });
        
        // Configure and send
        xhr.open('POST', `${CONFIG.uploadEndpoint}?token=${encodeURIComponent(token)}`);
        xhr.timeout = 300000; // 5 minutes
        xhr.send(formData);
    });
}

// Progress Display
function showProgress() {
    uploadForm.style.display = 'none';
    progressSection.style.display = 'block';
    resultsSection.style.display = 'none';
    
    progressFill.style.width = '0%';
    progressText.textContent = 'Subiendo fotos...';
}

function updateProgress(percent, stage = 'upload') {
    progressFill.style.width = percent + '%';
    
    if (stage === 'upload') {
        progressText.textContent = `Enviando fotos... ${percent}%`;
    } else if (stage === 'processing') {
        progressText.textContent = '⏳ Procesando y guardando en el servidor...';
        // Add pulsing animation to indicate ongoing work
        progressFill.style.animation = 'pulse 1.5s ease-in-out infinite';
    } else if (stage === 'complete') {
        progressText.textContent = '✅ Completado';
        progressFill.style.animation = 'none';
    }
}

// Results Display
function showResults(response) {
    progressSection.style.display = 'none';
    resultsSection.style.display = 'block';
    
    const uploaded = response.uploaded || 0;
    const failed = response.failed || 0;
    const total = uploaded + failed;
    
    // Determine status
    let statusClass, icon, title, message;
    
    if (failed === 0 && uploaded > 0) {
        statusClass = 'success';
        icon = '✅';
        title = '¡Fotos subidas!';
        message = `${uploaded} foto${uploaded > 1 ? 's' : ''} subida${uploaded > 1 ? 's' : ''} correctamente`;
    } else if (uploaded === 0) {
        statusClass = 'error';
        icon = '❌';
        title = 'Error al subir';
        message = 'No se pudo subir ninguna foto';
    } else {
        statusClass = 'partial';
        icon = '⚠️';
        title = 'Subida parcial';
        message = `${uploaded} de ${total} fotos subidas`;
    }
    
    resultsHeader.className = `results-header ${statusClass}`;
    resultsHeader.innerHTML = `
        <h2>${icon} ${title}</h2>
        <p>${message}</p>
    `;
    
    // Build results list
    resultsList.innerHTML = '';
    
    // Successful uploads
    if (response.files) {
        response.files.forEach(file => {
            const item = document.createElement('div');
            item.className = 'result-item success';
            item.innerHTML = `
                <span class="result-icon">✅</span>
                <div class="result-info">
                    <div class="result-name">${escapeHtml(file.original_name)}</div>
                    <div class="result-detail">${formatFileSize(file.size_bytes)} • ${file.saved_as}</div>
                </div>
            `;
            resultsList.appendChild(item);
        });
    }
    
    // Failed uploads
    if (response.errors) {
        response.errors.forEach(error => {
            const item = document.createElement('div');
            item.className = 'result-item error';
            item.innerHTML = `
                <span class="result-icon">❌</span>
                <div class="result-info">
                    <div class="result-name">${escapeHtml(error.filename)}</div>
                    <div class="result-detail">${escapeHtml(error.error)}</div>
                </div>
            `;
            resultsList.appendChild(item);
        });
    }
    
    // Clear selected files
    selectedFiles = [];
}

function showError(message) {
    progressSection.style.display = 'none';
    resultsSection.style.display = 'block';
    
    resultsHeader.className = 'results-header error';
    resultsHeader.innerHTML = `
        <h2>❌ Error</h2>
        <p>${escapeHtml(message)}</p>
    `;
    
    resultsList.innerHTML = '';
}

// Reset for new upload
function resetUpload() {
    selectedFiles = [];
    previewGrid.innerHTML = '';
    previewSection.style.display = 'none';
    resultsSection.style.display = 'none';
    progressSection.style.display = 'none';
    uploadForm.style.display = 'block';
    uploadBtn.disabled = true;
    
    // Reset file input
    fileInput.value = '';
}

// Utility
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
