const API_BASE_URL = window.location.hostname === 'localhost' 
    ? 'http://localhost:3000' 
    : '/api';

function showMessage(text, type = 'success') {
    const messageDiv = document.getElementById('message');
    messageDiv.innerHTML = `<div class="${type}">${text}</div>`;
    setTimeout(() => messageDiv.innerHTML = '', 5000);
}

function showError(text) {
    showMessage(text, 'error');
}

async function loadUsers() {
    try {
        const response = await fetch(`${API_BASE_URL}/users`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const users = await response.json();
        
        const usersList = document.getElementById('usersList');
        
        if (users.length === 0) {
            usersList.innerHTML = '<p>No users found. Add some users above!</p>';
            return;
        }
        
        usersList.innerHTML = users.map(user => `
            <div class="user-item">
                <strong>${escapeHtml(user.name)}</strong> (${escapeHtml(user.email)})
                <br>
                <small>ID: ${user.id} | Created: ${new Date(user.created_at).toLocaleString()}</small>
                ${user.message ? `<br><em>"${escapeHtml(user.message)}"</em>` : ''}
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading users:', error);
        showError(`Failed to load users: ${error.message}`);
        document.getElementById('usersList').innerHTML = '<p>Failed to load users. Please try again.</p>';
    }
}

async function addUser(userData) {
    try {
        const response = await fetch(`${API_BASE_URL}/users`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(userData)
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        showMessage('User added successfully!');
        document.getElementById('userForm').reset();
        loadUsers();
        return result;
    } catch (error) {
        console.error('Error adding user:', error);
        showError(`Failed to add user: ${error.message}`);
        throw error;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

document.getElementById('userForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const userData = {
        name: formData.get('name').trim(),
        email: formData.get('email').trim(),
        message: formData.get('message').trim()
    };
    
    if (!userData.name || !userData.email) {
        showError('Name and email are required!');
        return;
    }
    
    try {
        await addUser(userData);
    } catch (error) {
        console.error('Form submission error:', error);
    }
});

window.addEventListener('DOMContentLoaded', () => {
    loadUsers();
});