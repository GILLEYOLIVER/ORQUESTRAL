import { ArrowRight, Bot, Cable, ShieldCheck, Workflow } from "lucide-react";
import { Link } from "react-router-dom";

export function LandingPage() {
  return (
    <div className="landing">
      <section className="hero">
        <div className="hero__content">
          <span className="eyebrow">
            Operação mais simples. Negócios mais conectados.
          </span>
          <h1>Automação empresarial em uma só orquestra.</h1>
          <p>
            Conecte processos, integrações e agentes de inteligência artificial
            sem expor a complexidade técnica para sua equipe.
          </p>
          <Link className="hero__cta" to="/login">
            Conhecer a plataforma <ArrowRight size={18} />
          </Link>
        </div>
        <div
          aria-label="Capacidades da plataforma"
          className="capability-panel"
        >
          <div className="capability-panel__top">
            <span>Fundação Orkestral</span>
            <span className="status-dot">Estrutura ativa</span>
          </div>
          <div className="capability-grid">
            <article>
              <Workflow />
              <strong>Automações</strong>
              <span>Fluxos empresariais organizados</span>
            </article>
            <article>
              <Bot />
              <strong>Agentes de IA</strong>
              <span>Ferramentas sob controle</span>
            </article>
            <article>
              <Cable />
              <strong>Integrações</strong>
              <span>Sistemas conectados</span>
            </article>
            <article>
              <ShieldCheck />
              <strong>Governança</strong>
              <span>Segurança desde a base</span>
            </article>
          </div>
        </div>
      </section>
      <section className="principles" aria-label="Princípios da Orkestral">
        <div>
          <span>01</span>
          <strong>Modular por natureza</strong>
          <p>Cada empresa ativa apenas o que precisa.</p>
        </div>
        <div>
          <span>02</span>
          <strong>Segurança no núcleo</strong>
          <p>Isolamento e rastreabilidade orientam a arquitetura.</p>
        </div>
        <div>
          <span>03</span>
          <strong>Linguagem empresarial</strong>
          <p>A tecnologia trabalha nos bastidores.</p>
        </div>
      </section>
    </div>
  );
}
