document.addEventListener('DOMContentLoaded', function() {
  // DOM elements
  const fileInput = document.getElementById('fileInput');
  const browseButton = document.getElementById('browseButton');
  const dropZone = document.getElementById('dropZone');
  const fileInfo = document.getElementById('fileInfo');
  const fileName = document.getElementById('fileName');
  const removeFile = document.getElementById('removeFile');
  const uploadForm = document.getElementById('uploadForm');
  const uploadButton = document.getElementById('uploadButton');
  const uploadSpinner = document.getElementById('uploadSpinner');
  const uploadText = document.getElementById('uploadText');
  const toast = document.getElementById('toast');
  const toastTitle = document.getElementById('toastTitle');
  const toastMessage = document.getElementById('toastMessage');

  // Initialize Bootstrap toast if available
  let toastInstance;
  if (window.bootstrap && toast) {
    toastInstance = new bootstrap.Toast(toast);
  }

  // Show notification
  function showNotification(title, message, delay = 3000) {
    if (!toast) return;

    toastTitle.textContent = title;
    toastMessage.textContent = message;
    toast.setAttribute('data-bs-delay', delay);

    if (toastInstance) {
      toastInstance.show();
    }
  }

  // Browse button click
  if (browseButton) {
    browseButton.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      if (fileInput) {
        fileInput.click();
      }
    });
  }

  // Click on drop zone to browse files
  if (dropZone) {
    dropZone.addEventListener('click', function(e) {
      // Don't trigger if clicking on buttons or the file info area
      if (e.target === dropZone || e.target.closest('.upload-prompt') && !e.target.closest('#browseButton')) {
        fileInput.click();
      }
    });
  }

  // File input change
  if (fileInput) {
    fileInput.addEventListener('change', function() {
      if (this.files && this.files[0]) {
        handleFileSelection(this.files[0]);
      }
    });
  }

  // Drag and drop functionality
  if (dropZone) {
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
      dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
      e.preventDefault();
      e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
      dropZone.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
      dropZone.addEventListener(eventName, unhighlight, false);
    });

    function highlight() {
      dropZone.classList.add('drag-over');
    }

    function unhighlight() {
      dropZone.classList.remove('drag-over');
    }

    dropZone.addEventListener('drop', function(e) {
      const dt = e.dataTransfer;
      if (dt.files && dt.files[0]) {
        handleFileSelection(dt.files[0]);
      }
    });
  }

  // Handle file selection
  function handleFileSelection(file) {
    if (!file) return;

    // Check if file is audio or video
    if (!file.type.match('audio.*') && !file.type.match('video.*')) {
      showNotification('Invalid File', 'Please upload an audio or video file.');
      return;
    }

    // Update file name display
    if (fileName) {
      fileName.textContent = file.name;
    }

    // Hide upload prompt and show file info
    const uploadPrompt = document.querySelector('.upload-prompt');
    if (uploadPrompt) {
      uploadPrompt.classList.add('d-none');
    }

    if (fileInfo) {
      fileInfo.classList.remove('d-none');
    }

    // Add animation to the selected file if anime.js is available
    if (window.anime && fileInfo) {
      anime({
        targets: fileInfo,
        opacity: [0, 1],
        translateY: [20, 0],
        easing: 'easeOutElastic(1, .8)',
        duration: 800
      });
    }
  }

  // Remove file
  if (removeFile) {
    removeFile.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation(); // Prevent triggering dropZone click
      if (fileInput) {
        fileInput.value = '';
      }
      if (fileInfo) {
        fileInfo.classList.add('d-none');
      }
      const uploadPrompt = document.querySelector('.upload-prompt');
      if (uploadPrompt) {
        uploadPrompt.classList.remove('d-none');
      }
    });
  }

  // Form submission
  if (uploadForm) {
    uploadForm.addEventListener('submit', function(e) {
      if (!fileInput || !fileInput.files.length) {
        e.preventDefault();
        showNotification('No File Selected', 'Please select a file to upload.');
        return;
      }

      // Show loading state
      if (uploadButton) {
        uploadButton.disabled = true;
      }
      if (uploadSpinner) {
        uploadSpinner.classList.remove('d-none');
      }
      if (uploadText) {
        uploadText.textContent = 'Processing...';
      }
    });
  }

  // Copy to clipboard functionality for summary page
  const copyButton = document.getElementById('copyButton');
  const summaryContent = document.getElementById('summaryContent');

  if (copyButton && summaryContent) {
    copyButton.addEventListener('click', function() {
      const summaryText = summaryContent.innerText;
      navigator.clipboard.writeText(summaryText).then(function() {
        showNotification('Copied', 'Summary copied to clipboard');
      });
    });
  }

  // Download summary functionality
  const downloadButton = document.getElementById('downloadButton');

  if (downloadButton && summaryContent) {
    downloadButton.addEventListener('click', function(e) {
      // If the button is an anchor with href, let the default behavior work
      if (downloadButton.getAttribute('href')) {
        return;
      }

      e.preventDefault();
      const summaryText = summaryContent.innerText;
      const blob = new Blob([summaryText], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'media-summary.txt';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    });
  }

  // Add entrance animations if anime.js is available
  if (window.anime) {
    anime({
      targets: '.upload-card',
      opacity: [0, 1],
      translateY: [50, 0],
      easing: 'easeOutExpo',
      duration: 1200,
      delay: 300
    });
  }
});