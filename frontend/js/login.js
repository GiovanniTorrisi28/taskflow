const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const toggleLink = document.getElementById("toggle-link");
const formTitle = document.getElementById("form-title");
const errorMessage = document.getElementById("error-message");

if (getToken()) {
  window.location.href = "/projects.html";
}

let showingLogin = true;

toggleLink.addEventListener("click", (e) => {
  e.preventDefault();
  showingLogin = !showingLogin;
  loginForm.style.display = showingLogin ? "block" : "none";
  registerForm.style.display = showingLogin ? "none" : "block";
  formTitle.textContent = showingLogin ? "Accedi a TaskFlow" : "Crea un account";
  toggleLink.textContent = showingLogin ? "Non hai un account? Registrati" : "Hai già un account? Accedi";
  errorMessage.textContent = "";
});

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorMessage.textContent = "";
  const username = document.getElementById("login-username").value;
  const password = document.getElementById("login-password").value;

  try {
    const data = await apiFetch("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    setSession(data.token, data.user);
    window.location.href = "/projects.html";
  } catch (err) {
    errorMessage.textContent = err.message;
  }
});

registerForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorMessage.textContent = "";
  const username = document.getElementById("register-username").value;
  const email = document.getElementById("register-email").value;
  const password = document.getElementById("register-password").value;

  try {
    await apiFetch("/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, email, password }),
    });
    const data = await apiFetch("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    setSession(data.token, data.user);
    window.location.href = "/projects.html";
  } catch (err) {
    errorMessage.textContent = err.message;
  }
});
