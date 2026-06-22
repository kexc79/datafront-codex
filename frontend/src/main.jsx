import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { AgGridReact } from "ag-grid-react";
import { ModuleRegistry } from "ag-grid-community";
import { AllEnterpriseModule, LicenseManager } from "ag-grid-enterprise";
import {
  Building2,
  Check,
  Database,
  FileArchive,
  LogOut,
  Moon,
  RefreshCw,
  Rows3,
  Shield,
  Sun,
  Upload,
  Users,
} from "lucide-react";

import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-quartz.css";
import "./styles.css";

ModuleRegistry.registerModules([AllEnterpriseModule]);
if (import.meta.env.VITE_AG_GRID_LICENSE_KEY) {
  LicenseManager.setLicenseKey(import.meta.env.VITE_AG_GRID_LICENSE_KEY);
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1";

function App() {
  const [token, setToken] = useState(localStorage.getItem("df_token"));
  const [me, setMe] = useState(null);
  const [activeView, setActiveView] = useState("engineer");
  const [theme, setTheme] = useState(localStorage.getItem("df_theme") || "dark");
  const api = useMemo(() => createApi(token), [token]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("df_theme", theme);
  }, [theme]);

  useEffect(() => {
    if (!token) return;
    api.get("/auth/me").then(setMe).catch(() => logout());
  }, [token]);

  function onLogin(nextToken) {
    localStorage.setItem("df_token", nextToken);
    setToken(nextToken);
  }

  function logout() {
    localStorage.removeItem("df_token");
    setToken(null);
    setMe(null);
  }

  if (!token || !me) {
    return <LoginScreen onLogin={onLogin} />;
  }

  const canAdmin = me.role === "admin";

  return (
    <div className="appShell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark">DF</div>
          <div>
            <div className="brandName">DataFront</div>
            <div className="brandMeta">engineering control</div>
          </div>
        </div>

        <nav className="navList">
          <button className={activeView === "engineer" ? "navItem active" : "navItem"} onClick={() => setActiveView("engineer")}>
            <Upload size={18} /> Загрузка отчетов
          </button>
          {canAdmin && (
            <>
              <button className={activeView === "matrix" ? "navItem active" : "navItem"} onClick={() => setActiveView("matrix")}>
                <Building2 size={18} /> Матрица
              </button>
              <button className={activeView === "plan" ? "navItem active" : "navItem"} onClick={() => setActiveView("plan")}>
                <Rows3 size={18} /> План отчетов
              </button>
              <button className={activeView === "users" ? "navItem active" : "navItem"} onClick={() => setActiveView("users")}>
                <Users size={18} /> Пользователи
              </button>
              <button className={activeView === "oracle" ? "navItem active" : "navItem"} onClick={() => setActiveView("oracle")}>
                <Database size={18} /> Oracle
              </button>
            </>
          )}
        </nav>

        <div className="sidebarFooter">
          <button className="iconButton" title="Сменить тему" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
            {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
          </button>
          <button className="iconButton" title="Выйти" onClick={logout}>
            <LogOut size={18} />
          </button>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <h1>{viewTitle(activeView)}</h1>
            <p>{me.full_name} · {roleLabel(me.role)}</p>
          </div>
          <div className="statusPill"><Shield size={16} /> {me.email}</div>
        </header>

        {activeView === "engineer" && <EngineerView api={api} />}
        {activeView === "matrix" && <MatrixView api={api} />}
        {activeView === "plan" && <PlanView api={api} />}
        {activeView === "users" && <UsersView api={api} />}
        {activeView === "oracle" && <OracleView api={api} />}
      </main>
    </div>
  );
}

function LoginScreen({ onLogin }) {
  const [email, setEmail] = useState("admin@datafront.local");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body = new URLSearchParams({ username: email, password });
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });
      if (!response.ok) throw new Error("Не удалось войти");
      const data = await response.json();
      onLogin(data.access_token);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="loginPage">
      <form className="loginPanel" onSubmit={submit}>
        <div className="brandMark large">DF</div>
        <h1>DataFront</h1>
        <input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="email" type="email" />
        <input value={password} onChange={(event) => setPassword(event.target.value)} placeholder="password" type="password" />
        {error && <div className="errorText">{error}</div>}
        <button className="primaryButton" disabled={busy}>{busy ? "Вход..." : "Войти"}</button>
      </form>
    </div>
  );
}

function EngineerView({ api }) {
  const [reports, setReports] = useState([]);
  const [selected, setSelected] = useState(null);
  const [message, setMessage] = useState("");

  async function load() {
    setReports(await api.get("/engineer/reports"));
  }

  useEffect(() => {
    load();
  }, []);

  const rows = reports.map((report) => ({
    id: report.id,
    customer: report.customer_project.customer.display_name,
    project: report.customer_project.project.type,
    country: report.country?.name || "Не указана",
    dataType: report.data_type?.name || "Не указан",
    distributor: report.distributor?.name || "Не указан",
    period: report.period,
    deadline: report.deadline,
    status: statusLabel(report.status),
    files: report.files.length,
    latestFile: report.files[0]?.original_filename || "",
    rowCount: report.files[0]?.row_count ?? "",
    packCount: report.files[0]?.pack_count ?? "",
  }));

  async function uploadFile(event) {
    const file = event.target.files?.[0];
    if (!file || !selected) return;
    const body = new FormData();
    body.append("upload", file);
    await api.postFile(`/engineer/reports/${selected.id}/files`, body);
    setMessage("Файл загружен");
    event.target.value = "";
    await load();
  }

  return (
    <section className="contentBand">
      <div className="toolbar">
        <button className="secondaryButton" onClick={load}><RefreshCw size={16} /> Обновить</button>
        <label className={selected ? "uploadButton" : "uploadButton disabled"}>
          <FileArchive size={16} /> Загрузить файл
          <input disabled={!selected} type="file" onChange={uploadFile} />
        </label>
        {message && <span className="okText">{message}</span>}
      </div>
      <DataGrid
        rows={rows}
        onRowClicked={(event) => setSelected(reports.find((report) => report.id === event.data.id))}
        columnDefs={[
          { field: "customer", headerName: "Заказчик", rowGroup: true, hide: true },
          { field: "project", headerName: "Проект", rowGroup: true, hide: true },
          { field: "country", headerName: "Страна", rowGroup: true, hide: true },
          { field: "period", headerName: "Период", rowGroup: true, hide: true },
          { field: "distributor", headerName: "Дистрибьютор" },
          { field: "dataType", headerName: "Тип данных" },
          { field: "status", headerName: "Статус" },
          { field: "files", headerName: "Файлы", width: 100 },
          { field: "latestFile", headerName: "Последний файл" },
          { field: "rowCount", headerName: "Строки", editable: false, width: 110 },
          { field: "packCount", headerName: "Пачки", editable: false, width: 110 },
        ]}
      />
      {selected && <FileEditor api={api} report={selected} onSaved={load} />}
    </section>
  );
}

function FileEditor({ api, report, onSaved }) {
  const file = report.files[0];
  const [rowCount, setRowCount] = useState(file?.row_count ?? "");
  const [packCount, setPackCount] = useState(file?.pack_count ?? "");
  const [comment, setComment] = useState(file?.comment ?? "");
  const [active, setActive] = useState(file?.active ?? true);

  useEffect(() => {
    setRowCount(file?.row_count ?? "");
    setPackCount(file?.pack_count ?? "");
    setComment(file?.comment ?? "");
    setActive(file?.active ?? true);
  }, [file?.id]);

  if (!file) {
    return <div className="detailPanel">Для выбранного ожидания файл еще не загружен.</div>;
  }

  async function save() {
    await api.patch(`/engineer/files/${file.id}`, {
      row_count: rowCount === "" ? null : Number(rowCount),
      pack_count: packCount === "" ? null : Number(packCount),
      comment,
      active,
    });
    await onSaved();
  }

  async function feedback() {
    await api.post(`/engineer/files/${file.id}/feedback`, { comment: comment || "Требуется обратная связь" });
    await onSaved();
  }

  return (
    <div className="detailPanel compactForm">
      <strong>{file.original_filename}</strong>
      <input value={rowCount} onChange={(event) => setRowCount(event.target.value)} placeholder="Количество строк" type="number" min="0" />
      <input value={packCount} onChange={(event) => setPackCount(event.target.value)} placeholder="Количество пачек" type="number" min="0" />
      <input value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Комментарий" />
      <label className="checkLine"><input checked={active} onChange={(event) => setActive(event.target.checked)} type="checkbox" /> Активен</label>
      <button className="primaryButton small" onClick={save}><Check size={16} /> Сохранить</button>
      <button className="secondaryButton small" onClick={feedback}>Вопросы</button>
    </div>
  );
}

function MatrixView({ api }) {
  const [rows, setRows] = useState([]);

  async function load() {
    setRows(await api.get("/admin/customer-projects"));
  }

  useEffect(() => {
    load();
  }, []);

  async function toggle(pair) {
    await api.patch(`/admin/customer-projects/${pair.id}`, { active: !pair.active });
    await load();
  }

  const projects = Array.from(
    new Map(rows.map((item) => [item.project.id, item.project])).values()
  ).sort((left, right) => left.type.localeCompare(right.type));

  const customers = Array.from(
    new Map(rows.map((item) => [item.customer.id, item.customer])).values()
  ).sort((left, right) => left.oracle_id - right.oracle_id);

  const matrixRows = customers.map((customer) => {
    const row = {
      customer: customer.display_name,
    };
    for (const project of projects) {
      row[`project_${project.id}`] = rows.find(
        (item) => item.customer.id === customer.id && item.project.id === project.id
      );
    }
    return row;
  });

  return (
    <section className="contentBand">
      <div className="toolbar"><button className="secondaryButton" onClick={load}><RefreshCw size={16} /> Обновить</button></div>
      <DataGrid
        rows={matrixRows}
        columnDefs={[
          { field: "customer", headerName: "Заказчик", pinned: "left", minWidth: 260, flex: 1 },
          ...projects.map((project) => ({
            field: `project_${project.id}`,
            headerName: project.type,
            minWidth: 130,
            flex: 0,
            sortable: false,
            filter: false,
            cellRenderer: (params) => {
              const pair = params.value;
              if (!pair) return "";
              return (
                <button
                  className={pair.active ? "gridToggle on" : "gridToggle"}
                  title={pair.active ? "Отключить сочетание" : "Включить сочетание"}
                  onClick={() => toggle(pair)}
                >
                  {pair.active ? "✓" : ""}
                </button>
              );
            },
          })),
        ]}
      />
    </section>
  );
}

function PlanView({ api }) {
  const [reports, setReports] = useState([]);
  const [pairs, setPairs] = useState([]);
  const [countries, setCountries] = useState([]);
  const [dataTypes, setDataTypes] = useState([]);
  const [distributors, setDistributors] = useState([]);
  const [form, setForm] = useState({
    customer_project_id: "",
    country_id: "",
    data_type_id: "",
    distributor_id: "",
    period: new Date().toISOString().slice(0, 8) + "01",
    deadline: "",
    active: true,
  });

  async function load() {
    const [nextReports, nextPairs, nextCountries, nextDataTypes, nextDistributors] = await Promise.all([
      api.get("/admin/expected-reports"),
      api.get("/admin/customer-projects"),
      api.get("/admin/dictionary-items/countries"),
      api.get("/admin/dictionary-items/data_types"),
      api.get("/admin/dictionary-items/distributors"),
    ]);
    setReports(nextReports);
    setPairs(nextPairs.filter((pair) => pair.active));
    setCountries(nextCountries);
    setDataTypes(nextDataTypes);
    setDistributors(nextDistributors);
  }

  useEffect(() => {
    load();
  }, []);

  async function create(event) {
    event.preventDefault();
    await api.post("/admin/expected-reports", {
      ...form,
      customer_project_id: Number(form.customer_project_id),
      country_id: form.country_id ? Number(form.country_id) : null,
      data_type_id: form.data_type_id ? Number(form.data_type_id) : null,
      distributor_id: form.distributor_id ? Number(form.distributor_id) : null,
      deadline: form.deadline || null,
    });
    await load();
  }

  return (
    <section className="contentBand">
      <form className="toolbar wrap" onSubmit={create}>
        <select value={form.customer_project_id} onChange={(event) => setForm({ ...form, customer_project_id: event.target.value })} required>
          <option value="">Заказчик / проект</option>
          {pairs.map((pair) => (
            <option key={pair.id} value={pair.id}>{pair.customer.display_name} · {pair.project.type}</option>
          ))}
        </select>
        <select value={form.country_id} onChange={(event) => setForm({ ...form, country_id: event.target.value })}>
          <option value="">Страна</option>
          {countries.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
        <select value={form.data_type_id} onChange={(event) => setForm({ ...form, data_type_id: event.target.value })}>
          <option value="">Тип данных</option>
          {dataTypes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
        <select value={form.distributor_id} onChange={(event) => setForm({ ...form, distributor_id: event.target.value })}>
          <option value="">Дистрибьютор</option>
          {distributors.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
        <input type="date" value={form.period} onChange={(event) => setForm({ ...form, period: event.target.value })} required />
        <input type="date" value={form.deadline} onChange={(event) => setForm({ ...form, deadline: event.target.value })} />
        <button className="primaryButton small">Добавить</button>
      </form>
      <DataGrid
        rows={reports.map((report) => ({
          id: report.id,
          customer: report.customer_project.customer.display_name,
          project: report.customer_project.project.type,
          country: report.country?.name || "",
          dataType: report.data_type?.name || "",
          distributor: report.distributor?.name || "",
          period: report.period,
          deadline: report.deadline,
          status: statusLabel(report.status),
          active: report.active,
        }))}
        columnDefs={[
          { field: "customer", headerName: "Заказчик" },
          { field: "project", headerName: "Проект" },
          { field: "period", headerName: "Период" },
          { field: "deadline", headerName: "Дедлайн" },
          { field: "status", headerName: "Статус" },
          { field: "active", headerName: "Активен", width: 110 },
        ]}
      />
    </section>
  );
}

function UsersView({ api }) {
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState({ email: "", full_name: "", password: "", role: "engineer" });

  async function load() {
    setUsers(await api.get("/admin/users"));
  }

  useEffect(() => {
    load();
  }, []);

  async function create(event) {
    event.preventDefault();
    await api.post("/admin/users", form);
    setForm({ email: "", full_name: "", password: "", role: "engineer" });
    await load();
  }

  return (
    <section className="contentBand">
      <form className="toolbar wrap" onSubmit={create}>
        <input value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} placeholder="email" type="email" required />
        <input value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} placeholder="Имя" required />
        <input value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} placeholder="Пароль" type="password" required />
        <select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}>
          <option value="engineer">Инженер</option>
          <option value="customer">Заказчик</option>
          <option value="admin">Админ</option>
        </select>
        <button className="primaryButton small">Создать</button>
      </form>
      <DataGrid
        rows={users}
        columnDefs={[
          { field: "email", headerName: "Email" },
          { field: "full_name", headerName: "Имя" },
          { field: "role", headerName: "Роль", valueFormatter: (params) => roleLabel(params.value) },
          { field: "active", headerName: "Активен", width: 120 },
        ]}
      />
    </section>
  );
}

function OracleView({ api }) {
  const [queries, setQueries] = useState([]);
  const [message, setMessage] = useState("");

  async function load() {
    setQueries(await api.get("/admin/dictionary-queries"));
  }

  useEffect(() => {
    load();
  }, []);

  async function sync(key) {
    const result = await api.post(`/admin/sync/${key}`, {});
    setMessage(result.warning || `Синхронизировано: ${result.synced}`);
    await load();
  }

  return (
    <section className="contentBand">
      <div className="toolbar">
        <button className="secondaryButton" onClick={load}><RefreshCw size={16} /> Обновить</button>
        {message && <span className="okText">{message}</span>}
      </div>
      <DataGrid
        rows={queries}
        columnDefs={[
          { field: "key", headerName: "Справочник", width: 160 },
          { field: "active", headerName: "Активен", width: 110 },
          { field: "sql_text", headerName: "SQL", flex: 2 },
          { field: "last_error", headerName: "Ошибка", flex: 1 },
          {
            field: "sync",
            headerName: "",
            width: 130,
            cellRenderer: (params) => <button className="gridToggle on" onClick={() => sync(params.data.key)}>Sync</button>,
          },
        ]}
      />
    </section>
  );
}

function DataGrid({ rows, columnDefs, onRowClicked }) {
  return (
    <div className="gridShell ag-theme-quartz">
      <AgGridReact
        rowData={rows}
        columnDefs={columnDefs}
        onRowClicked={onRowClicked}
        groupDisplayType="groupRows"
        animateRows
        defaultColDef={{ sortable: true, filter: true, resizable: true, flex: 1, minWidth: 120 }}
        pagination
        paginationPageSize={25}
      />
    </div>
  );
}

function createApi(token) {
  async function request(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        Authorization: `Bearer ${token}`,
        ...(options.headers || {}),
      },
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(detail.detail || "Request failed");
    }
    return response.status === 204 ? null : response.json();
  }
  return {
    get: (path) => request(path),
    post: (path, body) => request(path, { method: "POST", body: JSON.stringify(body) }),
    patch: (path, body) => request(path, { method: "PATCH", body: JSON.stringify(body) }),
    postFile: (path, body) => request(path, { method: "POST", body }),
  };
}

function statusLabel(status) {
  return {
    not_received: "Не получен",
    received: "Получен",
    counted: "Подсчитан",
    feedback: "Вопросы",
  }[status] || status;
}

function roleLabel(role) {
  return { admin: "Админ", engineer: "Инженер", customer: "Заказчик" }[role] || role;
}

function viewTitle(view) {
  return {
    engineer: "Загрузка отчетов",
    matrix: "Матрица заказчик-проект",
    plan: "План ожидаемых отчетов",
    users: "Пользователи",
    oracle: "Oracle справочники",
  }[view];
}

createRoot(document.getElementById("root")).render(<App />);
