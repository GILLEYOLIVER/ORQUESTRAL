import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgePercent, Boxes, ShoppingBag } from "lucide-react";
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
  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ["commerce", "variants"] }),
      queryClient.invalidateQueries({ queryKey: ["commerce", "promotions"] }),
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
    </div>
  );
}
