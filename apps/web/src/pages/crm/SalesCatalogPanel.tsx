import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeDollarSign, FileCheck2, PackagePlus } from "lucide-react";
import { Alert, Button } from "@orkestral/ui-components";
import { ApiClientError, request } from "../../lib/http";
import { useSession } from "../../session/context";

type InventoryItem = {
  id: string;
  sku: string;
  name: string;
  unit: string;
  active: boolean;
};

type Opportunity = {
  id: string;
  title: string;
  status: "open" | "won" | "lost";
};

type PriceBook = {
  id: string;
  name: string;
  currency: string;
  status: "draft" | "published" | "archived";
  version: number;
  entries: Array<{
    inventory_item_id: string;
    sku: string;
    item_name: string;
    unit_price: string;
  }>;
};

type Quote = {
  id: string;
  quote_number: string;
  title: string;
  status: "draft" | "published" | "accepted" | "rejected" | "expired";
  total: string;
  valid_until: string;
  items: Array<{ sku: string; description: string; quantity: string }>;
};

function errorMessage(error: unknown, fallback: string) {
  return error instanceof ApiClientError ? error.message : fallback;
}

export function SalesCatalogPanel() {
  const session = useSession();
  const readOnly = session.me?.access_mode === "read_only";
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [bookName, setBookName] = useState("");
  const [bookId, setBookId] = useState("");
  const [productId, setProductId] = useState("");
  const [unitPrice, setUnitPrice] = useState("");
  const [opportunityId, setOpportunityId] = useState("");
  const [quoteTitle, setQuoteTitle] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [discount, setDiscount] = useState("0");
  const [validUntil, setValidUntil] = useState(
    new Date(Date.now() + 15 * 86_400_000).toISOString().slice(0, 10),
  );

  const priceBooks = useQuery({
    queryKey: ["crm-price-books"],
    queryFn: () => request<PriceBook[]>("/crm/sales/price-books"),
  });
  const quotes = useQuery({
    queryKey: ["crm-quotes"],
    queryFn: () => request<Quote[]>("/crm/sales/quotes"),
  });
  const products = useQuery({
    queryKey: ["inventory-items"],
    queryFn: () => request<InventoryItem[]>("/inventory/items"),
  });
  const opportunities = useQuery({
    queryKey: ["crm-opportunities"],
    queryFn: () =>
      request<Opportunity[]>("/crm/opportunities?opportunity_status=open"),
  });

  const draftBook =
    priceBooks.data?.find((book) => book.id === bookId) ??
    priceBooks.data?.find((book) => book.status === "draft");
  const publishedBook = priceBooks.data?.find(
    (book) => book.status === "published",
  );
  const quoteProductId =
    productId || publishedBook?.entries[0]?.inventory_item_id || "";
  const money = useMemo(
    () =>
      new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: publishedBook?.currency ?? "BRL",
      }),
    [publishedBook?.currency],
  );

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["crm-price-books"] }),
      queryClient.invalidateQueries({ queryKey: ["crm-quotes"] }),
      queryClient.invalidateQueries({ queryKey: ["crm-opportunities"] }),
    ]);
  };

  const createBook = useMutation({
    mutationFn: () =>
      request<PriceBook>("/crm/sales/price-books", {
        method: "POST",
        body: { name: bookName, currency: "BRL", is_default: true },
      }),
    onSuccess: async (book) => {
      setBookName("");
      setBookId(book.id);
      setError(null);
      await refresh();
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível criar a tabela.")),
  });

  const setPrice = useMutation({
    mutationFn: () =>
      request<PriceBook>(
        `/crm/sales/price-books/${draftBook?.id}/entries`,
        {
          method: "PUT",
          body: {
            inventory_item_id: productId,
            unit_price: Number(unitPrice),
            minimum_quantity: 1,
          },
        },
      ),
    onSuccess: async () => {
      setUnitPrice("");
      setError(null);
      await refresh();
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível registrar o preço.")),
  });

  const publishBook = useMutation({
    mutationFn: (id: string) =>
      request<PriceBook>(`/crm/sales/price-books/${id}/publish`, {
        method: "POST",
      }),
    onSuccess: refresh,
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível publicar a tabela.")),
  });

  const createQuote = useMutation({
    mutationFn: () => {
      if (!publishedBook) throw new Error("Publique uma tabela de preços.");
      return request<Quote>("/crm/sales/quotes", {
        method: "POST",
        body: {
          opportunity_id: opportunityId,
          price_book_id: publishedBook.id,
          title: quoteTitle,
          valid_until: validUntil,
          items: [
            {
              inventory_item_id: quoteProductId,
              quantity: Number(quantity),
              discount_percent: Number(discount),
            },
          ],
        },
      });
    },
    onSuccess: async () => {
      setQuoteTitle("");
      setError(null);
      await refresh();
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível criar a proposta.")),
  });

  const quoteAction = useMutation({
    mutationFn: ({
      quote,
      action,
    }: {
      quote: Quote;
      action: "publish" | "accepted" | "rejected";
    }) =>
      request<Quote>(
        action === "publish"
          ? `/crm/sales/quotes/${quote.id}/publish`
          : `/crm/sales/quotes/${quote.id}/decision`,
        {
          method: "POST",
          body:
            action === "publish"
              ? undefined
              : {
                  decision: action,
                  note: `Decisão registrada para ${quote.quote_number}.`,
                },
        },
      ),
    onSuccess: refresh,
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível atualizar a proposta.")),
  });

  return (
    <details className="crm-pipeline-disclosure sales-catalog" open>
      <summary>
        <span>Catálogo, preços e propostas</span>
        <small>
          Transforme produtos do estoque em ofertas comerciais auditáveis.
        </small>
      </summary>
      {error ? <Alert variant="error">{error}</Alert> : null}
      {products.isError ? (
        <Alert variant="error">
          Ative o módulo Estoque para usar produtos no catálogo comercial.
        </Alert>
      ) : null}
      <div className="sales-catalog__grid">
        <form
          className="sales-catalog__card"
          onSubmit={(event) => {
            event.preventDefault();
            createBook.mutate();
          }}
        >
          <strong>
            <BadgeDollarSign size={18} /> Nova tabela de preços
          </strong>
          <label>
            Nome
            <input
              disabled={readOnly}
              onChange={(event) => setBookName(event.target.value)}
              placeholder="Ex.: Comercial 2026"
              value={bookName}
            />
          </label>
          <Button
            disabled={readOnly || bookName.trim().length < 2}
            loading={createBook.isPending}
            type="submit"
          >
            Criar tabela
          </Button>
          <div className="sales-catalog__list">
            {priceBooks.data?.map((book) => (
              <button
                className={book.id === draftBook?.id ? "selected" : ""}
                key={book.id}
                onClick={() => setBookId(book.id)}
                type="button"
              >
                <span>{book.name}</span>
                <small>
                  v{book.version} · {book.status} · {book.entries.length} itens
                </small>
              </button>
            ))}
          </div>
        </form>

        <form
          className="sales-catalog__card"
          onSubmit={(event) => {
            event.preventDefault();
            setPrice.mutate();
          }}
        >
          <strong>
            <PackagePlus size={18} /> Precificar produto
          </strong>
          <label>
            Produto do estoque
            <select
              disabled={readOnly}
              onChange={(event) => setProductId(event.target.value)}
              value={productId}
            >
              <option value="">Selecione</option>
              {products.data
                ?.filter((item) => item.active)
                .map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.sku} · {item.name}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Preço unitário
            <input
              disabled={readOnly}
              min="0"
              onChange={(event) => setUnitPrice(event.target.value)}
              step="0.01"
              type="number"
              value={unitPrice}
            />
          </label>
          <Button
            disabled={
              readOnly ||
              !draftBook ||
              draftBook.status !== "draft" ||
              !productId ||
              unitPrice === ""
            }
            loading={setPrice.isPending}
            type="submit"
          >
            Salvar preço
          </Button>
          {draftBook?.status === "draft" ? (
            <Button
              disabled={readOnly || draftBook.entries.length === 0}
              loading={publishBook.isPending}
              onClick={() => publishBook.mutate(draftBook.id)}
              type="button"
              variant="secondary"
            >
              Publicar tabela
            </Button>
          ) : null}
        </form>

        <form
          className="sales-catalog__card"
          onSubmit={(event) => {
            event.preventDefault();
            createQuote.mutate();
          }}
        >
          <strong>
            <FileCheck2 size={18} /> Nova proposta
          </strong>
          <label>
            Oportunidade
            <select
              disabled={readOnly}
              onChange={(event) => setOpportunityId(event.target.value)}
              value={opportunityId}
            >
              <option value="">Selecione</option>
              {opportunities.data?.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            Título
            <input
              disabled={readOnly}
              onChange={(event) => setQuoteTitle(event.target.value)}
              value={quoteTitle}
            />
          </label>
          <label>
            Produto
            <select
              disabled={readOnly}
              onChange={(event) => setProductId(event.target.value)}
              value={quoteProductId}
            >
              <option value="">Selecione</option>
              {publishedBook?.entries.map((entry) => (
                <option
                  key={entry.inventory_item_id}
                  value={entry.inventory_item_id}
                >
                  {entry.sku} · {entry.item_name} ·{" "}
                  {money.format(Number(entry.unit_price))}
                </option>
              ))}
            </select>
          </label>
          <div className="sales-catalog__row">
            <label>
              Quantidade
              <input
                disabled={readOnly}
                min="0.001"
                onChange={(event) => setQuantity(event.target.value)}
                step="0.001"
                type="number"
                value={quantity}
              />
            </label>
            <label>
              Desconto %
              <input
                disabled={readOnly}
                max="100"
                min="0"
                onChange={(event) => setDiscount(event.target.value)}
                step="0.01"
                type="number"
                value={discount}
              />
            </label>
          </div>
          <label>
            Validade
            <input
              disabled={readOnly}
              min={new Date().toISOString().slice(0, 10)}
              onChange={(event) => setValidUntil(event.target.value)}
              type="date"
              value={validUntil}
            />
          </label>
          <Button
            disabled={
              readOnly ||
              !publishedBook ||
              !opportunityId ||
              !quoteProductId ||
              quoteTitle.trim().length < 2
            }
            loading={createQuote.isPending}
            type="submit"
          >
            Criar proposta
          </Button>
        </form>
      </div>

      <div className="sales-catalog__quotes">
        <strong>Propostas comerciais</strong>
        {quotes.data?.length === 0 ? <p>Nenhuma proposta criada.</p> : null}
        {quotes.data?.map((quote) => (
          <article key={quote.id}>
            <div>
              <span>{quote.quote_number}</span>
              <strong>{quote.title}</strong>
              <small>
                {quote.items.length} itens · válida até{" "}
                {new Date(`${quote.valid_until}T12:00:00`).toLocaleDateString(
                  "pt-BR",
                )}
              </small>
            </div>
            <b>{money.format(Number(quote.total))}</b>
            <span className="sales-prospecting__status">{quote.status}</span>
            <div className="sales-prospecting__actions">
              {quote.status === "draft" ? (
                <Button
                  disabled={readOnly}
                  onClick={() =>
                    quoteAction.mutate({ quote, action: "publish" })
                  }
                  variant="secondary"
                >
                  Publicar
                </Button>
              ) : null}
              {quote.status === "published" ? (
                <>
                  <Button
                    disabled={readOnly}
                    onClick={() =>
                      quoteAction.mutate({ quote, action: "accepted" })
                    }
                  >
                    Aceitar
                  </Button>
                  <Button
                    disabled={readOnly}
                    onClick={() =>
                      quoteAction.mutate({ quote, action: "rejected" })
                    }
                    variant="ghost"
                  >
                    Rejeitar
                  </Button>
                </>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </details>
  );
}
