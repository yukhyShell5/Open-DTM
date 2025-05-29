<template>
  <div class="form-container">
    <h1>Fuzzing Job Submission</h1>
    <form @submit.prevent="submitJob">
      <div class="form-group">
        <label for="url">URL:</label>
        <input type="text" id="url" v-model="url" />
      </div>

      <div class="form-group">
        <label for="method">Method:</label>
        <select id="method" v-model="method">
          <option value="POST">POST</option>
          <option value="GET">GET</option>
          <option value="PUT">PUT</option>
          <option value="DELETE">DELETE</option>
          <option value="HEAD">HEAD</option>
          <option value="OPTIONS">OPTIONS</option>
          <option value="PATCH">PATCH</option>
        </select>
      </div>

      <div class="form-group">
        <label for="wordlist">Wordlist:</label>
        <input type="file" id="wordlist" @change="handleFileUpload" />
      </div>

      <div class="form-group">
        <label for="hashFormat">Hash Format:</label>
        <select id="hashFormat" v-model="hashFormat">
          <option value="SHA256">SHA256</option>
          <option value="MD5">MD5</option>
          <option value="SHA1">SHA1</option>
          <option value="SHA384">SHA384</option>
          <option value="SHA512">SHA512</option>
          <option value="BCRYPT">BCRYPT</option>
          <option value="SCRYPT">SCRYPT</option>
        </select>
      </div>

      <button type="submit">Submit Job</button>
    </form>

    <div v-if="responseMessage" class="message success-message">
      {{ responseMessage }}
    </div>
    <div v-if="errorMessage" class="message error-message">
      {{ errorMessage }}
    </div>
  </div>
</template>

<script>
import { ref } from 'vue';

export default {
  setup() {
    // Reactive variables for form inputs and messages
    const url = ref('');
    const method = ref('POST');
    const wordlistFile = ref(null);
    const hashFormat = ref('SHA256');
    const responseMessage = ref('');
    const errorMessage = ref('');

    // Handles file selection for the wordlist
    const handleFileUpload = (event) => {
      if (event.target.files && event.target.files[0]) {
        wordlistFile.value = event.target.files[0];
      } else {
        wordlistFile.value = null;
      }
    };

    // Handles form submission
    const submitJob = async () => {
      // Clear previous messages
      responseMessage.value = '';
      errorMessage.value = '';

      // Create FormData object
      const formData = new FormData();
      formData.append('url', url.value);
      formData.append('method', method.value);
      formData.append('hashFormat', hashFormat.value);

      if (wordlistFile.value) {
        formData.append('wordlist', wordlistFile.value);
      } else {
        // It's good practice to inform the user or handle this case as per requirements
        errorMessage.value = 'Please select a wordlist file.';
        return;
      }

      try {
        // Send POST request to the backend
        const response = await fetch('/api/submit_job', {
          method: 'POST',
          body: formData,
        });

        // Handle response
        if (response.ok) {
          const data = await response.json();
          responseMessage.value = `Job submitted successfully: ${JSON.stringify(data)}`;
        } else {
          const errorData = await response.json().catch(() => ({ message: 'Unknown error occurred' }));
          errorMessage.value = `Error submitting job: ${errorData.message || response.statusText}`;
        }
      } catch (error) {
        // Handle network errors or other issues
        console.error('Submission error:', error);
        errorMessage.value = `Network error or other issue: ${error.message}`;
      }
    };

    return {
      url,
      method,
      hashFormat,
      handleFileUpload,
      submitJob,
      responseMessage,
      errorMessage,
    };
  },
};
</script>

<style scoped>
.form-container {
  max-width: 600px;
  margin: 20px auto;
  padding: 20px;
  background-color: #f9f9f9;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

h1 {
  text-align: center;
  color: #333;
  margin-bottom: 20px;
}

.form-group {
  margin-bottom: 15px;
}

label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
  color: #555;
}

input[type="text"],
select,
input[type="file"] {
  width: 100%;
  padding: 10px;
  margin-top: 3px;
  border: 1px solid #ccc;
  border-radius: 4px;
  box-sizing: border-box; /* Ensures padding doesn't affect overall width */
  font-size: 16px;
}

input[type="file"] {
  padding: 3px; /* Specific adjustment for file input */
}

button {
  margin-top: 20px;
  padding: 12px 20px;
  background-color: #007bff; /* A more modern blue */
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
  transition: background-color 0.3s ease; /* Smooth transition for hover */
}

button:hover {
  background-color: #0056b3; /* Darker blue on hover */
}

.message {
  margin-top: 20px;
  padding: 10px;
  border-radius: 4px;
  font-size: 14px;
}

.success-message {
  background-color: #d4edda; /* Light green */
  color: #155724; /* Dark green text */
  border: 1px solid #c3e6cb;
}

.error-message {
  background-color: #f8d7da; /* Light red */
  color: #721c24; /* Dark red text */
  border: 1px solid #f5c6cb;
}
</style>
