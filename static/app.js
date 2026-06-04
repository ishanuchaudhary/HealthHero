// State management
let authToken = null;
let currentUser = null;
let userProfile = null;
let userSettings = null;
let ws = null;
let currentView = 'chat';
const SESSION_ID = localStorage.getItem("hh_session") || crypto.randomUUID();
localStorage.setItem("hh_session", SESSION_ID);

// DOM elements (will be initialized when DOM is ready)
let authModal, mainApp, chatEl, chatForm, userInput, loginForm, registerForm, logoutBtn;

// User preferences
const defaultSettings = {
  unitSystem: 'metric',
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  dateFormat: 'MM/DD/YYYY'
};

// Check if user is already logged in
function checkAuth() {
  const token = localStorage.getItem("hh_token");
  const user = localStorage.getItem("hh_user");
  if (token && user) {
    authToken = token;
    currentUser = JSON.parse(user);
    showMainApp();
    connectWebSocket();
    loadUserProfile();
    loadSettings();
    loadView('chat');
  } else {
    showAuthModal();
  }
}

// Authentication
async function login(username, password) {
  try {
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });
    
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || "Login failed");
    }
    
    const data = await res.json();
    authToken = data.access_token;
    currentUser = { id: data.user_id, username: data.username, email: data.email || '' };
    
    localStorage.setItem("hh_token", authToken);
    localStorage.setItem("hh_user", JSON.stringify(currentUser));
    
    showMainApp();
    connectWebSocket();
    loadUserProfile();
    loadSettings();
    loadView('chat');
    showToast("Welcome back, " + data.username + "!", "success");
  } catch (error) {
    showError("auth-error", error.message);
  }
}

async function register(username, email, password) {
  try {
    const res = await fetch("/api/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, email, password })
    });
    
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || "Registration failed");
    }
    
    const data = await res.json();
    authToken = data.access_token;
    currentUser = { id: data.user_id, username: data.username, email: email };
    
    localStorage.setItem("hh_token", authToken);
    localStorage.setItem("hh_user", JSON.stringify(currentUser));
    
    showMainApp();
    connectWebSocket();
    loadUserProfile();
    loadSettings();
    loadView('chat');
    showToast("Account created successfully! Welcome to HealthHero!", "success");
  } catch (error) {
    showError("register-error", error.message);
  }
}

function logout() {
  authToken = null;
  currentUser = null;
  userProfile = null;
  localStorage.removeItem("hh_token");
  localStorage.removeItem("hh_user");
  localStorage.removeItem("hh_profile");
  localStorage.removeItem("hh_settings");
  if (ws) {
    ws.close();
    ws = null;
  }
  showAuthModal();
  showToast("Logged out successfully", "info");
}

// UI Helpers
function showAuthModal() {
  if (authModal && mainApp) {
    authModal.style.display = "flex";
    mainApp.style.display = "none";
  }
}

function showMainApp() {
  if (authModal && mainApp) {
    authModal.style.display = "none";
    mainApp.style.display = "flex";
    updateUserDisplay();
  }
}

function updateUserDisplay() {
  if (!currentUser) return;
  
  const userNameEl = document.getElementById("user-name");
  const userEmailEl = document.getElementById("user-email");
  const userAvatarEl = document.getElementById("user-avatar");
  
  if (userNameEl) userNameEl.textContent = currentUser.username || "User";
  if (userEmailEl) userEmailEl.textContent = currentUser.email || userProfile?.email || "user@example.com";
  
  if (userAvatarEl) {
    const initials = (currentUser.username || "U").charAt(0).toUpperCase();
    userAvatarEl.textContent = initials;
    if (userProfile?.avatar) {
      userAvatarEl.style.backgroundImage = `url(${userProfile.avatar})`;
      userAvatarEl.style.backgroundSize = "cover";
      userAvatarEl.style.backgroundPosition = "center";
    }
  }
}

function showError(elementId, message) {
  const errorEl = document.getElementById(elementId);
  if (errorEl) {
    errorEl.textContent = message;
    errorEl.style.display = "block";
    setTimeout(() => {
      errorEl.style.display = "none";
    }, 5000);
  }
}

function showToast(message, type = "info") {
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
  toast.innerHTML = `<span class="toast-icon">${icons[type] || 'ℹ'}</span><span>${message}</span>`;
  document.getElementById("toast-container").appendChild(toast);
  
  setTimeout(() => {
    toast.classList.add("show");
  }, 10);
  
  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 400);
  }, 3000);
}

// WebSocket connection
let wsReconnectAttempts = 0;
const MAX_WS_RECONNECT_ATTEMPTS = 2;

function connectWebSocket() {
  if (!authToken) {
    console.log("No auth token, skipping WebSocket connection");
    return;
  }
  
  if (wsReconnectAttempts >= MAX_WS_RECONNECT_ATTEMPTS) {
    console.log("WebSocket reconnection limit reached, using HTTP only");
    return;
  }
  
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws?token=${encodeURIComponent(authToken)}`;
  
  console.log("Connecting WebSocket...");
  
  try {
    ws = new WebSocket(wsUrl);
  } catch (e) {
    console.error("Failed to create WebSocket:", e);
    ws = null;
    return;
  }
  
  let connectionTimeout;
  
  connectionTimeout = setTimeout(() => {
    if (ws && ws.readyState === WebSocket.CONNECTING) {
      console.log("WebSocket connection timeout");
      ws.close();
      ws = null;
    }
  }, 5000);
  
  ws.onopen = () => {
    clearTimeout(connectionTimeout);
    console.log("WebSocket connected");
    wsReconnectAttempts = 0;
    try {
      ws.send(JSON.stringify({ type: "auth", token: authToken }));
    } catch (e) {
      console.error("Error sending auth message:", e);
    }
  };
  
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === "auth_success") {
        console.log("WebSocket authentication successful");
      } else if (data.type === "auth_error") {
        console.error("WebSocket authentication failed:", data.message);
        ws.close();
        ws = null;
      }
    } catch (e) {
      // Not a JSON message, might be a chat response - handled elsewhere
    }
  };
  
  ws.onerror = (error) => {
    clearTimeout(connectionTimeout);
    console.error("WebSocket error:", error);
  };
  
  ws.onclose = (event) => {
    clearTimeout(connectionTimeout);
    console.log("WebSocket closed", event.code, event.reason);
    ws = null;
    
    if (event.code !== 1000 && event.code !== 1006 && authToken && wsReconnectAttempts < MAX_WS_RECONNECT_ATTEMPTS) {
      wsReconnectAttempts++;
      console.log(`Attempting WebSocket reconnect (${wsReconnectAttempts}/${MAX_WS_RECONNECT_ATTEMPTS})...`);
      setTimeout(() => {
        if (authToken && !ws) connectWebSocket();
      }, 3000);
    }
  };
}

// Chat functions
function addMsg(text, who) {
  if (!chatEl) {
    console.error("Chat element not found");
    return null;
  }
  const div = document.createElement("div");
  div.className = `msg ${who}`;
  div.textContent = text;
  chatEl.appendChild(div);
  chatEl.scrollTop = chatEl.scrollHeight;
  return div;
}

function addLoader() {
  if (!chatEl) {
    console.error("Chat element not found");
    return null;
  }
  const div = document.createElement("div");
  div.className = "msg bot forming";
  div.innerHTML = `<div class="loading"><div class="loading-dots"><span></span><span></span><span></span></div></div>`;
  chatEl.appendChild(div);
  chatEl.scrollTop = chatEl.scrollHeight;
  return div;
}

async function sendMessage(q) {
  if (!authToken) {
    showToast("Please login first", "error");
    return;
  }
  
  if (!userInput) {
    console.error("User input element not found");
    return;
  }
  
  addMsg(q, "user");
  userInput.value = "";
  
  if (ws && ws.readyState === WebSocket.OPEN) {
    console.log("Sending via WebSocket");
    sendViaWebSocket(q);
  } else {
    console.log("Sending via HTTP");
    sendViaHTTP(q);
  }
}

function sendViaWebSocket(q) {
  const div = addMsg("", "bot");
  if (!div) return;
  div.classList.add("forming");
  
  let messageBuffer = "";
  let handlerAdded = false;
  
  const messageHandler = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === "token") {
        messageBuffer += data.content;
        div.textContent = messageBuffer;
        chatEl.scrollTop = chatEl.scrollHeight;
      } else if (data.type === "end") {
        div.classList.remove("forming");
        if (handlerAdded) {
          ws.removeEventListener("message", messageHandler);
        }
      } else if (data.type === "error") {
        div.textContent = "Error: " + data.message;
        div.classList.remove("forming");
        if (handlerAdded) {
          ws.removeEventListener("message", messageHandler);
        }
      } else if (data.type === "auth_success" || data.type === "auth_error") {
        return;
      }
    } catch (e) {
      console.error("WebSocket message error:", e);
    }
  };
  
  ws.addEventListener("message", messageHandler);
  handlerAdded = true;
  
  ws.send(JSON.stringify({
    session_id: SESSION_ID,
    message: q
  }));
}

async function sendViaHTTP(q) {
  const loader = addLoader();
  if (!loader) {
    showToast("Error: Chat interface not ready", "error");
    return;
  }
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({ session_id: SESSION_ID, message: q })
    });
    
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
      throw new Error(errorData.detail || "Chat request failed");
    }
    
    const data = await res.json();
    loader.remove();
    addMsg(data.reply, "bot");
  } catch (error) {
    console.error("Chat error:", error);
    loader.remove();
    const errorMsg = error.message || "Sorry, I encountered an error. Please try again.";
    addMsg(`Error: ${errorMsg}`, "bot");
    showToast("Error sending message: " + errorMsg, "error");
  }
}

// Quick Actions
function handleQuickAction(action) {
  const quickActions = {
    water: () => {
      loadView('tracking');
      setTimeout(() => {
        document.getElementById('metric-type').value = 'water';
        document.getElementById('metric-value').focus();
        showToast("Enter your water intake in liters", "info");
      }, 100);
    },
    steps: () => {
      loadView('tracking');
      setTimeout(() => {
        document.getElementById('metric-type').value = 'steps';
        document.getElementById('metric-value').focus();
        showToast("Enter your step count", "info");
      }, 100);
    },
    sleep: () => {
      loadView('tracking');
      setTimeout(() => {
        document.getElementById('metric-type').value = 'sleep';
        document.getElementById('metric-value').focus();
        showToast("Enter your sleep hours", "info");
      }, 100);
    },
    exercise: () => {
      loadView('tracking');
      setTimeout(() => {
        document.getElementById('metric-type').value = 'exercise';
        document.getElementById('metric-value').focus();
        showToast("Enter your exercise minutes", "info");
      }, 100);
    }
  };
  
  if (quickActions[action]) {
    quickActions[action]();
  }
}

// View management
function loadView(viewName) {
  currentView = viewName;
  
  document.querySelectorAll(".nav-item").forEach(item => {
    item.classList.remove("active");
  });
  const navItem = document.querySelector(`[data-view="${viewName}"]`);
  if (navItem) navItem.classList.add("active");
  
  document.querySelectorAll(".view").forEach(view => {
    view.classList.remove("active");
  });
  const viewEl = document.getElementById(`${viewName}-view`);
  if (viewEl) viewEl.classList.add("active");
  
  if (viewName === "tracking") {
    loadMetrics();
  } else if (viewName === "reminders") {
    loadReminders();
  } else if (viewName === "goals") {
    loadGoals();
  } else if (viewName === "analytics") {
    loadAnalytics();
  } else if (viewName === "reports") {
    // Reports loaded on button click
  } else if (viewName === "settings") {
    loadSettings();
  }
}

// Health Tracking
async function loadMetrics() {
  const list = document.getElementById("metrics-list");
  if (!list) return;
  list.innerHTML = `<div class='loading'><div class='loading-dots'><span></span><span></span><span></span></div>Loading metrics…</div>`;
  
  try {
    const res = await fetch("/api/health/metrics?days=7", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({ detail: "Unknown error" }));
      throw new Error(errorData.detail || `HTTP ${res.status}`);
    }
    
    const data = await res.json();
    displayMetrics(data.metrics || []);
  } catch (error) {
    console.error("Error loading metrics:", error);
    list.innerHTML = `<p class='error'>Error loading metrics: ${error.message}</p>`;
    showToast("Error loading metrics: " + error.message, "error");
  }
}

function displayMetrics(metrics) {
  const list = document.getElementById("metrics-list");
  if (!list) return;
  
  if (metrics.length === 0) {
    list.innerHTML = `<div class='empty-state'><div class='empty-state-icon'>📊</div><strong>No entries yet</strong>Start tracking your health above.</div>`;
    return;
  }
  
  const settings = getUserSettings();
  list.innerHTML = metrics.map(m => {
    const date = formatDate(m.created_at, settings.dateFormat);
    return `
      <div class="metric-card">
        <div class="metric-header">
          <span class="metric-badge">${getMetricIcon(m.metric_type)} ${m.metric_type.replace('_',' ')}</span>
        </div>
        <div class="metric-value">${formatMetricValue(m.value, m.metric_type, settings.unitSystem)}</div>
        ${m.notes ? `<p class="metric-notes">${m.notes}</p>` : ''}
        <span class="metric-date">${date}</span>
      </div>
    `;
  }).join("");
}

function formatMetricValue(value, type, unitSystem) {
  if (type === 'weight') {
    return unitSystem === 'imperial' ? `${(value * 2.20462).toFixed(1)} lbs` : `${value} kg`;
  }
  return value;
}

function formatDate(dateString, format) {
  const date = new Date(dateString);
  const day = String(date.getDate()).padStart(2, '0');
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const year = date.getFullYear();
  
  if (format === 'DD/MM/YYYY') return `${day}/${month}/${year}`;
  if (format === 'YYYY-MM-DD') return `${year}-${month}-${day}`;
  return `${month}/${day}/${year}`;
}

function getMetricIcon(type) {
  const icons = {
    water: "💧",
    steps: "🚶",
    sleep: "😴",
    exercise: "🏃",
    weight: "⚖️",
    heart_rate: "❤️"
  };
  return icons[type] || "📊";
}

async function addMetric() {
  const type = document.getElementById("metric-type").value;
  const value = parseFloat(document.getElementById("metric-value").value);
  const notes = document.getElementById("metric-notes").value;
  
  if (!type || isNaN(value)) {
    showToast("Please fill in all required fields", "error");
    return;
  }
  
  try {
    const res = await fetch("/api/health/metrics", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({ metric_type: type, value, notes })
    });
    
    if (!res.ok) throw new Error("Failed to add metric");
    
    showToast("Metric added successfully!", "success");
    document.getElementById("metric-form").reset();
    loadMetrics();
  } catch (error) {
    showToast("Error adding metric", "error");
  }
}

// Reminders
async function loadReminders() {
  const list = document.getElementById("reminders-list");
  if (!list) return;
  list.innerHTML = `<div class='loading'><div class='loading-dots'><span></span><span></span><span></span></div>Loading reminders…</div>`;
  
  try {
    const res = await fetch("/api/reminders", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({ detail: "Unknown error" }));
      throw new Error(errorData.detail || `HTTP ${res.status}`);
    }
    
    const data = await res.json();
    displayReminders(data.reminders || []);
  } catch (error) {
    console.error("Error loading reminders:", error);
    list.innerHTML = `<p class='error'>Error loading reminders: ${error.message}</p>`;
    showToast("Error loading reminders: " + error.message, "error");
  }
}

function displayReminders(reminders) {
  const list = document.getElementById("reminders-list");
  if (!list) return;
  
  if (reminders.length === 0) {
    list.innerHTML = `<div class='empty-state'><div class='empty-state-icon'>⏰</div><strong>No reminders yet</strong>Create one above to stay on track.</div>`;
    return;
  }
  
  list.innerHTML = reminders.map(r => `
    <div class="reminder-card">
      <div class="reminder-icon-wrap">${getReminderIcon(r.reminder_type)}</div>
      <div class="reminder-body">
        <div class="reminder-header">
          <h3>${r.title}</h3>
          <span class="reminder-time-badge">🕐 ${r.scheduled_time}</span>
        </div>
        ${r.description ? `<p class="reminder-desc">${r.description}</p>` : ''}
      </div>
    </div>
  `).join("");
}

function getReminderIcon(type) {
  const icons = {
    water: "💧",
    medication: "💊",
    exercise: "🏃",
    meal: "🍎",
    sleep: "😴",
    other: "📝"
  };
  return icons[type] || "⏰";
}

async function addReminder() {
  const title = document.getElementById("reminder-title").value;
  const description = document.getElementById("reminder-description").value;
  const type = document.getElementById("reminder-type").value;
  const time = document.getElementById("reminder-time").value;
  
  if (!title || !type || !time) {
    showToast("Please fill in all required fields", "error");
    return;
  }
  
  try {
    const res = await fetch("/api/reminders", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({ title, description, reminder_type: type, scheduled_time: time })
    });
    
    if (!res.ok) throw new Error("Failed to create reminder");
    
    showToast("Reminder created successfully!", "success");
    document.getElementById("reminder-form").reset();
    loadReminders();
  } catch (error) {
    showToast("Error creating reminder", "error");
  }
}

// Analytics
async function loadAnalytics() {
  const content = document.getElementById("analytics-content");
  if (!content) return;
  content.innerHTML = `<div class='loading'><div class='loading-dots'><span></span><span></span><span></span></div>Loading analytics…</div>`;
  
  try {
    const res = await fetch("/api/analytics", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({ detail: "Unknown error" }));
      throw new Error(errorData.detail || `HTTP ${res.status}`);
    }
    
    const data = await res.json();
    displayAnalytics(data);
  } catch (error) {
    console.error("Error loading analytics:", error);
    content.innerHTML = `<p class='error'>Error loading analytics: ${error.message}</p>`;
    showToast("Error loading analytics: " + error.message, "error");
  }
}

// Keep old displayAnalytics for backward compatibility
async function displayAnalytics(data) {
  await displayAnalyticsWithCharts(data);
}

// Profile Management
async function loadUserProfile() {
  const stored = localStorage.getItem("hh_profile");
  if (stored) {
    userProfile = JSON.parse(stored);
    updateUserDisplay();
    return;
  }
  
  // Try to load from API if available
  try {
    const res = await fetch("/api/profile", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (res.ok) {
      userProfile = await res.json();
      localStorage.setItem("hh_profile", JSON.stringify(userProfile));
      updateUserDisplay();
    }
  } catch (error) {
    console.log("Profile API not available, using defaults");
  }
  
  // Set defaults
  if (!userProfile) {
    userProfile = {
      username: currentUser?.username || "",
      email: currentUser?.email || "",
      age: null,
      gender: "",
      height: null,
      weight: null,
      conditions: "",
      medications: "",
      allergies: ""
    };
  }
  
  updateUserDisplay();
}

function openProfileModal() {
  const modal = document.getElementById("profile-modal");
  if (!modal) return;
  
  // Populate form
  document.getElementById("profile-username").value = userProfile?.username || currentUser?.username || "";
  document.getElementById("profile-email").value = userProfile?.email || currentUser?.email || "";
  document.getElementById("profile-age").value = userProfile?.age || "";
  document.getElementById("profile-gender").value = userProfile?.gender || "";
  document.getElementById("profile-height").value = userProfile?.height || "";
  document.getElementById("profile-weight").value = userProfile?.weight || "";
  document.getElementById("profile-conditions").value = userProfile?.conditions || "";
  document.getElementById("profile-medications").value = userProfile?.medications || "";
  document.getElementById("profile-allergies").value = userProfile?.allergies || "";
  
  const avatarPreview = document.getElementById("avatar-preview");
  if (userProfile?.avatar) {
    avatarPreview.style.backgroundImage = `url(${userProfile.avatar})`;
    avatarPreview.style.backgroundSize = "cover";
    avatarPreview.textContent = "";
  } else {
    avatarPreview.style.backgroundImage = "";
    avatarPreview.textContent = (userProfile?.username || currentUser?.username || "U").charAt(0).toUpperCase();
  }
  
  modal.classList.add("active");
}

function closeProfileModal() {
  const modal = document.getElementById("profile-modal");
  if (modal) modal.classList.remove("active");
}

async function saveProfile() {
  const profileData = {
    username: document.getElementById("profile-username").value,
    email: document.getElementById("profile-email").value,
    age: parseInt(document.getElementById("profile-age").value) || null,
    gender: document.getElementById("profile-gender").value,
    height: parseFloat(document.getElementById("profile-height").value) || null,
    weight: parseFloat(document.getElementById("profile-weight").value) || null,
    conditions: document.getElementById("profile-conditions").value,
    medications: document.getElementById("profile-medications").value,
    allergies: document.getElementById("profile-allergies").value
  };
  
  userProfile = { ...userProfile, ...profileData };
  localStorage.setItem("hh_profile", JSON.stringify(userProfile));
  
  // Try to save to API if available
  try {
    await fetch("/api/profile", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify(profileData)
    });
  } catch (error) {
    console.log("Profile API not available, saved locally");
  }
  
  currentUser.username = profileData.username;
  currentUser.email = profileData.email;
  localStorage.setItem("hh_user", JSON.stringify(currentUser));
  
  updateUserDisplay();
  closeProfileModal();
  showToast("Profile updated successfully!", "success");
}

// Settings Management
function getUserSettings() {
  const stored = localStorage.getItem("hh_settings");
  if (stored) {
    return JSON.parse(stored);
  }
  return { ...defaultSettings };
}

function loadSettings() {
  const settings = getUserSettings();
  userSettings = settings;
  
  const unitSystemEl = document.getElementById("unit-system");
  const timezoneEl = document.getElementById("timezone");
  const dateFormatEl = document.getElementById("date-format");
  
  if (unitSystemEl) unitSystemEl.value = settings.unitSystem || 'metric';
  if (dateFormatEl) dateFormatEl.value = settings.dateFormat || 'MM/DD/YYYY';
  
  // Populate timezones
  if (timezoneEl) {
    const timezones = Intl.supportedValuesOf('timeZone');
    timezoneEl.innerHTML = timezones.map(tz => 
      `<option value="${tz}" ${tz === settings.timezone ? 'selected' : ''}>${tz}</option>`
    ).join("");
  }
}

function saveSettings() {
  const settings = {
    unitSystem: document.getElementById("unit-system").value,
    timezone: document.getElementById("timezone").value,
    dateFormat: document.getElementById("date-format").value
  };
  
  userSettings = settings;
  localStorage.setItem("hh_settings", JSON.stringify(settings));
  
  // Try to save to API if available
  try {
    fetch("/api/settings", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify(settings)
    });
  } catch (error) {
    console.log("Settings API not available, saved locally");
  }
  
  showToast("Settings saved successfully!", "success");
  loadMetrics(); // Reload to apply unit changes
}

// Help Modal
function openHelpModal() {
  const modal = document.getElementById("help-modal");
  if (modal) modal.classList.add("active");
}

function closeHelpModal() {
  const modal = document.getElementById("help-modal");
  if (modal) modal.classList.remove("active");
}

function toggleFaq(element) {
  const faqItem = element.closest(".faq-item");
  const isActive = faqItem.classList.contains("active");
  
  document.querySelectorAll(".faq-item").forEach(item => {
    item.classList.remove("active");
  });
  
  if (!isActive) {
    faqItem.classList.add("active");
  }
}

// Avatar upload
function handleAvatarUpload(event) {
  const file = event.target.files[0];
  if (!file) return;
  
  if (file.size > 2 * 1024 * 1024) {
    showToast("Image size must be less than 2MB", "error");
    return;
  }
  
  const reader = new FileReader();
  reader.onload = (e) => {
    const avatarPreview = document.getElementById("avatar-preview");
    avatarPreview.style.backgroundImage = `url(${e.target.result})`;
    avatarPreview.style.backgroundSize = "cover";
    avatarPreview.textContent = "";
    
    if (!userProfile) userProfile = {};
    userProfile.avatar = e.target.result;
    localStorage.setItem("hh_profile", JSON.stringify(userProfile));
    updateUserDisplay();
  };
  reader.readAsDataURL(file);
}

// Goals Management
let goalCharts = {};

async function loadGoals() {
  const list = document.getElementById("goals-list");
  if (!list) return;
  list.innerHTML = `<div class='loading'><div class='loading-dots'><span></span><span></span><span></span></div>Loading goals…</div>`;
  
  try {
    const res = await fetch("/api/goals?active_only=true", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({ detail: "Unknown error" }));
      throw new Error(errorData.detail || `HTTP ${res.status}`);
    }
    
    const data = await res.json();
    displayGoals(data.goals || []);
  } catch (error) {
    console.error("Error loading goals:", error);
    list.innerHTML = `<p class='error'>Error loading goals: ${error.message}</p>`;
    showToast("Error loading goals: " + error.message, "error");
  }
}

function displayGoals(goals) {
  const list = document.getElementById("goals-list");
  if (!list) return;
  
  if (goals.length === 0) {
    list.innerHTML = `<div class='empty-state'><div class='empty-state-icon'>🎯</div><strong>No goals yet</strong>Create your first goal to start tracking progress.</div>`;
    return;
  }
  
  list.innerHTML = goals.map(goal => {
    const progress = goal.progress_percent || 0;
    const isCompleted = goal.is_completed || false;
    return `
      <div class="goal-card ${isCompleted ? 'completed' : ''}">
        <div class="goal-header">
          <div class="goal-title-area">
            <h3>${goal.title}</h3>
            <span class="goal-type-badge">${getGoalTypeIcon(goal.goal_type)} ${goal.goal_type.replace('_',' ')}</span>
          </div>
          <div class="goal-actions">
            <button class="btn-secondary" style="padding:6px 12px;font-size:12px;" onclick="addGoalProgress(${goal.id})" title="Add Progress">+ Progress</button>
            <button class="btn-danger" onclick="deleteGoal(${goal.id})" title="Delete">✕</button>
          </div>
        </div>
        ${goal.description ? `<p class="goal-description">${goal.description}</p>` : ''}
        <div class="goal-progress">
          <div class="progress-label">
            <span>${(goal.current_value || 0).toFixed(1)} / ${goal.target_value} ${goal.unit || ''}</span>
            <span class="progress-pct">${progress.toFixed(1)}%</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" style="width: ${Math.min(100, progress)}%"></div>
          </div>
        </div>
        ${isCompleted ? '<span class="goal-completed-badge">✓ Completed</span>' : ''}
        <div class="goal-dates">
          <span>Start: ${formatDate(goal.start_date, getUserSettings().dateFormat)}</span>
          ${goal.end_date ? `<span>End: ${formatDate(goal.end_date, getUserSettings().dateFormat)}</span>` : ''}
        </div>
      </div>
    `;
  }).join("");
}

function getGoalTypeIcon(type) {
  const icons = {
    water: "💧",
    steps: "🚶",
    sleep: "😴",
    exercise: "🏃",
    weight: "⚖️",
    heart_rate: "❤️",
    other: "📝"
  };
  return icons[type] || "🎯";
}

function openGoalModal() {
  const modal = document.getElementById("goal-modal");
  if (!modal) return;
  document.getElementById("goal-modal-title").textContent = "New Goal";
  document.getElementById("goal-form").reset();
  document.getElementById("goal-start-date").value = new Date().toISOString().split('T')[0];
  modal.classList.add("active");
}

function closeGoalModal() {
  const modal = document.getElementById("goal-modal");
  if (modal) modal.classList.remove("active");
}

async function saveGoal() {
  const goalData = {
    goal_type: document.getElementById("goal-type").value,
    title: document.getElementById("goal-title").value,
    description: document.getElementById("goal-description").value,
    target_value: parseFloat(document.getElementById("goal-target").value),
    unit: document.getElementById("goal-unit").value,
    start_date: document.getElementById("goal-start-date").value,
    end_date: document.getElementById("goal-end-date").value || null
  };
  
  try {
    const res = await fetch("/api/goals", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify(goalData)
    });
    
    if (!res.ok) throw new Error("Failed to create goal");
    
    showToast("Goal created successfully!", "success");
    closeGoalModal();
    loadGoals();
  } catch (error) {
    showToast("Error creating goal", "error");
  }
}

async function deleteGoal(goalId) {
  if (!confirm("Are you sure you want to delete this goal?")) return;
  
  try {
    const res = await fetch(`/api/goals/${goalId}`, {
      method: "DELETE",
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    
    if (!res.ok) throw new Error("Failed to delete goal");
    
    showToast("Goal deleted successfully!", "success");
    loadGoals();
  } catch (error) {
    showToast("Error deleting goal", "error");
  }
}

async function addGoalProgress(goalId) {
  const value = prompt("Enter progress value:");
  if (!value || isNaN(value)) return;
  
  try {
    const res = await fetch("/api/goals/progress", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({
        goal_id: goalId,
        date: new Date().toISOString().split('T')[0],
        value: parseFloat(value)
      })
    });
    
    if (!res.ok) throw new Error("Failed to add progress");
    
    showToast("Progress added successfully!", "success");
    loadGoals();
  } catch (error) {
    showToast("Error adding progress", "error");
  }
}

// Charts & Visualizations
function createMetricChart(containerId, metricType, data) {
  const container = document.getElementById(containerId);
  if (!container) return null;
  
  // Clear existing chart
  const canvas = document.createElement('canvas');
  container.innerHTML = '';
  container.appendChild(canvas);
  
  const labels = data.map(d => formatDate(d.created_at, getUserSettings().dateFormat));
  const values = data.map(d => parseFloat(d.value));
  
  return new Chart(canvas, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: metricType,
        data: values,
        borderColor: '#3d6b52',
        backgroundColor: 'rgba(61,107,82, 0.08)',
        tension: 0.4,
        fill: true,
        pointBackgroundColor: '#3d6b52',
        pointRadius: 3,
        pointHoverRadius: 5
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { color: '#9aaa9d', font: { size: 11 } },
          grid: { color: '#e4dfd7' }
        },
        x: {
          ticks: { color: '#9aaa9d', font: { size: 11 }, maxRotation: 30 },
          grid: { color: '#e4dfd7' }
        }
      }
    }
  });
}

// Enhanced Analytics with Charts
async function loadAnalytics() {
  const content = document.getElementById("analytics-content");
  if (!content) return;
  content.innerHTML = `<div class='loading'><div class='loading-dots'><span></span><span></span><span></span></div>Loading analytics…</div>`;
  
  try {
    const res = await fetch("/api/analytics", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({ detail: "Unknown error" }));
      throw new Error(errorData.detail || `HTTP ${res.status}`);
    }
    
    const data = await res.json();
    await displayAnalyticsWithCharts(data);
  } catch (error) {
    console.error("Error loading analytics:", error);
    content.innerHTML = `<p class='error'>Error loading analytics: ${error.message}</p>`;
    showToast("Error loading analytics: " + error.message, "error");
  }
}

async function displayAnalyticsWithCharts(data) {
  const content = document.getElementById("analytics-content");
  if (!content) return;
  
  if (!data.metrics || Object.keys(data.metrics).length === 0) {
    content.innerHTML = `<div class='empty-state'><div class='empty-state-icon'>📈</div><strong>No data yet</strong>Start logging health metrics to see your analytics.</div>`;
    return;
  }
  
  let html = '<div class="analytics-grid">';
  
  // Metrics cards with charts
  for (const [type, stats] of Object.entries(data.metrics)) {
    html += `
      <div class="analytics-card">
        <div class="analytics-header">
          <div class="analytics-icon-wrap">${getMetricIcon(type)}</div>
          <h3>${type.charAt(0).toUpperCase() + type.slice(1).replace('_', ' ')}</h3>
        </div>
        <div class="analytics-stats">
          <div class="stat">
            <span class="stat-label">Average</span>
            <span class="stat-value">${stats.average.toFixed(1)}</span>
          </div>
          <div class="stat">
            <span class="stat-label">Latest</span>
            <span class="stat-value">${stats.latest.toFixed(1)}</span>
          </div>
          <div class="stat">
            <span class="stat-label">Range</span>
            <span class="stat-value">${stats.min.toFixed(1)}–${stats.max.toFixed(1)}</span>
          </div>
          <div class="stat">
            <span class="stat-label">Entries</span>
            <span class="stat-value">${stats.count}</span>
          </div>
        </div>
        <div class="chart-container" style="height: 200px; margin-top: 20px;">
          <canvas id="chart-${type}"></canvas>
        </div>
      </div>
    `;
  }
  
  html += `
    <div class="analytics-card summary-card">
      <h3>Summary</h3>
      <div class="summary-stats">
        <div class="summary-item">
          <span class="summary-label">Active Reminders</span>
          <span class="summary-value">${data.active_reminders || 0}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">Total Reminders</span>
          <span class="summary-value">${data.reminder_count || 0}</span>
        </div>
      </div>
    </div>
  `;
  
  html += '</div>';
  content.innerHTML = html;
  
  // Load charts for each metric
  for (const type of Object.keys(data.metrics)) {
    try {
      const metricsRes = await fetch(`/api/health/metrics?metric_type=${type}&days=30`, {
        headers: { "Authorization": `Bearer ${authToken}` }
      });
      if (metricsRes.ok) {
        const metricsData = await metricsRes.json();
        if (metricsData.metrics && metricsData.metrics.length > 0) {
          createMetricChart(`chart-${type}`, type, metricsData.metrics.reverse());
        }
      }
    } catch (error) {
      console.error(`Error loading chart for ${type}:`, error);
    }
  }
}

// Health Reports
async function loadReport(period) {
  const content = document.getElementById("reports-content");
  if (!content) return;
  content.innerHTML = `<div class='loading'><div class='loading-dots'><span></span><span></span><span></span></div>Generating report…</div>`;
  
  try {
    const res = await fetch(`/api/reports?period=${period}`, {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({ detail: "Unknown error" }));
      throw new Error(errorData.detail || `HTTP ${res.status}`);
    }
    
    const data = await res.json();
    displayReport(data, period);
  } catch (error) {
    console.error("Error loading report:", error);
    content.innerHTML = `<p class='error'>Error generating report: ${error.message}</p>`;
    showToast("Error generating report: " + error.message, "error");
  }
}

function displayReport(data, period) {
  const content = document.getElementById("reports-content");
  if (!content) return;
  
  let html = `
    <div class="report-header">
      <h3>${period === 'week' ? 'Weekly' : 'Monthly'} Health Report</h3>
      <p class="report-date">Generated: ${formatDate(data.generated_at, getUserSettings().dateFormat)}</p>
    </div>
    
    <div class="report-summary">
      <div class="summary-card">
        <h4>Overview</h4>
        <div class="summary-stats">
          <div class="summary-item">
            <span class="summary-label">Metrics Logged</span>
            <span class="summary-value">${data.metrics_count}</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">Active Reminders</span>
            <span class="summary-value">${data.reminders_count}</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">Active Goals</span>
            <span class="summary-value">${data.active_goals}</span>
          </div>
        </div>
      </div>
    </div>
  `;
  
  if (data.trends && Object.keys(data.trends).length > 0) {
    html += '<div class="report-section"><h4>Trends</h4>';
    for (const [type, trend] of Object.entries(data.trends)) {
      const trendIcon = trend.trend === 'improving' ? '📈' : trend.trend === 'declining' ? '📉' : '➡️';
      html += `
        <div class="trend-item">
          <span class="trend-icon">${trendIcon}</span>
          <div>
            <strong>${type.charAt(0).toUpperCase() + type.slice(1).replace('_', ' ')}</strong>
            <span class="trend-change">${trend.change_percent > 0 ? '+' : ''}${trend.change_percent}%</span>
            <span class="trend-label">${trend.trend}</span>
          </div>
        </div>
      `;
    }
    html += '</div>';
  }
  
  if (data.goal_summaries && data.goal_summaries.length > 0) {
    html += '<div class="report-section"><h4>Goal Progress</h4>';
    data.goal_summaries.forEach(goal => {
      html += `
        <div class="goal-progress-item">
          <div class="goal-progress-header">
            <strong>${goal.title}</strong>
            <span>${goal.progress_percent.toFixed(1)}%</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" style="width: ${goal.progress_percent}%"></div>
          </div>
          ${goal.is_completed ? '<span class="goal-completed">✓ Completed</span>' : ''}
        </div>
      `;
    });
    html += '</div>';
  }
  
  content.innerHTML = html;
}

// Initialize when DOM is ready
function init() {
  // Get DOM elements
  authModal = document.getElementById("auth-modal");
  mainApp = document.getElementById("main-app");
  chatEl = document.getElementById("chat");
  chatForm = document.getElementById("chat-form");
  userInput = document.getElementById("user-input");
  loginForm = document.getElementById("login-form");
  registerForm = document.getElementById("register-form");
  logoutBtn = document.getElementById("logout-btn");
  
  if (!authModal || !mainApp) {
    console.error("Required DOM elements not found!");
    return;
  }
  
  // Set up event listeners
  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const username = document.getElementById("login-username").value;
    const password = document.getElementById("login-password").value;
    await login(username, password);
  });

  registerForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const username = document.getElementById("register-username").value;
    const email = document.getElementById("register-email").value;
    const password = document.getElementById("register-password").value;
    await register(username, email, password);
  });

  // Tab switching
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      
      const tab = btn.dataset.tab;
      loginForm.style.display = tab === "login" ? "block" : "none";
      registerForm.style.display = tab === "register" ? "block" : "none";
    });
  });

  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = userInput.value.trim();
    if (!q) return;
    await sendMessage(q);
  });

  // Navigation
  document.querySelectorAll(".nav-item").forEach(item => {
    item.addEventListener("click", () => {
      const view = item.dataset.view;
      if (view) loadView(view);
    });
  });

  logoutBtn.addEventListener("click", logout);

  // Profile button
  const profileBtn = document.getElementById("user-profile-btn");
  if (profileBtn) {
    profileBtn.addEventListener("click", openProfileModal);
  }

  // Help button
  const helpBtn = document.getElementById("help-btn");
  if (helpBtn) {
    helpBtn.addEventListener("click", openHelpModal);
  }

  // Profile form
  const profileForm = document.getElementById("profile-form");
  if (profileForm) {
    profileForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      await saveProfile();
    });
  }

  // Avatar upload
  const avatarInput = document.getElementById("avatar-input");
  if (avatarInput) {
    avatarInput.addEventListener("change", handleAvatarUpload);
  }

  // Quick actions
  document.querySelectorAll(".quick-action-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const action = btn.dataset.quick;
      if (action) handleQuickAction(action);
    });
  });

  // Health tracking form
  const metricForm = document.getElementById("metric-form");
  if (metricForm) {
    metricForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      await addMetric();
    });
  }

  // Reminder form
  const reminderForm = document.getElementById("reminder-form");
  if (reminderForm) {
    reminderForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      await addReminder();
    });
  }

  // Goal form
  const goalForm = document.getElementById("goal-form");
  if (goalForm) {
    goalForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      await saveGoal();
    });
  }
  
  // Keyboard shortcuts
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeProfileModal();
      closeHelpModal();
    }
    if (e.key === "/" && e.target.tagName !== "INPUT" && e.target.tagName !== "TEXTAREA") {
      e.preventDefault();
      if (userInput) userInput.focus();
    }
  });
  
  // Check authentication
  checkAuth();
}

// Wait for DOM to be ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
