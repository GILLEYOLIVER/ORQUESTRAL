import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowDownLeft,
  ArrowUpRight,
  Banknote,
  Landmark,
  Plus,
  ReceiptText,
  WalletCards,
} from "lucide-react";
import { Alert, Button, Card } from "@orkestral/ui-components";
import { ApiClientError, request } from "../lib/http";
import { useSession } from "../session/context";
import "./finance.css";

type Money = number | string;
type Account = {
  id: string;
  name: string;
  account_type: "bank" | "cash" | "payment_gateway";
  opening_balance: Money;
  current_balance: Money;
  active: boolean;
};
type Category = {
  id: string;
  name: string;
  entry_type: "income" | "expense";
  active: boolean;
};
type Entry = {
  id: string;
  account_id: string | null;
  category_id: string | null;
  description: string;
  entry_type: "income" | "expense";
  status: "pending" | "settled" | "cancelled";
  amount: Money;
  due_date: string;
  settled_at: string | null;
  overdue: boolean;
};
type Summary = {
  current_balance: Money;
  receivable_pending: Money;
  payable_pending: Money;
  income_month: Money;
  expense_month: Money;
  overdue_total: Money;
  overdue_count: number;
};
function errorMessage(error: unknown, fallback: string) {
  return error instanceof ApiClientError ? error.message : fallback;
}
function money(value: Money) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(Number(value));
}
function shortDate(value: string) {
  return new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(
    new Date(`${value}T12:00:00Z`),
  );
}

export function FinancePage() {
  const { me } = useSession();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"entries" | "accounts" | "categories">(
    "entries",
  );
  const [showEntryForm, setShowEntryForm] = useState(false);
  const [showAccountForm, setShowAccountForm] = useState(false);
  const [showCategoryForm, setShowCategoryForm] = useState(false);
  const [description, setDescription] = useState("");
  const [entryType, setEntryType] = useState<"income" | "expense">("income");
  const [amount, setAmount] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [accountName, setAccountName] = useState("");
  const [accountType, setAccountType] =
    useState<Account["account_type"]>("bank");
  const [openingBalance, setOpeningBalance] = useState("0");
  const [categoryName, setCategoryName] = useState("");
  const [categoryType, setCategoryType] = useState<"income" | "expense">(
    "income",
  );
  const [settleAccount, setSettleAccount] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const canAccounts =
    me?.permissions.includes("finance.accounts.manage") ?? false;
  const canCreate = me?.permissions.includes("finance.entries.create") ?? false;
  const canSettle = me?.permissions.includes("finance.entries.settle") ?? false;
  const canCategories =
    me?.permissions.includes("finance.categories.manage") ?? false;
  const summary = useQuery({
    queryKey: ["finance", "summary"],
    queryFn: () => request<Summary>("/finance/summary"),
  });
  const accounts = useQuery({
    queryKey: ["finance", "accounts"],
    queryFn: () => request<Account[]>("/finance/accounts"),
  });
  const categories = useQuery({
    queryKey: ["finance", "categories"],
    queryFn: () => request<Category[]>("/finance/categories"),
  });
  const entries = useQuery({
    queryKey: ["finance", "entries"],
    queryFn: () => request<Entry[]>("/finance/entries"),
  });
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["finance", "summary"] }),
      queryClient.invalidateQueries({ queryKey: ["finance", "accounts"] }),
      queryClient.invalidateQueries({ queryKey: ["finance", "entries"] }),
    ]);
  };
  const createEntry = useMutation({
    mutationFn: () =>
      request<Entry>("/finance/entries", {
        method: "POST",
        body: {
          description,
          entry_type: entryType,
          amount: Number(amount),
          due_date: dueDate,
          category_id: categoryId || null,
        },
      }),
    onSuccess: async () => {
      setDescription("");
      setAmount("");
      setDueDate("");
      setCategoryId("");
      setShowEntryForm(false);
      setFeedback("Lançamento registrado.");
      setError(null);
      await refresh();
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível criar o lançamento.")),
  });
  const settleEntry = useMutation({
    mutationFn: (entryId: string) =>
      request<Entry>(`/finance/entries/${entryId}/settle`, {
        method: "POST",
        body: { account_id: settleAccount },
      }),
    onSuccess: async () => {
      setFeedback("Pagamento baixado e saldo atualizado.");
      setError(null);
      await refresh();
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível baixar o lançamento.")),
  });
  const createAccount = useMutation({
    mutationFn: () =>
      request<Account>("/finance/accounts", {
        method: "POST",
        body: {
          name: accountName,
          account_type: accountType,
          opening_balance: Number(openingBalance) || 0,
        },
      }),
    onSuccess: async () => {
      setAccountName("");
      setOpeningBalance("0");
      setShowAccountForm(false);
      setFeedback("Conta financeira criada.");
      await refresh();
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível criar a conta.")),
  });
  const createCategory = useMutation({
    mutationFn: () =>
      request<Category>("/finance/categories", {
        method: "POST",
        body: { name: categoryName, entry_type: categoryType },
      }),
    onSuccess: async () => {
      setCategoryName("");
      setShowCategoryForm(false);
      setFeedback("Categoria criada.");
      await queryClient.invalidateQueries({
        queryKey: ["finance", "categories"],
      });
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível criar a categoria.")),
  });
  return (
    <div className="finance-page">
      <section className="finance-hero">
        <div>
          <span className="eyebrow eyebrow--light">Visão financeira</span>
          <h1>Clareza para decidir antes do vencimento.</h1>
          <p>
            Controle contas, receitas e despesas com baixa rastreável e visão
            atual do caixa.
          </p>
        </div>
        <Landmark size={62} />
      </section>
      {feedback ? <Alert variant="success">{feedback}</Alert> : null}
      {error ? <Alert variant="error">{error}</Alert> : null}
      <section className="finance-metrics">
        <Card className="primary">
          <WalletCards size={21} />
          <span>Saldo atual</span>
          <strong>{money(summary.data?.current_balance ?? 0)}</strong>
        </Card>
        <Card>
          <ArrowDownLeft size={21} />
          <span>A receber</span>
          <strong>{money(summary.data?.receivable_pending ?? 0)}</strong>
        </Card>
        <Card>
          <ArrowUpRight size={21} />
          <span>A pagar</span>
          <strong>{money(summary.data?.payable_pending ?? 0)}</strong>
        </Card>
        <Card className={summary.data?.overdue_count ? "danger" : ""}>
          <AlertCircle size={21} />
          <span>Em atraso</span>
          <strong>{money(summary.data?.overdue_total ?? 0)}</strong>
          <small>{summary.data?.overdue_count ?? 0} lançamentos</small>
        </Card>
      </section>
      <div className="finance-tabs">
        <button
          className={tab === "entries" ? "active" : ""}
          onClick={() => setTab("entries")}
          type="button"
        >
          Lançamentos
        </button>
        <button
          className={tab === "accounts" ? "active" : ""}
          onClick={() => setTab("accounts")}
          type="button"
        >
          Contas
        </button>
        <button
          className={tab === "categories" ? "active" : ""}
          onClick={() => setTab("categories")}
          type="button"
        >
          Categorias
        </button>
      </div>
      {tab === "entries" ? (
        <>
          <div className="finance-heading">
            <div>
              <span className="eyebrow">Contas a pagar e receber</span>
              <h2>Lançamentos financeiros</h2>
            </div>
            {canCreate ? (
              <Button onClick={() => setShowEntryForm((value) => !value)}>
                <Plus size={16} /> Novo lançamento
              </Button>
            ) : null}
          </div>
          {showEntryForm ? (
            <Card className="finance-form">
              <label>
                Tipo
                <select
                  value={entryType}
                  onChange={(event) => {
                    setEntryType(event.target.value as typeof entryType);
                    setCategoryId("");
                  }}
                >
                  <option value="income">Receita</option>
                  <option value="expense">Despesa</option>
                </select>
              </label>
              <label className="wide">
                Descrição
                <input
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                />
              </label>
              <label>
                Valor
                <input
                  inputMode="decimal"
                  value={amount}
                  onChange={(event) => setAmount(event.target.value)}
                />
              </label>
              <label>
                Vencimento
                <input
                  type="date"
                  value={dueDate}
                  onChange={(event) => setDueDate(event.target.value)}
                />
              </label>
              <label>
                Categoria
                <select
                  value={categoryId}
                  onChange={(event) => setCategoryId(event.target.value)}
                >
                  <option value="">Sem categoria</option>
                  {categories.data
                    ?.filter((category) => category.entry_type === entryType)
                    .map((category) => (
                      <option key={category.id} value={category.id}>
                        {category.name}
                      </option>
                    ))}
                </select>
              </label>
              <Button
                disabled={description.trim().length < 2 || !amount || !dueDate}
                loading={createEntry.isPending}
                onClick={() => createEntry.mutate()}
              >
                Registrar
              </Button>
            </Card>
          ) : null}
          <Card className="entry-table">
            <div className="entry-table__settle">
              <span>Conta usada para baixar pagamentos:</span>
              <select
                value={settleAccount}
                onChange={(event) => setSettleAccount(event.target.value)}
              >
                <option value="">Selecione</option>
                {accounts.data
                  ?.filter((account) => account.active)
                  .map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.name}
                    </option>
                  ))}
              </select>
            </div>
            {entries.data?.length ? (
              entries.data.map((entry) => (
                <article
                  className={`${entry.entry_type} ${entry.overdue ? "overdue" : ""}`}
                  key={entry.id}
                >
                  <span className="entry-icon">
                    {entry.entry_type === "income" ? (
                      <ArrowDownLeft size={19} />
                    ) : (
                      <ArrowUpRight size={19} />
                    )}
                  </span>
                  <span>
                    <strong>{entry.description}</strong>
                    <small>
                      Vence {shortDate(entry.due_date)}
                      {entry.overdue ? " · Em atraso" : ""}
                    </small>
                  </span>
                  <span className="entry-value">
                    <strong>
                      {entry.entry_type === "income" ? "+" : "-"}
                      {money(entry.amount)}
                    </strong>
                    <small>
                      {entry.status === "pending"
                        ? "Pendente"
                        : entry.status === "settled"
                          ? "Pago"
                          : "Cancelado"}
                    </small>
                  </span>
                  {canSettle && entry.status === "pending" ? (
                    <Button
                      disabled={!settleAccount}
                      loading={
                        settleEntry.isPending &&
                        settleEntry.variables === entry.id
                      }
                      onClick={() => settleEntry.mutate(entry.id)}
                      variant="secondary"
                    >
                      Dar baixa
                    </Button>
                  ) : null}
                </article>
              ))
            ) : (
              <p className="finance-empty">Nenhum lançamento cadastrado.</p>
            )}
          </Card>
        </>
      ) : null}
      {tab === "accounts" ? (
        <>
          <div className="finance-heading">
            <div>
              <span className="eyebrow">Disponibilidades</span>
              <h2>Contas financeiras</h2>
            </div>
            {canAccounts ? (
              <Button onClick={() => setShowAccountForm((value) => !value)}>
                <Plus size={16} /> Nova conta
              </Button>
            ) : null}
          </div>
          {showAccountForm ? (
            <Card className="account-form">
              <input
                placeholder="Nome da conta"
                value={accountName}
                onChange={(event) => setAccountName(event.target.value)}
              />
              <select
                value={accountType}
                onChange={(event) =>
                  setAccountType(event.target.value as typeof accountType)
                }
              >
                <option value="bank">Conta bancária</option>
                <option value="cash">Caixa</option>
                <option value="payment_gateway">Gateway de pagamento</option>
              </select>
              <input
                inputMode="decimal"
                placeholder="Saldo inicial"
                value={openingBalance}
                onChange={(event) => setOpeningBalance(event.target.value)}
              />
              <Button
                disabled={accountName.trim().length < 2}
                loading={createAccount.isPending}
                onClick={() => createAccount.mutate()}
              >
                Criar conta
              </Button>
            </Card>
          ) : null}
          <section className="account-grid">
            {accounts.data?.map((account) => (
              <Card key={account.id}>
                <Banknote size={22} />
                <span>
                  {account.account_type === "bank"
                    ? "Banco"
                    : account.account_type === "cash"
                      ? "Caixa"
                      : "Gateway"}
                </span>
                <h3>{account.name}</h3>
                <strong>{money(account.current_balance)}</strong>
                <small>
                  {account.active ? "Conta ativa" : "Conta inativa"}
                </small>
              </Card>
            ))}
          </section>
        </>
      ) : null}
      {tab === "categories" ? (
        <>
          <div className="finance-heading">
            <div>
              <span className="eyebrow">Classificação</span>
              <h2>Categorias financeiras</h2>
            </div>
            {canCategories ? (
              <Button onClick={() => setShowCategoryForm((value) => !value)}>
                <Plus size={16} /> Nova categoria
              </Button>
            ) : null}
          </div>
          {showCategoryForm ? (
            <Card className="category-form">
              <input
                placeholder="Nome da categoria"
                value={categoryName}
                onChange={(event) => setCategoryName(event.target.value)}
              />
              <select
                value={categoryType}
                onChange={(event) =>
                  setCategoryType(event.target.value as typeof categoryType)
                }
              >
                <option value="income">Receita</option>
                <option value="expense">Despesa</option>
              </select>
              <Button
                disabled={categoryName.trim().length < 2}
                loading={createCategory.isPending}
                onClick={() => createCategory.mutate()}
              >
                Criar categoria
              </Button>
            </Card>
          ) : null}
          <section className="category-grid">
            {categories.data?.map((category) => (
              <Card className={category.entry_type} key={category.id}>
                <ReceiptText size={20} />
                <span>
                  {category.entry_type === "income" ? "Receita" : "Despesa"}
                </span>
                <h3>{category.name}</h3>
              </Card>
            ))}
          </section>
        </>
      ) : null}
    </div>
  );
}
