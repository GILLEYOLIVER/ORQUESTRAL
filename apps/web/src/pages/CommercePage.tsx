import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgePercent, Boxes, FileCheck2, ShoppingBag } from "lucide-react";
import { Alert, Button, Card } from "@orkestral/ui-components";
import { ApiClientError, request } from "../lib/http";
import { useSession } from "../session/context";
import "./commerce.css";

type Item = { id: string; sku: string; name: string; active: boolean };
type Variant = { id: string; inventory_item_id: string; sku: string; name: string };
type Promotion = {
  id: string;
  name: string;
  code: string | null;
  discount_type: "percent" | "fixed";
  discount_value: number;
  status: "draft" | "active" | "paused" | "expired";
};
type Quote = { id: string; quote_number: string; title: string; status: string; total: number };
type Location = { id: string; code: string; name: string; active: boolean };
type Order = {
  id: string;
  order_number: string;
  status: "draft" | "reserved" | "confirmed" | "fulfilled" | "cancelled";
  total: number;
  items: Array<{ id: string; sku: string; description: string; quantity: number }>;
};
type Contract = {
  id: string;
  contract_number: string;
  title: string;
  status: string;
  billing_interval: string | null;
  next_billing_on: string | null;
};

function message(error: unknown) {
  return error instanceof ApiClientError ? error.message : "Não foi possível concluir a ação.";
}

export function CommercePage() {
  const { me } = useSession();
  const queryClient = useQueryClient();
  const readOnly = me?.access_mode === "read_only";
  const [itemId, setItemId] = useState("");
  const [sku, setSku] = useState("");
  const [variantName, setVariantName] = useState("");
  const [promotionName, setPromotionName] = useState("");
  const [code, setCode] = useState("");
  const [discount, setDiscount] = useState("10");
  const [quoteId, setQuoteId] = useState("");
  const [locationId, setLocationId] = useState("");
  const [contract, setContract] = useState(false);
  const [recurring, setRecurring] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const items = useQuery({
    queryKey: ["inventory", "items", "commerce"],
    queryFn: () => request<Item[]>("/inventory/items"),
  });
  const variants = useQuery({
    queryKey: ["commerce", "variants"],
    queryFn: () => request<Variant[]>("/commerce/variants"),
  });
  const promotions = useQuery({
    queryKey: ["commerce", "promotions"],
    queryFn: () => request<Promotion[]>("/commerce/promotions"),
  });
  const quotes = useQuery({
    queryKey: ["crm-quotes", "commerce"],
    queryFn: () => request<Quote[]>("/crm/sales/quotes"),
  });
  const locations = useQuery({
    queryKey: ["inventory", "locations", "commerce"],
    queryFn: () => request<Location[]>("/inventory/locations"),
  });
  const orders = useQuery({
    queryKey: ["commerce", "orders"],
    queryFn: () => request<Order[]>("/commerce/orders"),
  });
  const contracts = useQuery({
    queryKey: ["commerce", "contracts"],
    queryFn: () => request<Contract[]>("/commerce/contracts"),
  });
  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ["commerce", "variants"] }),
      queryClient.invalidateQueries({ queryKey: ["commerce", "promotions"] }),
      queryClient.invalidateQueries({ queryKey: ["commerce", "orders"] }),
      queryClient.invalidateQueries({ queryKey: ["commerce", "contracts"] }),
    ]);
  const createVariant = useMutation({
    mutationFn: () =>
      request<Variant>("/commerce/variants", {
        method: "POST",
        body: { inventory_item_id: itemId, sku, name: variantName, attributes: {} },
      }),
    onSuccess: async () => {
      setSku("");
      setVariantName("");
      setError(null);
      await refresh();
    },
    onError: (caught) => setError(message(caught)),
  });
  const createPromotion = useMutation({
    mutationFn: () =>
      request<Promotion>("/commerce/promotions", {
        method: "POST",
        body: {
          name: promotionName,
          code: code || null,
          discount_type: "percent",
          discount_value: Number(discount),
          applies_to: "all",
          minimum_quantity: 1,
          starts_at: new Date().toISOString(),
        },
      }),
    onSuccess: async () => {
      setPromotionName("");
      setCode("");
      setError(null);
      await refresh();
    },
    onError: (caught) => setError(message(caught)),
  });
  const activate = useMutation({
    mutationFn: (id: string) =>
      request<Promotion>(`/commerce/promotions/${id}/activate`, { method: "POST" }),
    onSuccess: refresh,
    onError: (caught) => setError(message(caught)),
  });
  const createOrder = useMutation({
    mutationFn: () =>
      request<Order>("/commerce/orders/from-quote", {
        method: "POST",
        body: {
          quote_id: quoteId,
          idempotency_key: `quote-order:${quoteId}`,
        },
      }),
    onSuccess: refresh,
    onError: (caught) => setError(message(caught)),
  });
  const reserveOrder = useMutation({
    mutationFn: (orderId: string) =>
      request<Order>(`/commerce/orders/${orderId}/reserve`, {
        method: "POST",
        body: { location_id: locationId },
      }),
    onSuccess: refresh,
    onError: (caught) => setError(message(caught)),
  });
  const confirmOrder = useMutation({
    mutationFn: (orderId: string) => {
      const due = new Date();
      due.setDate(due.getDate() + 30);
      return request<Order>(`/commerce/orders/${orderId}/confirm`, {
        method: "POST",
        body: {
          due_date: due.toISOString().slice(0, 10),
          create_contract: contract,
          billing_interval: recurring ? "monthly" : null,
        },
      });
    },
    onSuccess: refresh,
    onError: (caught) => setError(message(caught)),
  });
  const changeOrder = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "cancel" | "fulfill" }) =>
      request<Order>(`/commerce/orders/${id}/${action}`, { method: "POST" }),
    onSuccess: refresh,
    onError: (caught) => setError(message(caught)),
  });
  return (
    <div className="commerce-page">
      <header>
        <div><span>COMÉRCIO E RECEITA</span><h1>Ofertas consistentes, do catálogo ao pedido.</h1>
        <p>Variantes e promoções reutilizam produtos do estoque e tabelas de preço do CRM.</p></div>
        <ShoppingBag size={54} />
      </header>
      {error ? <Alert variant="error">{error}</Alert> : null}
      <section>
        <Card>
          <h2><Boxes size={20} /> Nova variante</h2>
          <select value={itemId} onChange={(event) => setItemId(event.target.value)}>
            <option value="">Produto do estoque</option>
            {items.data?.filter((item) => item.active).map((item) => (
              <option key={item.id} value={item.id}>{item.sku} · {item.name}</option>
            ))}
          </select>
          <input placeholder="SKU da variante" value={sku} onChange={(event) => setSku(event.target.value)} />
          <input placeholder="Nome da variante" value={variantName} onChange={(event) => setVariantName(event.target.value)} />
          <Button disabled={readOnly || !itemId || !sku || variantName.length < 2} onClick={() => createVariant.mutate()}>Criar variante</Button>
          {variants.data?.map((variant) => <small key={variant.id}>{variant.sku} · {variant.name}</small>)}
        </Card>
        <Card>
          <h2><BadgePercent size={20} /> Nova promoção</h2>
          <input placeholder="Nome da promoção" value={promotionName} onChange={(event) => setPromotionName(event.target.value)} />
          <input placeholder="Código opcional" value={code} onChange={(event) => setCode(event.target.value)} />
          <input min="0" max="100" type="number" value={discount} onChange={(event) => setDiscount(event.target.value)} />
          <Button disabled={readOnly || promotionName.length < 2} onClick={() => createPromotion.mutate()}>Criar rascunho</Button>
          {promotions.data?.map((promotion) => (
            <div className="commerce-row" key={promotion.id}>
              <span><b>{promotion.name}</b><small>{promotion.discount_value}% · {promotion.status}</small></span>
              {promotion.status === "draft" ? <Button disabled={readOnly} onClick={() => activate.mutate(promotion.id)}>Ativar</Button> : null}
            </div>
          ))}
        </Card>
      </section>
      <Card className="commerce-orders">
        <h2><FileCheck2 size={20} /> Pedidos, estoque e receita</h2>
        <div className="commerce-order-create">
          <select value={quoteId} onChange={(event) => setQuoteId(event.target.value)}>
            <option value="">Proposta aceita</option>
            {quotes.data?.filter((quote) => quote.status === "accepted").map((quote) => (
              <option key={quote.id} value={quote.id}>{quote.quote_number} · {quote.title}</option>
            ))}
          </select>
          <Button disabled={readOnly || !quoteId} onClick={() => createOrder.mutate()}>
            Criar pedido
          </Button>
          <select value={locationId} onChange={(event) => setLocationId(event.target.value)}>
            <option value="">Depósito para reserva</option>
            {locations.data?.filter((location) => location.active).map((location) => (
              <option key={location.id} value={location.id}>{location.code} · {location.name}</option>
            ))}
          </select>
          <label><input type="checkbox" checked={contract} onChange={(event) => setContract(event.target.checked)} /> Gerar contrato</label>
          <label><input type="checkbox" checked={recurring} disabled={!contract} onChange={(event) => setRecurring(event.target.checked)} /> Assinatura mensal</label>
        </div>
        {orders.data?.map((order) => (
          <article className="commerce-order" key={order.id}>
            <span><b>{order.order_number}</b><small>{order.items.length} itens · {order.status}</small></span>
            <strong>{new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(order.total))}</strong>
            {order.status === "draft" ? <Button disabled={readOnly || !locationId} onClick={() => reserveOrder.mutate(order.id)}>Reservar estoque</Button> : null}
            {order.status === "reserved" ? <Button disabled={readOnly} onClick={() => confirmOrder.mutate(order.id)}>Confirmar e faturar</Button> : null}
            {order.status === "confirmed" ? <Button disabled={readOnly} onClick={() => changeOrder.mutate({ id: order.id, action: "fulfill" })}>Concluir pedido</Button> : null}
            {order.status === "draft" || order.status === "reserved" ? <Button disabled={readOnly} variant="ghost" onClick={() => changeOrder.mutate({ id: order.id, action: "cancel" })}>Cancelar</Button> : null}
          </article>
        ))}
        {contracts.data?.length ? <h3>Contratos ativos</h3> : null}
        {contracts.data?.map((item) => (
          <div className="commerce-row" key={item.id}>
            <span><b>{item.contract_number}</b><small>{item.title} · {item.status}</small></span>
            <small>{item.billing_interval ? `Recorrência ${item.billing_interval}` : "Sem recorrência"}</small>
          </div>
        ))}
      </Card>
    </div>
  );
}
