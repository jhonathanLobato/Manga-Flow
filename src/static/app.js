const form = document.getElementById("form");
const progressWrap = document.getElementById("progressWrap");
const progressBar = document.getElementById("progressBar");
const statusEl = document.getElementById("status");
const submitBtn = document.getElementById("submit");
const profileSel = document.getElementById("profile");

function profileWH() {
  const [w, h] = profileSel.value.split("x").map(Number);
  return { w, h };
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  statusEl.textContent = "";
  progressWrap.hidden = false;
  progressBar.style.width = "0%";
  submitBtn.disabled = true;

  const fd = new FormData(form);
  const { w, h } = profileWH();
  fd.append("width", String(w));
  fd.append("height", String(h));

  // fallback defaults
  if (!fd.get("jpeg_quality")) fd.set("jpeg_quality", "80");
  if (!fd.get("title")) fd.set("title", "My Manga");
  if (!fd.get("rtl")) fd.set("rtl", "on");

  try {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/convert", true);
    xhr.responseType = "blob";

    xhr.upload.onprogress = (evt) => {
      if (evt.lengthComputable) {
        const pct = (evt.loaded / evt.total) * 100;
        progressBar.style.width = `${pct.toFixed(1)}%`;
      }
    };

    xhr.onload = () => {
      submitBtn.disabled = false;
      if (xhr.status === 200) {
        const disp = xhr.getResponseHeader("Content-Disposition") || 'attachment; filename="output.epub"';
        const match = /filename="([^"]+)"/.exec(disp);
        const filename = match ? match[1] : "output.epub";

        const url = window.URL.createObjectURL(xhr.response);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        a.click();
        window.URL.revokeObjectURL(url);
        statusEl.textContent = "Pronto! O download deve ter iniciado.";
      } else {
        // Tenta ler corpo textual
        const reader = new FileReader();
        reader.onload = () => {
          try {
            const data = JSON.parse(reader.result);
            statusEl.textContent = data.detail || "Erro na conversão.";
          } catch {
            statusEl.textContent = "Erro na conversão.";
          }
        };
        reader.readAsText(xhr.response);
      }
    };

    xhr.onerror = () => {
      submitBtn.disabled = false;
      statusEl.textContent = "Erro de rede.";
    };

    xhr.send(fd);
  } catch (err) {
    submitBtn.disabled = false;
    statusEl.textContent = "Falha inesperada.";
  }
});
