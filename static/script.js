document.addEventListener('DOMContentLoaded', () => {
    // Get references to all the important HTML elements
    const videoUpload = document.getElementById('video-upload');
    const fileNameDisplay = document.getElementById('file-name');
    const languageSelect = document.getElementById('language-select');
    const generateBtn = document.getElementById('generate-btn');
    const resultsSection = document.getElementById('results-section');
    const statusMessage = document.getElementById('status-message');
    const loader = document.getElementById('loader');
    const videoContainer = document.getElementById('video-container');
    const resultVideo = document.getElementById('result-video');
    const downloadLink = document.getElementById('download-link');
    const errorMessage = document.getElementById('error-message');

    let selectedFile = null;

    // Update the file name display when a user selects a video
    videoUpload.addEventListener('change', () => {
        if (videoUpload.files.length > 0) {
            selectedFile = videoUpload.files[0];
            fileNameDisplay.textContent = selectedFile.name;
        } else {
            selectedFile = null;
            fileNameDisplay.textContent = 'Click to select a file...';
        }
    });

    // Handle the click event for the generate button
    generateBtn.addEventListener('click', async () => {
        if (!selectedFile) {
            alert('Please select a video file first!');
            return;
        }

        // --- Prepare the UI for processing ---
        generateBtn.disabled = true;
        generateBtn.textContent = 'Processing...';
        resultsSection.classList.remove('hidden');
        videoContainer.classList.add('hidden');
        errorMessage.classList.add('hidden');
        loader.classList.remove('hidden');
        statusMessage.textContent = 'Uploading video...';

        // --- Create a FormData object to send the file and language ---
        const formData = new FormData();
        formData.append('video', selectedFile);
        formData.append('language', languageSelect.value);

        try {
            // --- Make the API call to the Flask backend ---
            statusMessage.textContent = 'Video uploaded. Starting AI processing... This might take a while.';
            
            const response = await fetch('/process-video', {
                method: 'POST',
                body: formData,
            });

            const result = await response.json();

            // Hide the loader
            loader.classList.add('hidden');

            if (response.ok) {
                // --- Success! Display the results ---
                statusMessage.textContent = 'Processing complete!';
                videoContainer.classList.remove('hidden');
                
                // Set the source for the video player and download link
                resultVideo.src = result.video_url;
                downloadLink.href = result.video_url;
                downloadLink.download = result.video_url.split('/').pop(); // Set filename
            } else {
                // --- Handle errors from the backend ---
                throw new Error(result.error || 'An unknown error occurred.');
            }

        } catch (error) {
            // --- Display any caught errors to the user ---
            loader.classList.add('hidden');
            errorMessage.textContent = `Error: ${error.message}`;
            errorMessage.classList.remove('hidden');
            statusMessage.textContent = 'An error occurred.';
        } finally {
            // --- Re-enable the button regardless of outcome ---
            generateBtn.disabled = false;
            generateBtn.textContent = 'Generate Subtitled Video';
        }
    });
});
