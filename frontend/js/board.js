requireAuth();

const params = new URLSearchParams(window.location.search);
const projectId = params.get("project");

const errorMessage = document.getElementById("error-message");
const newTaskForm = document.getElementById("new-task-form");
const taskAssigneeSelect = document.getElementById("task-assignee");
const membersList = document.getElementById("members-list");
const addMemberForm = document.getElementById("add-member-form");
const projectNameLabel = document.getElementById("project-name");
const usernameLabel = document.getElementById("username-label");
const logoutLink = document.getElementById("logout-link");

const modalOverlay = document.getElementById("task-modal-overlay");
const closeModalBtn = document.getElementById("close-modal");
const modalTaskTitle = document.getElementById("modal-task-title");
const modalTaskDescription = document.getElementById("modal-task-description");
const modalAssigneeSelect = document.getElementById("modal-assignee");
const statusActions = document.getElementById("status-actions");
const activityList = document.getElementById("activity-list");
const commentList = document.getElementById("comment-list");
const commentForm = document.getElementById("comment-form");

let currentTask = null;
let currentProject = null;
let currentMembers = [];

const currentUser = getCurrentUser();
if (currentUser) usernameLabel.textContent = currentUser.username;

logoutLink.addEventListener("click", (e) => {
  e.preventDefault();
  clearSession();
  window.location.href = "/index.html";
});

if (!projectId) {
  window.location.href = "/projects.html";
}

async function loadProject() {
  try {
    currentProject = await apiFetch(`/projects/${projectId}`);
    projectNameLabel.textContent = currentProject.name;
    addMemberForm.style.display = isOwner() ? "flex" : "none";
  } catch (err) {
    errorMessage.textContent = err.message;
  }
}

function isOwner() {
  return currentProject && currentUser && currentProject.owner_id === currentUser.id;
}

async function loadMembers() {
  try {
    const data = await apiFetch(`/projects/${projectId}/members`);
    currentMembers = data.members;
    renderMembers(currentMembers);
    populateAssigneeSelects();
  } catch (err) {
    errorMessage.textContent = err.message;
  }
}

function populateAssigneeSelects() {
  const optionsHtml =
    '<option value="">Nessun assegnatario</option>' +
    currentMembers
      .map((m) => `<option value="${m.user_id}">${escapeHtml(m.username || `utente #${m.user_id}`)}</option>`)
      .join("");
  taskAssigneeSelect.innerHTML = optionsHtml;
  modalAssigneeSelect.innerHTML = optionsHtml;
}

function memberLabel(userId) {
  if (!userId) return "nessuno";
  const member = currentMembers.find((m) => m.user_id === Number(userId));
  return member ? member.username || `utente #${userId}` : `utente #${userId}`;
}

function renderMembers(members) {
  membersList.innerHTML = "";
  for (const member of members) {
    const li = document.createElement("li");
    const label = member.username ? `@${member.username}` : `utente #${member.user_id}`;
    const roleTag = member.role === "owner" ? " (proprietario)" : "";
    li.innerHTML = `<span>${escapeHtml(label + roleTag)}</span>`;
    if (member.role !== "owner" && isOwner()) {
      const removeBtn = document.createElement("button");
      removeBtn.textContent = "Rimuovi";
      removeBtn.className = "secondary";
      removeBtn.addEventListener("click", () => removeMember(member.user_id));
      li.appendChild(removeBtn);
    }
    membersList.appendChild(li);
  }
}

async function removeMember(memberUserId) {
  errorMessage.textContent = "";
  try {
    await apiFetch(`/projects/${projectId}/members/${memberUserId}`, { method: "DELETE" });
    loadMembers();
  } catch (err) {
    errorMessage.textContent = err.message;
  }
}

addMemberForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorMessage.textContent = "";
  const username = document.getElementById("member-username").value;
  try {
    await apiFetch(`/projects/${projectId}/members`, {
      method: "POST",
      body: JSON.stringify({ username }),
    });
    addMemberForm.reset();
    loadMembers();
  } catch (err) {
    errorMessage.textContent = err.message;
  }
});

async function loadTasks() {
  try {
    const data = await apiFetch(`/projects/${projectId}/tasks`);
    renderBoard(data.tasks);
  } catch (err) {
    errorMessage.textContent = err.message;
  }
}

function renderBoard(tasks) {
  const columns = { todo: [], in_progress: [], done: [] };
  for (const task of tasks) {
    (columns[task.status] || columns.todo).push(task);
  }
  for (const status of Object.keys(columns)) {
    const container = document.getElementById(`column-${status}`);
    container.innerHTML = "";
    for (const task of columns[status]) {
      const card = document.createElement("div");
      card.className = "task-card";
      card.innerHTML = `<div>${escapeHtml(task.title)}</div>`;
      if (task.assignee_id) {
        card.innerHTML += `<div class="assignee">Assegnato a ${escapeHtml(memberLabel(task.assignee_id))}</div>`;
      }
      card.addEventListener("click", () => openTaskModal(task));
      container.appendChild(card);
    }
  }
}

newTaskForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorMessage.textContent = "";
  const title = document.getElementById("task-title").value;
  const assigneeId = taskAssigneeSelect.value;
  try {
    await apiFetch(`/projects/${projectId}/tasks`, {
      method: "POST",
      body: JSON.stringify({ title, assignee_id: assigneeId ? Number(assigneeId) : null }),
    });
    newTaskForm.reset();
    loadTasks();
  } catch (err) {
    errorMessage.textContent = err.message;
  }
});

async function openTaskModal(task) {
  currentTask = task;
  modalTaskTitle.textContent = task.title;
  modalTaskDescription.textContent = task.description || "";
  highlightActiveStatus(task.status);
  modalAssigneeSelect.value = task.assignee_id ? String(task.assignee_id) : "";
  modalOverlay.classList.add("open");
  await Promise.all([loadActivityForTask(task), loadComments(task.id)]);
}

modalAssigneeSelect.addEventListener("change", async () => {
  if (!currentTask) return;
  const value = modalAssigneeSelect.value;
  try {
    const updated = await apiFetch(`/tasks/${currentTask.id}`, {
      method: "PATCH",
      body: JSON.stringify({ assignee_id: value ? Number(value) : null }),
    });
    currentTask = updated;
    await loadActivityForTask(currentTask);
    loadTasks();
  } catch (err) {
    errorMessage.textContent = err.message;
  }
});

function highlightActiveStatus(status) {
  for (const btn of statusActions.querySelectorAll("button")) {
    btn.classList.toggle("active", btn.dataset.status === status);
  }
}

statusActions.addEventListener("click", async (e) => {
  const status = e.target.dataset.status;
  if (!status || !currentTask) return;
  try {
    const updated = await apiFetch(`/tasks/${currentTask.id}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
    currentTask = updated;
    highlightActiveStatus(status);
    await loadActivityForTask(currentTask);
    loadTasks();
  } catch (err) {
    errorMessage.textContent = err.message;
  }
});

async function loadActivityForTask(task) {
  try {
    const data = await apiFetch(`/activities?project_id=${projectId}`);
    const relevant = data.activities.filter((a) => a.task_id === task.id);
    activityList.innerHTML = relevant.length
      ? relevant.map(renderActivityItem).join("")
      : "<p>Nessuna attività registrata.</p>";
  } catch (err) {
    activityList.innerHTML = `<p class="error-message">${escapeHtml(err.message)}</p>`;
  }
}

function renderActivityItem(activity) {
  const description = describeActivity(activity);
  return `<div class="activity-item">${description}<div class="meta">${formatTimestamp(activity.timestamp)}</div></div>`;
}

function describeActivity(activity) {
  if (activity.type === "task_created") return "Task creato";
  if (activity.type === "status_changed") {
    const { from, to } = activity.payload || {};
    return `Stato cambiato da <strong>${from}</strong> a <strong>${to}</strong>`;
  }
  if (activity.type === "assignee_changed") {
    const { from, to } = activity.payload || {};
    return `Assegnatario cambiato da <strong>${escapeHtml(memberLabel(from))}</strong> a <strong>${escapeHtml(memberLabel(to))}</strong>`;
  }
  return escapeHtml(activity.type);
}

async function loadComments(taskId) {
  try {
    const data = await apiFetch(`/comments/${taskId}`);
    commentList.innerHTML = data.comments.length
      ? data.comments.map(renderComment).join("")
      : "<p>Nessun commento.</p>";
  } catch (err) {
    commentList.innerHTML = `<p class="error-message">${escapeHtml(err.message)}</p>`;
  }
}

function renderComment(comment) {
  return `<div class="comment-item">${escapeHtml(comment.body)}<div class="meta">utente #${comment.author_id} · ${formatTimestamp(comment.timestamp)}</div></div>`;
}

commentForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!currentTask) return;
  const body = document.getElementById("comment-body").value;
  try {
    await apiFetch(`/comments/${currentTask.id}`, {
      method: "POST",
      body: JSON.stringify({ body }),
    });
    document.getElementById("comment-body").value = "";
    await loadComments(currentTask.id);
  } catch (err) {
    errorMessage.textContent = err.message;
  }
});

closeModalBtn.addEventListener("click", () => {
  modalOverlay.classList.remove("open");
  currentTask = null;
});

modalOverlay.addEventListener("click", (e) => {
  if (e.target === modalOverlay) {
    modalOverlay.classList.remove("open");
    currentTask = null;
  }
});

function formatTimestamp(ts) {
  if (!ts) return "";
  return new Date(ts).toLocaleString("it-IT");
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

async function init() {
  await loadProject();
  await loadMembers();
  loadTasks();
}

init();
