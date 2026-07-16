import { Link, Outlet } from "react-router-dom";

export function PublicLayout() {
  return (
    <div className="public-shell">
      <header className="public-header">
        <Link aria-label="Orkestral — início" className="brand" to="/">
          <span aria-hidden="true" className="brand__mark">
            O
          </span>
          <span>Orkestral</span>
        </Link>
        <Link className="public-header__access" to="/login">
          Acessar plataforma
        </Link>
      </header>
      <main>
        <Outlet />
      </main>
      <footer className="public-footer">
        Orkestral · Fundação da plataforma
      </footer>
    </div>
  );
}
