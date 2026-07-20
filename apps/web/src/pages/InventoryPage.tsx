import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowDownToLine,
  ArrowUpFromLine,
  Boxes,
  MapPin,
  Plus,
  Scale,
  Warehouse,
} from "lucide-react";
import { Alert, Button, Card } from "@orkestral/ui-components";
import { ApiClientError, request } from "../lib/http";
import { useSession } from "../session/context";
import "./inventory.css";

type Quantity = number | string;
type Item = {
  id: string;
  sku: string;
  name: string;
  description: string | null;
  category_id: string | null;
  unit: string;
  minimum_stock: Quantity;
  total_quantity: Quantity;
  low_stock: boolean;
  active: boolean;
};
type Location = {
  id: string;
  code: string;
  name: string;
  description: string | null;
  active: boolean;
};
type Category = {
  id: string;
  name: string;
  description: string | null;
  active: boolean;
};
type Balance = {
  id: string;
  item_id: string;
  location_id: string;
  quantity: Quantity;
};
type Movement = {
  id: string;
  item_id: string;
  location_id: string;
  movement_type: "in" | "out" | "adjustment";
  quantity: Quantity;
  previous_quantity: Quantity;
  resulting_quantity: Quantity;
  reason: string;
  occurred_at: string;
};
type Summary = {
  items_total: number;
  locations_total: number;
  low_stock_total: number;
  total_quantity: Quantity;
};
function errorMessage(error: unknown, fallback: string) {
  return error instanceof ApiClientError ? error.message : fallback;
}
function quantity(value: Quantity) {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 3 }).format(
    Number(value),
  );
}
function dateTime(value: string) {
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

export function InventoryPage() {
  const { me } = useSession();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"items" | "movements" | "locations">("items");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showItemForm, setShowItemForm] = useState(false);
  const [showLocationForm, setShowLocationForm] = useState(false);
  const [sku, setSku] = useState("");
  const [name, setName] = useState("");
  const [minimumStock, setMinimumStock] = useState("0");
  const [categoryId, setCategoryId] = useState("");
  const [locationCode, setLocationCode] = useState("");
  const [locationName, setLocationName] = useState("");
  const [movementLocation, setMovementLocation] = useState("");
  const [movementType, setMovementType] = useState<"in" | "out" | "adjustment">(
    "in",
  );
  const [movementQuantity, setMovementQuantity] = useState("");
  const [movementReason, setMovementReason] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const canItems = me?.permissions.includes("inventory.items.manage") ?? false;
  const canMovements =
    me?.permissions.includes("inventory.movements.create") ?? false;
  const canLocations =
    me?.permissions.includes("inventory.locations.manage") ?? false;
  const items = useQuery({
    queryKey: ["inventory", "items"],
    queryFn: () => request<Item[]>("/inventory/items"),
  });
  const locations = useQuery({
    queryKey: ["inventory", "locations"],
    queryFn: () => request<Location[]>("/inventory/locations"),
  });
  const categories = useQuery({
    queryKey: ["inventory", "categories"],
    queryFn: () => request<Category[]>("/inventory/categories"),
  });
  const summary = useQuery({
    queryKey: ["inventory", "summary"],
    queryFn: () => request<Summary>("/inventory/summary"),
  });
  const movements = useQuery({
    queryKey: ["inventory", "movements"],
    queryFn: () => request<Movement[]>("/inventory/movements"),
  });
  const balances = useQuery({
    queryKey: ["inventory", "items", selectedId, "balances"],
    queryFn: () =>
      request<Balance[]>(`/inventory/items/${selectedId}/balances`),
    enabled: Boolean(selectedId),
  });
  const selected = useMemo(
    () => items.data?.find((item) => item.id === selectedId) ?? null,
    [items.data, selectedId],
  );
  useEffect(() => {
    if (!selectedId && items.data?.length) setSelectedId(items.data[0].id);
  }, [items.data, selectedId]);
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["inventory", "items"] }),
      queryClient.invalidateQueries({ queryKey: ["inventory", "summary"] }),
      queryClient.invalidateQueries({ queryKey: ["inventory", "movements"] }),
      queryClient.invalidateQueries({
        queryKey: ["inventory", "items", selectedId, "balances"],
      }),
    ]);
  };
  const createItem = useMutation({
    mutationFn: () =>
      request<Item>("/inventory/items", {
        method: "POST",
        body: {
          sku,
          name,
          category_id: categoryId || null,
          minimum_stock: Number(minimumStock) || 0,
        },
      }),
    onSuccess: async (item) => {
      setSku("");
      setName("");
      setMinimumStock("0");
      setCategoryId("");
      setSelectedId(item.id);
      setShowItemForm(false);
      setFeedback("Item cadastrado com sucesso.");
      setError(null);
      await refresh();
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível cadastrar o item.")),
  });
  const createLocation = useMutation({
    mutationFn: () =>
      request<Location>("/inventory/locations", {
        method: "POST",
        body: { code: locationCode, name: locationName },
      }),
    onSuccess: async () => {
      setLocationCode("");
      setLocationName("");
      setShowLocationForm(false);
      setFeedback("Local de estoque criado.");
      await queryClient.invalidateQueries({
        queryKey: ["inventory", "locations"],
      });
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível criar o local.")),
  });
  const createMovement = useMutation({
    mutationFn: () =>
      request<Movement>("/inventory/movements", {
        method: "POST",
        body: {
          item_id: selectedId,
          location_id: movementLocation,
          movement_type: movementType,
          quantity:
            movementType === "adjustment" ? null : Number(movementQuantity),
          adjusted_quantity:
            movementType === "adjustment" ? Number(movementQuantity) : null,
          reason: movementReason,
        },
      }),
    onSuccess: async () => {
      setMovementQuantity("");
      setMovementReason("");
      setFeedback("Movimentação registrada e saldo atualizado.");
      setError(null);
      await refresh();
    },
    onError: (caught) =>
      setError(
        errorMessage(caught, "Não foi possível registrar a movimentação."),
      ),
  });
  return (
    <div className="inventory-page">
      <section className="inventory-hero">
        <div>
          <span className="eyebrow eyebrow--light">Controle operacional</span>
          <h1>O saldo certo, no lugar certo, em tempo real.</h1>
          <p>
            Cadastre itens, organize depósitos e acompanhe cada entrada, saída e
            ajuste com histórico confiável.
          </p>
        </div>
        <Warehouse size={62} />
      </section>
      {feedback ? <Alert variant="success">{feedback}</Alert> : null}
      {error ? <Alert variant="error">{error}</Alert> : null}
      <section className="inventory-metrics">
        <Card>
          <Boxes size={20} />
          <strong>{summary.data?.items_total ?? 0}</strong>
          <span>itens ativos</span>
        </Card>
        <Card>
          <MapPin size={20} />
          <strong>{summary.data?.locations_total ?? 0}</strong>
          <span>locais</span>
        </Card>
        <Card className={summary.data?.low_stock_total ? "warning" : ""}>
          <AlertTriangle size={20} />
          <strong>{summary.data?.low_stock_total ?? 0}</strong>
          <span>estoques baixos</span>
        </Card>
        <Card>
          <Scale size={20} />
          <strong>{quantity(summary.data?.total_quantity ?? 0)}</strong>
          <span>unidades totais</span>
        </Card>
      </section>
      <div className="inventory-tabs">
        <button
          className={tab === "items" ? "active" : ""}
          onClick={() => setTab("items")}
          type="button"
        >
          Itens e saldos
        </button>
        <button
          className={tab === "movements" ? "active" : ""}
          onClick={() => setTab("movements")}
          type="button"
        >
          Movimentações
        </button>
        <button
          className={tab === "locations" ? "active" : ""}
          onClick={() => setTab("locations")}
          type="button"
        >
          Locais
        </button>
      </div>
      {tab === "items" ? (
        <>
          <div className="inventory-heading">
            <div>
              <span className="eyebrow">Catálogo</span>
              <h2>Itens em estoque</h2>
            </div>
            {canItems ? (
              <Button onClick={() => setShowItemForm((value) => !value)}>
                <Plus size={16} /> Novo item
              </Button>
            ) : null}
          </div>
          {showItemForm ? (
            <Card className="inventory-form">
              <label>
                SKU
                <input
                  value={sku}
                  onChange={(event) => setSku(event.target.value)}
                />
              </label>
              <label>
                Nome
                <input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                />
              </label>
              <label>
                Estoque mínimo
                <input
                  inputMode="decimal"
                  value={minimumStock}
                  onChange={(event) => setMinimumStock(event.target.value)}
                />
              </label>
              <label>
                Categoria
                <select
                  value={categoryId}
                  onChange={(event) => setCategoryId(event.target.value)}
                >
                  <option value="">Sem categoria</option>
                  {categories.data?.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name}
                    </option>
                  ))}
                </select>
              </label>
              <Button
                disabled={!sku.trim() || name.trim().length < 2}
                loading={createItem.isPending}
                onClick={() => createItem.mutate()}
              >
                Cadastrar item
              </Button>
            </Card>
          ) : null}
          <section className="inventory-workspace">
            <aside className="inventory-list">
              {items.data?.length ? (
                items.data.map((item) => (
                  <button
                    className={`${item.id === selectedId ? "active" : ""} ${item.low_stock ? "low" : ""}`}
                    key={item.id}
                    onClick={() => setSelectedId(item.id)}
                    type="button"
                  >
                    <span>
                      <strong>{item.name}</strong>
                      <small>{item.sku}</small>
                    </span>
                    <i>{quantity(item.total_quantity)}</i>
                  </button>
                ))
              ) : (
                <p className="inventory-empty">Nenhum item cadastrado.</p>
              )}
            </aside>
            <Card className="inventory-detail">
              {selected ? (
                <>
                  <div className="inventory-detail__top">
                    <div>
                      <span className="inventory-sku">{selected.sku}</span>
                      <h2>{selected.name}</h2>
                      <p>
                        {selected.description ||
                          "Item controlado por movimentações auditáveis."}
                      </p>
                    </div>
                    {selected.low_stock ? (
                      <span className="low-badge">
                        <AlertTriangle size={15} /> Estoque baixo
                      </span>
                    ) : null}
                  </div>
                  <div className="stock-total">
                    <span>Saldo total</span>
                    <strong>{quantity(selected.total_quantity)}</strong>
                    <small>Mínimo: {quantity(selected.minimum_stock)}</small>
                  </div>
                  <h3>Saldo por local</h3>
                  <div className="balance-list">
                    {balances.data?.length ? (
                      balances.data.map((balance) => (
                        <article key={balance.id}>
                          <MapPin size={17} />
                          <span>
                            {locations.data?.find(
                              (location) => location.id === balance.location_id,
                            )?.name ?? "Local"}
                          </span>
                          <strong>{quantity(balance.quantity)}</strong>
                        </article>
                      ))
                    ) : (
                      <p className="inventory-empty">
                        Ainda não há saldo registrado.
                      </p>
                    )}
                  </div>
                  {canMovements ? (
                    <form
                      className="movement-form"
                      onSubmit={(event) => {
                        event.preventDefault();
                        if (
                          movementLocation &&
                          movementQuantity &&
                          movementReason.trim().length >= 2
                        )
                          createMovement.mutate();
                      }}
                    >
                      <h3>Registrar movimentação</h3>
                      <select
                        value={movementLocation}
                        onChange={(event) =>
                          setMovementLocation(event.target.value)
                        }
                      >
                        <option value="">Selecione o local</option>
                        {locations.data
                          ?.filter((location) => location.active)
                          .map((location) => (
                            <option key={location.id} value={location.id}>
                              {location.name}
                            </option>
                          ))}
                      </select>
                      <select
                        value={movementType}
                        onChange={(event) =>
                          setMovementType(
                            event.target.value as typeof movementType,
                          )
                        }
                      >
                        <option value="in">Entrada</option>
                        <option value="out">Saída</option>
                        <option value="adjustment">
                          Ajuste para saldo contado
                        </option>
                      </select>
                      <input
                        inputMode="decimal"
                        placeholder="Quantidade"
                        value={movementQuantity}
                        onChange={(event) =>
                          setMovementQuantity(event.target.value)
                        }
                      />
                      <input
                        placeholder="Motivo"
                        value={movementReason}
                        onChange={(event) =>
                          setMovementReason(event.target.value)
                        }
                      />
                      <Button loading={createMovement.isPending} type="submit">
                        Registrar
                      </Button>
                    </form>
                  ) : null}
                </>
              ) : (
                <p className="inventory-empty">Selecione um item.</p>
              )}
            </Card>
          </section>
        </>
      ) : null}
      {tab === "movements" ? (
        <>
          <div className="inventory-heading">
            <div>
              <span className="eyebrow">Rastreabilidade</span>
              <h2>Histórico de movimentações</h2>
            </div>
          </div>
          <Card className="movement-history">
            {movements.data?.length ? (
              movements.data.map((movement) => (
                <article key={movement.id}>
                  <span
                    className={`movement-icon movement-icon--${movement.movement_type}`}
                  >
                    {movement.movement_type === "in" ? (
                      <ArrowDownToLine size={18} />
                    ) : movement.movement_type === "out" ? (
                      <ArrowUpFromLine size={18} />
                    ) : (
                      <Scale size={18} />
                    )}
                  </span>
                  <span>
                    <strong>
                      {items.data?.find((item) => item.id === movement.item_id)
                        ?.name ?? "Item"}
                    </strong>
                    <small>
                      {movement.reason} · {dateTime(movement.occurred_at)}
                    </small>
                  </span>
                  <span>
                    <strong>
                      {movement.movement_type === "out"
                        ? "-"
                        : movement.movement_type === "in"
                          ? "+"
                          : "="}
                      {quantity(movement.quantity)}
                    </strong>
                    <small>Saldo {quantity(movement.resulting_quantity)}</small>
                  </span>
                </article>
              ))
            ) : (
              <p className="inventory-empty">
                Nenhuma movimentação registrada.
              </p>
            )}
          </Card>
        </>
      ) : null}
      {tab === "locations" ? (
        <>
          <div className="inventory-heading">
            <div>
              <span className="eyebrow">Estrutura física</span>
              <h2>Locais de armazenamento</h2>
            </div>
            {canLocations ? (
              <Button onClick={() => setShowLocationForm((value) => !value)}>
                <Plus size={16} /> Novo local
              </Button>
            ) : null}
          </div>
          {showLocationForm ? (
            <Card className="location-form">
              <input
                placeholder="Código"
                value={locationCode}
                onChange={(event) => setLocationCode(event.target.value)}
              />
              <input
                placeholder="Nome do local"
                value={locationName}
                onChange={(event) => setLocationName(event.target.value)}
              />
              <Button
                disabled={
                  !locationCode.trim() || locationName.trim().length < 2
                }
                loading={createLocation.isPending}
                onClick={() => createLocation.mutate()}
              >
                Criar local
              </Button>
            </Card>
          ) : null}
          <section className="location-grid">
            {locations.data?.map((location) => (
              <Card key={location.id}>
                <MapPin size={22} />
                <span>{location.code}</span>
                <h3>{location.name}</h3>
                <p>
                  {location.description || "Local ativo para movimentações."}
                </p>
              </Card>
            ))}
          </section>
        </>
      ) : null}
    </div>
  );
}
