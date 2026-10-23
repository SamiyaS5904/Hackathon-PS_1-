"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { ApiError, auth, setSession } from "./api";
import type { AuthOut, Member, Role } from "./types";

const TOKEN_KEY = "tt_token";
const ORG_KEY = "tt_org";
export const PUBLIC_PATHS = ["/login", "/signup", "/invite", "/demo"];

interface AuthState {
  ready: boolean;
  user: AuthOut | null;
  member: Member | null; // membership in the college currently open
  role: Role | null;
  signIn: (out: AuthOut) => void;
  signOut: () => void;
  switchOrg: (orgId: string) => void;
}

const Ctx = createContext<AuthState | null>(null);

function read(key: string): string {
  try {
    return localStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}
function write(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* private mode: stay logged in for this tab only */
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const path = usePathname();
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState<AuthOut | null>(null);
  const [orgId, setOrgId] = useState("");

  const signOut = useCallback(() => {
    write(TOKEN_KEY, null);
    setSession("", "", () => {});
    setUser(null);
    router.replace("/login");
  }, [router]);

  const signIn = useCallback(
    (out: AuthOut) => {
      write(TOKEN_KEY, out.token);
      const keep = out.memberships.find((m) => m.org_id === read(ORG_KEY));
      const org = keep?.org_id ?? out.memberships[0]?.org_id ?? "";
      write(ORG_KEY, org);
      setSession(out.token, org, signOut);
      setOrgId(org);
      setUser(out);
    },
    [signOut],
  );

  // Restore the session on load.
  useEffect(() => {
    const token = read(TOKEN_KEY);
    if (!token) {
      setReady(true);
      return;
    }
    setSession(token, read(ORG_KEY), signOut);
    let cancelled = false;
    // A backend restart or a network blip must not log people out: retry for ~10 s; only 401 ends the session.
    const restore = async () => {
      for (let attempt = 0; attempt < 7 && !cancelled; attempt++) {
        try {
          const out = await auth.me();
          if (!cancelled) signIn({ ...out, token });
          return;
        } catch (e) {
          const retryable = e instanceof ApiError && (e.status === 0 || e.status >= 500);
          if (!retryable) break;
          await new Promise((r) => setTimeout(r, 1500));
        }
      }
      if (!cancelled) write(TOKEN_KEY, null);
    };
    restore().finally(() => {
      if (!cancelled) setReady(true);
    });
    return () => {
      cancelled = true;
    };
  }, [signIn, signOut]);

  // Guard: private pages need a login.
  const isPublic = PUBLIC_PATHS.some((p) => path.startsWith(p));
  useEffect(() => {
    if (ready && !user && !isPublic) router.replace("/login");
  }, [ready, user, isPublic, router]);

  const member = useMemo(() => user?.memberships.find((m) => m.org_id === orgId) ?? null, [user, orgId]);

  const switchOrg = useCallback(
    (id: string) => {
      write(ORG_KEY, id);
      setSession(read(TOKEN_KEY), id, signOut);
      setOrgId(id);
    },
    [signOut],
  );

  return (
    <Ctx.Provider value={{ ready, user, member, role: member?.role ?? null, signIn, signOut, switchOrg }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth must be used inside AuthProvider");
  return v;
}

export const isStaff = (role: Role | null) => role === "admin" || role === "coordinator";

export const ROLE_LABEL: Record<Role, string> = {
  admin: "College Admin",
  coordinator: "Department Coordinator",
  teacher: "Teacher",
  student: "Student",
};
