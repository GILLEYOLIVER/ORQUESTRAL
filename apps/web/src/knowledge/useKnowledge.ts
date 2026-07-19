import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { request } from "../lib/http";

export type KnowledgeBase = {
  id: string;
  name: string;
  description: string | null;
  status: string;
};

export type KnowledgeDocument = {
  id: string;
  knowledge_base_id: string;
  name: string;
  source_type: string;
  size_bytes: number;
  status: "uploaded" | "processing" | "ready" | "error";
  error_summary: string | null;
};

export type KnowledgeSearchResult = {
  document_id: string;
  document_name: string;
  chunk_index: number;
  content: string;
  score: number;
};

type AgentOption = {
  id: string;
  name: string;
  knowledge_base_id: string | null;
};

export function useKnowledgeBases() {
  return useQuery({
    queryKey: ["knowledge-bases"],
    queryFn: () => request<KnowledgeBase[]>("/knowledge-bases"),
  });
}

export function useKnowledgeDocuments(baseId: string | null) {
  return useQuery({
    queryKey: ["knowledge-documents", baseId],
    queryFn: () =>
      request<KnowledgeDocument[]>(`/knowledge-bases/${baseId}/documents`),
    enabled: Boolean(baseId),
    refetchInterval: (query) =>
      query.state.data?.some(
        (item) => item.status === "uploaded" || item.status === "processing",
      )
        ? 1500
        : false,
  });
}

export function useKnowledgeAgents() {
  return useQuery({
    queryKey: ["agents"],
    queryFn: () => request<AgentOption[]>("/agents"),
  });
}

export function useKnowledgeActions() {
  const queryClient = useQueryClient();
  const refreshBases = () =>
    queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] });
  const refreshDocuments = (baseId: string) =>
    queryClient.invalidateQueries({
      queryKey: ["knowledge-documents", baseId],
    });

  const createBase = useMutation({
    mutationFn: (payload: { name: string; description: string }) =>
      request<KnowledgeBase>("/knowledge-bases", {
        method: "POST",
        body: payload,
      }),
    onSuccess: refreshBases,
  });
  const uploadDocument = useMutation({
    mutationFn: ({ baseId, file }: { baseId: string; file: File }) => {
      const formData = new FormData();
      formData.append("file", file);
      return request<KnowledgeDocument>(
        `/knowledge-bases/${baseId}/documents`,
        {
          method: "POST",
          body: formData,
          timeoutMs: 30_000,
        },
      );
    },
    onSuccess: (document) => refreshDocuments(document.knowledge_base_id),
  });
  const importWebPage = useMutation({
    mutationFn: ({ baseId, url }: { baseId: string; url: string }) =>
      request<KnowledgeDocument>(`/knowledge-bases/${baseId}/web`, {
        method: "POST",
        body: { url },
      }),
    onSuccess: (document) => refreshDocuments(document.knowledge_base_id),
  });
  const reprocessDocument = useMutation({
    mutationFn: ({
      baseId,
      documentId,
    }: {
      baseId: string;
      documentId: string;
    }) =>
      request<KnowledgeDocument>(
        `/knowledge-bases/${baseId}/documents/${documentId}/reprocess`,
        { method: "POST" },
      ),
    onSuccess: (document) => refreshDocuments(document.knowledge_base_id),
  });
  const deleteDocument = useMutation({
    mutationFn: ({
      baseId,
      documentId,
    }: {
      baseId: string;
      documentId: string;
    }) =>
      request<void>(`/knowledge-bases/${baseId}/documents/${documentId}`, {
        method: "DELETE",
      }),
    onSuccess: (_result, variables) => refreshDocuments(variables.baseId),
  });
  const search = useMutation({
    mutationFn: ({ baseId, query }: { baseId: string; query: string }) =>
      request<KnowledgeSearchResult[]>(
        `/knowledge-bases/${baseId}/search?q=${encodeURIComponent(query)}&limit=6`,
      ),
  });
  const assignAgent = useMutation({
    mutationFn: ({
      agentId,
      baseId,
    }: {
      agentId: string;
      baseId: string | null;
    }) =>
      request<AgentOption>(`/agents/${agentId}`, {
        method: "PATCH",
        body: { knowledge_base_id: baseId },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["agents"] }),
  });

  return {
    assignAgent,
    createBase,
    deleteDocument,
    importWebPage,
    reprocessDocument,
    search,
    uploadDocument,
  };
}
