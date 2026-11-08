"use strict";

const profileId = new URLSearchParams(window.location.search).get("profile");
const form = document.getElementById("upload-form");
const errorMessage = document.getElementById("error");
const successMessage = document.getElementById("success");
const submitButton = document.getElementById("submit");
const fileInput = document.getElementById("document");
const fileName = document.getElementById("file-name");

fileInput.addEventListener("change", () => {
  fileName.textContent = fileInput.files.length ? fileInput.files[0].name : "Choose a file";
});

async function loadProfile() {
  if (!profileId) throw new Error("Missing profile ID. Start again from the profile page.");
  const response = await fetch("/api/profiles/" + encodeURIComponent(profileId));
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Profile could not be loaded.");
  document.getElementById("profile-name").textContent = result.name;
  if (result.status === "complete") {
    form.hidden = true;
    successMessage.textContent = "This profile already has a document upload.";
    successMessage.hidden = false;
  }
}

loadProfile().catch((error) => {
  errorMessage.textContent = error.message;
  errorMessage.hidden = false;
  form.hidden = true;
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorMessage.hidden = true;
  submitButton.disabled = true;
  submitButton.textContent = "Uploading to S3…";

  try {
    if (!profileId) throw new Error("Missing profile ID. Start again from the profile page.");
    const payload = new FormData();
    payload.append("document", fileInput.files[0]);
    payload.append("consent", document.getElementById("consent").checked ? "yes" : "no");
    const response = await fetch("/api/profiles/" + encodeURIComponent(profileId) + "/document", {
      method: "POST",
      body: payload
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Document upload failed.");
    form.hidden = true;
    successMessage.textContent = "Upload complete. Your document is stored in S3 and the profile table has been updated.";
    successMessage.hidden = false;
  } catch (error) {
    errorMessage.textContent = error.message || "The backend could not be reached. Please try again.";
    errorMessage.hidden = false;
    submitButton.disabled = false;
    submitButton.innerHTML = 'Upload document securely <span>→</span>';
  }
});
