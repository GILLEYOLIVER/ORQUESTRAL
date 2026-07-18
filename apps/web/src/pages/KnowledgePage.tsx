import { type FormEvent, useEffect, useMemo, useState } from "react";
import {
  BookOpenText,
  FileSearch,
  Globe2,
  Link2,
  LoaderCircle,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  UploadCloud,
} from "lucide-react";

import {
  type KnowledgeSearchResult,
  useKnowledgeActions,
  useKnowledgeAgents,
  useKnowledgeBases,
  useKnowledgeDocuments,
} from "../knowledge/useKnowledge";
import "../knowledge/knowledge.css";

const statusLabels: Record<string, string> = {
  uploaded: "Na fila",
  processing: "Processando",
  ready: "Disponivel",
  error: "Falhou",
};

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Nao foi possivel concluir a operacao.";
}

export function KnowledgePage() {
  const bases = useKnowledgeBases();
  const agents = useKnowledgeAgents();
  const actions = useKnowledgeActions();
  const [selectedBaseId, setSelectedBaseId] = useState<string | null>(null);
  const [baseName, setBaseName] = useState("");
  const [baseDescription, setBaseDescription] = useState("");
  const [webUrl, setWebUrl] = useState("");
  const [searchText, setSearchText] = useState("");
  const [searchResults, setSearchResults] = useState<KnowledgeSearchResult[]>([]);
  const [feedback, setFeedback] = useState<string | null>(null);
  const documents = useKnowledgeDocuments(selectedBaseId);

  useEffect(() => {
    if (!selectedBaseId && bases.data?.length) setSelectedBaseId(bases.data[0].id);
  }, [bases.data, selectedBaseId]);

  const selectedBase = useMemo(
    () => bases.data?.find((item) => item.id === selectedBaseId) ?? null,
    [bases.data, selectedBaseId],
  );

  async function createBase(event: FormEvent) {
    event.preventDefault();
    setFeedback(null);
    try {
      const created = await actions.createBase.mutateAsync({
        name: baseName.trim(),
        description: baseDescription.trim(),
      });
      setBaseName("");
      setBaseDescription("");
      setSelectedBaseId(created.id);
      setFeedback("Base criada e pronta para receber documentos.");
    } catch (error) {
      setFeedback(errorMessage(error));
    }
  }

  async function uploadFile(file?: File) {
    if (!selectedBaseId || !file) return;
    setFeedback(null);
    try {
      await actions.uploadDocument.mutateAsync({ baseId: selectedBaseId, file });
      setFeedback("Documento recebido. O processamento continua em segundo plano.");
    } catch (error) {
      setFeedback(errorMessage(error));
    }
  }

  async function importWeb(event: FormEvent) {
    event.preventDefault();
    if (!selectedBaseId) return;
    setFeedback(null);
    try {
      await actions.importWebPage.mutateAsync({ baseId: selectedBaseId, url: webUrl.trim() });
      setWebUrl("");
      setFeedback("Pagina autorizada recebida para processamento.");
    } catch (error) {
      setFeedback(errorMessage(error));
    }
  }

  async function runSearch(event: FormEvent) {
    event.preventDefault();
    if (!selectedBaseId) return;
    setFeedback(null);
    try {
      setSearchResults(
        await actions.search.mutateAsync({ baseId: selectedBaseId, query: searchText.trim() }),
      );
    } catch (error) {
      setFeedback(errorMessage(error));
    }
  }

  return (
    <div className="knowledge-page">
      <header className="knowledge-hero">
        <div>
          <span className="knowledge-kicker">Biblioteca operacional</span>
          <h1>Conhecimento que trabalha junto com seus agentes.</h1>
          <p>
            Reuna fontes autorizadas, acompanhe o processamento e entregue contexto interno
            rastreavel para cada resposta.
          </p>
        </div>
        <div className="knowledge-hero-mark" aria-hidden="true">
          <BookOpenText size={42} />
          <span>{documents.data?.filter((item) => item.status === "ready").length ?? 0}</span>
          <small>fontes prontas</small>
        </div>
      </header>

      {feedback ? <div className="knowledge-feedback">{feedback}</div> : null}

      <section className="knowledge-grid knowledge-grid--top">
        <article className="knowledge-panel">
          <div className="knowledge-panel-title">
            <div><span>01</span><h2>Bases</h2></div>
            <small>{bases.data?.length ?? 0} cadastradas</small>
          </div>
          <div className="knowledge-base-list">
            {bases.data?.map((base) => (
              <button
                className={base.id === selectedBaseId ? "is-active" : ""}
                key={base.id}
                onClick={() => {
                  setSelectedBaseId(base.id);
                  setSearchResults([]);
                }}
                type="button"
              >
                <span>{base.name}</span>
                <small>{base.description || "Sem descricao"}</small>
              </button>
            ))}
          </div>
          <form className="knowledge-create" onSubmit={(event) => void createBase(event)}>
            <label>
              Nova base
              <input
                onChange={(event) => setBaseName(event.target.value)}
                placeholder="Ex.: Operacao comercial"
                required
                value={baseName}
              />
            </label>
            <textarea
              onChange={(event) => setBaseDescription(event.target.value)}
              placeholder="O que os agentes encontrarao aqui?"
              value={baseDescription}
            />
            <button disabled={actions.createBase.isPending} type="submit">
              <Plus size={16} /> Criar base
            </button>
          </form>
        </article>

        <article className="knowledge-panel">
          <div className="knowledge-panel-title">
            <div><span>02</span><h2>Fontes</h2></div>
            <small>{selectedBase?.name ?? "Selecione uma base"}</small>
          </div>
          <label className={`knowledge-drop ${!selectedBaseId ? "is-disabled" : ""}`}>
            <UploadCloud size={30} />
            <strong>Enviar um documento</strong>
            <span>PDF, DOCX, TXT, CSV ou XLSX. Limite de 20 MB.</span>
            <input
              accept=".pdf,.docx,.txt,.csv,.xlsx"
              disabled={!selectedBaseId || actions.uploadDocument.isPending}
              onChange={(event) => {
                void uploadFile(event.target.files?.[0]);
                event.target.value = "";
              }}
              type="file"
            />
          </label>
          <form className="knowledge-web" onSubmit={(event) => void importWeb(event)}>
            <Globe2 size={19} />
            <input
              disabled={!selectedBaseId}
              onChange={(event) => setWebUrl(event.target.value)}
              placeholder="https://dominio-autorizado.com/pagina"
              required
              type="url"
              value={webUrl}
            />
            <button disabled={!selectedBaseId || actions.importWebPage.isPending} type="submit">
              Importar
            </button>
          </form>
          <p className="knowledge-hint">
            Paginas web so entram quando o dominio esta na lista segura da instalacao.
          </p>
        </article>
      </section>

      <section className="knowledge-panel">
        <div className="knowledge-panel-title">
          <div><span>03</span><h2>Processamento</h2></div>
          {documents.isFetching ? <LoaderCircle className="knowledge-spin" size={18} /> : null}
        </div>
        <div className="knowledge-document-list">
          {documents.data?.map((document) => (
            <article key={document.id}>
              <FileSearch size={21} />
              <div>
                <strong>{document.name}</strong>
                <small>{document.source_type.toUpperCase()} · {(document.size_bytes / 1024).toFixed(1)} KB</small>
                {document.error_summary ? <em>{document.error_summary}</em> : null}
              </div>
              <span className={`knowledge-status knowledge-status--${document.status}`}>
                {statusLabels[document.status] ?? document.status}
              </span>
              <button
                aria-label="Reprocessar documento"
                onClick={() => selectedBaseId && void actions.reprocessDocument.mutateAsync({ baseId: selectedBaseId, documentId: document.id })}
                title="Reprocessar"
                type="button"
              ><RefreshCw size={16} /></button>
              <button
                aria-label="Excluir documento"
                className="is-danger"
                onClick={() => selectedBaseId && window.confirm(`Excluir ${document.name}?`) && void actions.deleteDocument.mutateAsync({ baseId: selectedBaseId, documentId: document.id })}
                title="Excluir"
                type="button"
              ><Trash2 size={16} /></button>
            </article>
          ))}
          {!documents.data?.length ? <div className="knowledge-empty">Nenhuma fonte nesta base ainda.</div> : null}
        </div>
      </section>

      <section className="knowledge-grid knowledge-grid--bottom">
        <article className="knowledge-panel">
          <div className="knowledge-panel-title">
            <div><span>04</span><h2>Conectar agentes</h2></div><Link2 size={18} />
          </div>
          <div className="knowledge-agent-list">
            {agents.data?.map((agent) => (
              <label key={agent.id}>
                <span>{agent.name}</span>
                <select
                  onChange={(event) => void actions.assignAgent.mutateAsync({ agentId: agent.id, baseId: event.target.value || null })}
                  value={agent.knowledge_base_id ?? ""}
                >
                  <option value="">Sem base vinculada</option>
                  {bases.data?.map((base) => <option key={base.id} value={base.id}>{base.name}</option>)}
                </select>
              </label>
            ))}
          </div>
        </article>

        <article className="knowledge-panel knowledge-search">
          <div className="knowledge-panel-title">
            <div><span>05</span><h2>Testar recuperacao</h2></div><Search size={18} />
          </div>
          <form onSubmit={(event) => void runSearch(event)}>
            <input
              disabled={!selectedBaseId}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="O que o agente deve encontrar?"
              required
              value={searchText}
            />
            <button disabled={!selectedBaseId || actions.search.isPending} type="submit">Buscar</button>
          </form>
          <div className="knowledge-results">
            {searchResults.map((result) => (
              <article key={`${result.document_id}-${result.chunk_index}`}>
                <strong>{result.document_name}</strong>
                <small>Trecho {result.chunk_index + 1} · aderencia {(result.score * 100).toFixed(0)}%</small>
                <p>{result.content}</p>
              </article>
            ))}
          </div>
        </article>
      </section>
    </div>
  );
}
