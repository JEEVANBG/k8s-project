"use strict";

const form = document.getElementById("profile-form");
const errorMessage = document.getElementById("error");
const submitButton = document.getElementById("submit");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorMessage.hidden = true;
  submitButton.disabled = true;
  submitButton.textContent = "Saving profile…";

  try {
    const response = await fetch("/api/profiles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: document.getElementById("name").value,
        bio: document.getElementById("bio").value,
        consent: document.getElementById("consent").checked
      })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Profile could not be saved.");
    window.location.assign("/upload/?profile=" + encodeURIComponent(result.id));
  } catch (error) {
    errorMessage.textContent = error.message || "The backend could not be reached. Please try again.";
    errorMessage.hidden = false;
    submitButton.disabled = false;
    submitButton.innerHTML = 'Continue to document upload <span>→</span>';
  }
});
