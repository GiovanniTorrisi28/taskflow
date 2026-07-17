requireAuth();

const projectList = document.getElementById("project-list");
const errorMessage = document.getElementById("error-message");
const newProjectForm = document.getElementById("new-project-form");
const usernameLabel = document.getElementById("username-label");
const logoutLink = document.getElementById("logout-link");

const currentUser = getCurrentUser();
if (currentUser) {
  usernameLabel.textContent = currentUser.username;
}

logoutLink.addEventListener("click", (e) => {
  e.preventDefault();
  clearSession();
  window.location.href = "/index.html";
});

async function loadProjects() {
  try {
    const data = await apiFetch("/projects");
    renderProjects(data.projects);
  } catch (err) {
    errorMessage.textContent = err.message;
  }
}

function renderProjects(projects) {
  projectList.innerHTML = "";
  if (projects.length === 0) {
    projectList.innerHTML = "<p>Non hai ancora nessun progetto. Creane uno qui sotto.</p>";
    return;
  }
  for (const project of projects) {
    const card = document.createElement("div");
    card.className = "project-card";
    card.innerHTML = `<h3>${escapeHtml(project.name)}</h3><p>${escapeHtml(project.description || "")}</p>`;
    card.addEventListener("click", () => {
      window.location.href = `/board.html?project=${project.id}`;
    });
    projectList.appendChild(card);
  }
}

newProjectForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorMessage.textContent = "";
  const name = document.getElementById("project-name").value;
  const description = document.getElementById("project-description").value;

  try {
    await apiFetch("/projects", {
      method: "POST",
      body: JSON.stringify({ name, description }),
    });
    newProjectForm.reset();
    loadProjects();
  } catch (err) {
    errorMessage.textContent = err.message;
  }
});

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

loadProjects();
