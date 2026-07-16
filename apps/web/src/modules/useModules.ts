import { useQuery } from "@tanstack/react-query";
import type { ModuleResponse } from "@orkestral/shared-types";
import { request } from "../lib/http";
import { useSession } from "../session/context";

export function useModules(enabled = true) {
  const { me, status } = useSession();
  return useQuery({
    queryKey: ["modules", me?.current_company?.id],
    queryFn: () => request<ModuleResponse[]>("/modules"),
    enabled:
      enabled &&
      status === "authenticated" &&
      Boolean(me?.current_company) &&
      (me?.permissions.includes("modules.view") ?? false),
  });
}

export function isModuleActive(
  modules: ModuleResponse[] | undefined,
  moduleCode: string,
) {
  return modules?.some(
    (module) =>
      module.code === moduleCode && module.company_status === "active",
  );
}
