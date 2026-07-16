import type { ReactNode } from "react";
import { useSession } from "../session/context";

interface PermissionGuardProps {
  all?: string[];
  any?: string[];
  children: ReactNode;
  fallback?: ReactNode;
}

export function PermissionGuard({
  all = [],
  any = [],
  children,
  fallback = null,
}: PermissionGuardProps) {
  const { me } = useSession();
  const permissions = new Set(me?.permissions ?? []);
  const hasAll = all.every((permission) => permissions.has(permission));
  const hasAny =
    any.length === 0 || any.some((permission) => permissions.has(permission));

  return hasAll && hasAny ? children : fallback;
}
